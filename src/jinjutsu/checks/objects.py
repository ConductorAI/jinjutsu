"""
We typically don't want to print object directly, since they render as {'header': {'title': 'X'}}

Warnings:
- '...' is an object and can't be printed directly   {{ case }} where the template also reads case.title
- '...' is a list and can't be printed directly      {{ rows }} where the template also reads row.name
"""

from ..types import ListNode, ObjectNode, VariableNode, WalkResult, child_properties
from ..utils.string_utils import warning_to_string


def check_no_objects_printed_directly(walked: WalkResult) -> list[str]:
    warnings = []
    for lineno, root, attrs in walked.printed:
        node = _lookup_path(walked.root, root, attrs)
        path = ".".join([root, *attrs])
        # Already reported as a clash, so one warning is enough
        if path in walked.conflict_paths:
            continue
        if isinstance(node, ObjectNode):
            article, rendered = "an object", "{'field': ...}"
            fix = "Print a single field, e.g. {{ " + path + ".field }}"
        elif isinstance(node, ListNode):
            article, rendered = "a list", "['item', ...]"
            fix = "Loop over it with {% for item in " + path + " %}"
        else:
            continue
        warnings.append(
            warning_to_string(
                line_no=lineno,
                title=f"'{path}' is {article} and can't be printed directly",
                found="{{ " + path + " }}",
                fix=fix,
                reason=(
                    f"The template also reads fields from '{path}', so it receives {article}. "
                    f"Printing it renders {rendered} into the document."
                ),
            )
        )
    return warnings


def _lookup_path(tree: dict[str, VariableNode], root: str, attrs: list[str]) -> VariableNode | None:
    node = tree.get(root)
    for segment in attrs:
        if node is None:
            return None
        node = child_properties(node).get(segment)
    return node
