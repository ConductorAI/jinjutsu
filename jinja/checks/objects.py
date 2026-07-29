"""
Warnings:
- '...' is an object and cannot be printed directly   {{ case }} where the template also reads case.title
- '...' is a list and cannot be printed directly     {{ rows }} where the template also reads row.name
"""

from ..utils.string_utils import warning_to_string
from ..variable_tree import VariableNode, VariableTreeVisitor


def check_no_objects_printed_directly(visitor: VariableTreeVisitor) -> list[str]:
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
                title=f"'{path}' is {article} and cannot be printed directly",
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
