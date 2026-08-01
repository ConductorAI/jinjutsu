"""
The JSON Schema a report carries: built from the node union, and rendered as the tree the CLI prints
"""

from .types import ListNode, ObjectNode, UnknownNode, VariableNode

JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
TYPE_GAP = 2  # Spaces between the longest label and the type column


def context_schema(variables: dict[str, VariableNode]) -> dict:
    """A JSON Schema for the context object the template expects to be rendered with"""
    return {"$schema": JSON_SCHEMA_DRAFT, **_object_schema(variables)}


def render_tree(properties: dict[str, dict]) -> list[str]:
    """One line per name, with the types aligned past the longest label"""
    rows = _tree_rows(properties, None)
    width = max((len(label) for label, _ in rows), default=0) + TYPE_GAP
    return [f"{label.ljust(width)}{type_label}" for label, type_label in rows]


def _tree_rows(properties: dict[str, dict], prefix: str | None) -> list[tuple[str, str]]:
    """`prefix` is None at the roots, which are flush left and take no connector"""
    rows = []
    last_index = len(properties) - 1
    for index, (name, node) in enumerate(properties.items()):
        is_last = index == last_index
        rows.append((name if prefix is None else f"{prefix}{'`-- ' if is_last else '|-- '}{name}", _type_label(node)))
        if children := _child_properties(node):
            rows.extend(_tree_rows(children, "" if prefix is None else prefix + ("    " if is_last else "|   ")))
    return rows


def _object_schema(properties: dict[str, VariableNode]) -> dict:
    # No `required` key, which in JSON Schema means nothing is required. Whether a name may be absent
    # is a property of each place it is used, not of the name, so one flag per name cannot answer it
    return {
        "type": "object",
        "properties": {name: _node_schema(node) for name, node in properties.items()},
    }


def _node_schema(node: VariableNode) -> dict:
    if isinstance(node, ObjectNode):
        return _object_schema(node.properties)
    if isinstance(node, ListNode):
        return {"type": "array", "items": _node_schema(node.items)}
    if isinstance(node, UnknownNode):
        # Nothing says what shape this takes, and a value with no evidence is usually rendered as text
        return {"type": "string"}
    return {"type": node.kind}


def _type_label(node: dict) -> str:
    """The type as the README writes it, where a list also says what one element looks like"""
    if node.get("type") != "array":
        return node.get("type", "unknown")
    item_type = node["items"].get("type", "unknown")
    return "list of lists" if item_type == "array" else f"list of {item_type}s"


def _child_properties(node: dict) -> dict[str, dict]:
    if node.get("type") == "object":
        return node["properties"]
    if node.get("type") == "array":
        return _child_properties(node["items"])
    return {}
