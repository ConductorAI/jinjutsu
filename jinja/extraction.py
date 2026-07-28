"""
Turn a template into the variable tree described in variable_tree.py, plus the warnings the walk found.

The tree and the walk that builds it live in variable_tree.py. This module drives them: parse once,
walk, ask Jinja which names the template actually requires, then fill in the item_format that only
a finished tree can answer, and word the conflicts that only a finished tree can confirm.
"""

from typing import NamedTuple

from jinja2 import TemplateAssertionError, meta

from .jinja_utils import format_warning, parse_result
from .variable_tree import VariableNode, VariableTreeVisitor


class TemplateAnalysis(NamedTuple):
    """
    variables: the variable tree described in variable_tree.py, keyed by top-level name
    conflicts: warnings for variables used in two incompatible ways
    """

    variables: dict[str, VariableNode]
    conflicts: list[str]


def analyze_template(text: str) -> TemplateAnalysis:
    """Walk a template once to derive both its variable tree and conflict warnings."""
    ast = parse_result(text).ast
    if not ast:
        return TemplateAnalysis({}, [])

    visitor = VariableTreeVisitor()
    visitor.visit(ast)

    # find_undeclared_variables already decides which names the template requires
    # the visitor only supplies the structure for those variables
    try:
        required = meta.find_undeclared_variables(ast)
    except TemplateAssertionError:
        # It compiles the template, so a filter this environment does not register fails here
        # rather than at parse time. docxtpl templates may rely on filters the caller adds later.
        return TemplateAnalysis({}, [])

    variables: dict[str, VariableNode] = {name: visitor.root.get(name, {"type": "string"}) for name in sorted(required)}
    _refine_list_formats(variables)

    conflicts = list(visitor.conflicts)
    for lineno, root, attrs in visitor.printed:
        node = _lookup_path(visitor.root, root, attrs)
        node_type = node.get("type") if node else None
        path = ".".join([root, *attrs])
        # A path already reported above has the same root cause, so one warning is enough.
        if node_type not in ("object", "list") or path in visitor.conflict_paths:
            continue
        if node_type == "object":
            article, rendered = "an object", "{'field': ...}"
            fix = "print a single field, e.g. {{ " + path + ".field }}"
        else:
            article, rendered = "a list", "['item', ...]"
            fix = "loop over it with {% for item in " + path + " %}"
        conflicts.append(
            format_warning(
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
    return TemplateAnalysis(variables, list(dict.fromkeys(conflicts)))


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
