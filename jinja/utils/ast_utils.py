from jinja2 import nodes

# A property name, or a list subscript such as the 0 in items[0].name
NamePathSegment = str | int


def split_ast_object_path(node: nodes.Node) -> tuple[str, list[NamePathSegment]] | None:
    """
    Splits a detected object into a root and list of path segments

    case.header.title  ->  ("case", ["header", "title"])
    amount             ->  ("amount", [])
    r['items']         ->  ("r", ["items"])        quoted key is a field, same as r.items
    items[0].name      ->  ("items", [0, "name"])  number is a list position, kept as int
    items.0.name       ->  ("items", [0, "name"])  same path, Jinja's other spelling
    """
    segments: list[NamePathSegment] = []
    current = node
    while True:
        if isinstance(current, nodes.Getattr):
            segments.append(current.attr)
            current = current.node
        elif isinstance(current, nodes.Getitem) and isinstance(current.arg, nodes.Const):
            value = current.arg.value
            if not isinstance(value, (str, int)):
                return None
            segments.append(value)
            current = current.node
        else:
            break
    if isinstance(current, nodes.Name):
        return current.name, list(reversed(segments))
    return None


def strip_list_operations(node: nodes.Node) -> nodes.Node:
    """Strip list operations from an expression, so `variable | sort | unique` yields `variable`"""
    while isinstance(node, nodes.Filter) and node.node:
        node = node.node
    return node


def jinja_local_variables(target: nodes.Node) -> list[str]:
    """Find local variables a template invents, like the x in {% for x in items %} or {% set x = 1 %}"""
    if isinstance(target, nodes.Name):
        return [target.name]
    if isinstance(target, nodes.Tuple):
        return [item.name for item in target.items if isinstance(item, nodes.Name)]
    return []
