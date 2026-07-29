"""
The one way in: hand it template text, get back what the template needs and what is wrong with it.

Everything else in this package is an internal step. Parsing happens here, exactly once, and both
halves are handed the same result: the walk that builds the variable tree, and the checks in checks/.
"""

from typing import NamedTuple

from jinja2 import TemplateAssertionError, meta

from .checks.delimiters import check_malformed_tags, check_misplaced_statement_delimiters
from .checks.syntax import check_jinja_syntax, check_mismatched_tags
from .checks.tags import check_builtin_method_attributes, check_hyphenated_variables, check_merge_tags_outside_loops
from .jinja_utils import ParseResult, parse_result, warning_to_string
from .variable_tree import VariableNode, VariableTreeVisitor


class TemplateReport(NamedTuple):
    """
    variables: the variable tree described in README.md, empty when the template will not parse
    diagnostics: every problem found, in the order a reader should see them
    """

    variables: dict[str, VariableNode]
    diagnostics: list[str]


def analyze_jinja_template(text: str) -> TemplateReport:
    parsed = parse_result(text)
    validation_errors = _validate(text, parsed)
    variables, variable_conflict_errors = _walk(parsed)
    return TemplateReport(variables, validation_errors + variable_conflict_errors)


def _validate(full_text: str, parsed: ParseResult) -> list[str]:
    "Run every text check, falling back to Jinja's parser for what they do not cover"
    lines = full_text.split("\n")

    # A broken delimiter makes Jinja read the tag as plain text, so nothing after it can be
    # trusted. Neither Jinja's own error nor the tag counts mean anything. See the README.
    broken_delimiters = check_malformed_tags(lines) + check_misplaced_statement_delimiters(lines)
    unbalanced_blocks = check_mismatched_tags(full_text)

    warnings = list(broken_delimiters or unbalanced_blocks)
    if not broken_delimiters:
        warnings.extend(check_jinja_syntax(full_text, parsed, blocks_already_counted=bool(unbalanced_blocks)))

    # A template can be perfectly valid and still hit these, so they must never hide a real
    # syntax error from the fallback above.
    warnings.extend(check_hyphenated_variables(full_text))
    warnings.extend(check_builtin_method_attributes(full_text))
    warnings.extend(check_merge_tags_outside_loops(full_text))
    return warnings


def _walk(parsed: ParseResult) -> tuple[dict[str, VariableNode], list[str]]:
    """Build the variable tree from an already-parsed template, and warn about what it finds."""
    ast = parsed.ast
    if not ast:
        return {}, []

    visitor = VariableTreeVisitor()
    visitor.visit(ast)

    # Jinja decides which names the template actually asks for. The walk only says what shape
    # each one has. Anything the walk saw but Jinja did not ask for is dropped.
    try:
        required = meta.find_undeclared_variables(ast)
    except TemplateAssertionError:
        # Asking Jinja for the names compiles the template, so an unknown filter fails here rather
        # than at parse time. A template may well use a filter the caller registers later.
        return {}, []

    variables: dict[str, VariableNode] = {name: visitor.root.get(name, {"type": "string"}) for name in sorted(required)}
    _refine_list_formats(variables)
    return variables, list(dict.fromkeys(visitor.conflicts + _printed_containers(visitor)))


def _printed_containers(visitor: VariableTreeVisitor) -> list[str]:
    """Warn for each {{ a.b }} that turned out to name an object or a list rather than a value."""
    warnings = []
    for lineno, root, attrs in visitor.printed:
        node = _lookup_path(visitor.root, root, attrs)
        node_type = node.get("type") if node else None
        path = ".".join([root, *attrs])
        # Already reported as a clash. Same cause, so one warning is enough.
        if node_type not in ("object", "list") or path in visitor.conflict_paths:
            continue
        if node_type == "object":
            article, rendered = "an object", "{'field': ...}"
            fix = "print a single field, e.g. {{ " + path + ".field }}"
        else:
            article, rendered = "a list", "['item', ...]"
            fix = "loop over it with {% for item in " + path + " %}"
        warnings.append(
            warning_to_string(
                line_no=lineno,
                title=f"'{path}' is printed as a whole {node_type}",
                found="{{ " + path + " }}",
                fix=fix,
                reason=(
                    f"the template also reads fields from '{path}', so it receives {article}. "
                    f"Printing it renders {rendered} into the document."
                ),
            )
        )
    return warnings


def _lookup_path(tree: dict[str, VariableNode], root: str, attrs: list[str]) -> VariableNode | None:
    node = tree.get(root)
    for segment in attrs:
        if not node:
            return None
        node = node.get("properties", {}).get(segment)
    return node


def _refine_list_formats(tree: dict[str, VariableNode]) -> None:
    """Derive item_format for every list in the tree, now that its item's fields are known."""
    for var_info in tree.values():
        if var_info.get("type") == "list":
            if "properties" in var_info and var_info["properties"]:
                var_info["item_format"] = "object"
                _refine_list_formats(var_info["properties"])
            else:
                var_info["item_format"] = "string"
                var_info.pop("properties", None)
        elif var_info.get("type") == "object":
            _refine_list_formats(var_info.get("properties", {}))
