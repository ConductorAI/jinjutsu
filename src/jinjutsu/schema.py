from .types import ListNode, ObjectNode, UnknownNode, VariableNode

JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def context_schema(variables: dict[str, VariableNode]) -> dict:
    """A JSON Schema for the context object the template expects to be rendered with"""
    return {"$schema": JSON_SCHEMA_DRAFT, **_object_schema(variables)}


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
