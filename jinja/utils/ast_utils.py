from jinja2 import nodes

# A property name, or a list subscript such as the 0 in items[0].name
NamePathSegment = str | int


def name_path(node: nodes.Node) -> tuple[str, list[NamePathSegment]] | None:
    """
    Split a dotted path like case.header.title into its first name and the steps after it.

    Returns None for anything that is not a plain path, such as a function call or arithmetic.
    A quoted subscript is a field name, so r['items'] reads the same as r.items. A number is a
    list position and is kept as a number, so items[0] and items.0 both mean the first element.
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


def unwrap_filters(node: nodes.Node) -> nodes.Node:
    "Strip filter applications from an expression, so `items | sort | unique` yields `items`"
    while isinstance(node, nodes.Filter) and node.node:
        node = node.node
    return node


def target_names(target: nodes.Node) -> list[str]:
    "The names a template invents, like the x in {% for x in items %} or {% set x = 1 %}"
    if isinstance(target, nodes.Name):
        return [target.name]
    if isinstance(target, nodes.Tuple):
        return [item.name for item in target.items if isinstance(item, nodes.Name)]
    return []
