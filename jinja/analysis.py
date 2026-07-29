"""
The one way in: hand it template text, get back what the template needs and what is wrong with it.

Everything else in this package is an internal step. Parsing happens here, exactly once, and both
halves are handed the same result: the walk that builds the variable tree, and the checks.
"""

from typing import NamedTuple

from jinja2 import TemplateAssertionError, meta

from .diagnostics import Diagnostic, Layout
from .jinja_utils import ParseResult, parse_result
from .validation import validate_template_jinja
from .variable_tree import VariableNode, VariableTreeVisitor


class TemplateReport(NamedTuple):
    """
    variables: the variable tree described in README.md, empty when the template will not parse
    diagnostics: every problem found, in the order a reader should see them
    """

    variables: dict[str, VariableNode]
    diagnostics: list[Diagnostic]


def analyze(text: str) -> TemplateReport:
    parsed = parse_result(text)
    variables, conflicts = _walk(parsed)
    return TemplateReport(variables, validate_template_jinja(text, parsed) + conflicts)


def _walk(parsed: ParseResult) -> tuple[dict[str, VariableNode], list[Diagnostic]]:
    """Build the variable tree from an already-parsed template, and word what the walk noticed."""
    ast = parsed.ast
    if not ast:
        return {}, []

    visitor = VariableTreeVisitor()
    visitor.visit(ast)

    # find_undeclared_variables already decides which names the template requires
    # the visitor only supplies the structure for those variables
    try:
        required = meta.find_undeclared_variables(ast)
    except TemplateAssertionError:
        # It compiles the template, so a filter this environment does not register fails here
        # rather than at parse time. docxtpl templates may rely on filters the caller adds later.
        return {}, []

    variables: dict[str, VariableNode] = {name: visitor.root.get(name, {"type": "string"}) for name in sorted(required)}
    _refine_list_formats(variables)
    return variables, list(dict.fromkeys(visitor.conflicts + _printed_containers(visitor)))


def _printed_containers(visitor: VariableTreeVisitor) -> list[Diagnostic]:
    """Warn for each {{ a.b }} that turned out to name an object or a list rather than a value."""
    warnings = []
    for lineno, root, attrs in visitor.printed:
        node = _lookup_path(visitor.root, root, attrs)
        node_type = node.get("type") if node else None
        path = ".".join([root, *attrs])
        # A path the visitor already reported has the same root cause, so one warning is enough.
        if node_type not in ("object", "list") or path in visitor.conflict_paths:
            continue
        if node_type == "object":
            article, rendered = "an object", "{'field': ...}"
            fix = "print a single field, e.g. {{ " + path + ".field }}"
        else:
            article, rendered = "a list", "['item', ...]"
            fix = "loop over it with {% for item in " + path + " %}"
        warnings.append(
            Diagnostic(
                code="printed-whole-container",
                layout=Layout.DETAIL,
                line=lineno,
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
