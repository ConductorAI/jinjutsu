import re
from enum import Enum, auto

from jinja2 import Environment, nodes

JINJA_ENV = Environment()

# docxtpl adds row/cell/paragraph/run prefixes to Jinja tags, e.g. {%tr for ... %} or {{r ... }}
DOCXTPL_TAG_PREFIX = r"(?:tr|tc|p|r)"


class PathSegment(Enum):
    """Segment of a name path that is not a property name."""

    LIST_INDEX = auto()


# A property name, or a marker for a list subscript such as the [0] in items[0].name
NamePathSegment = str | PathSegment


def normalize_docxtpl_prefixes(text: str) -> str:
    """Strip docxtpl row/cell/paragraph/run prefixes so vanilla Jinja can parse the tags."""
    return re.sub(rf"(\{{[%{{]){DOCXTPL_TAG_PREFIX}?\s+", r"\1 ", text)


def parse_template(text: str) -> nodes.Template:
    """Normalize docxtpl prefixes and parse the template into a Jinja AST.

    Raises TemplateSyntaxError if the template is malformed. Only prefixes are stripped, so
    line numbers still map back to the original text.
    """
    return JINJA_ENV.parse(normalize_docxtpl_prefixes(text))


def name_path(node: nodes.Node) -> tuple[str, list[NamePathSegment]] | None:
    """
    Resolve a Name / Getattr / constant Getitem chain to (root_name, path_segments), else None.

    A string subscript is a property name, so r['items'] resolves the same as r.items. An integer
    subscript is a list index, yielding PathSegment.LIST_INDEX. Non-constant subscripts like
    items[i] return None.
    """
    segments: list[NamePathSegment] = []
    current = node
    while True:
        if isinstance(current, nodes.Getattr):
            segments.append(current.attr)
            current = current.node
        elif isinstance(current, nodes.Getitem) and isinstance(current.arg, nodes.Const):
            value = current.arg.value
            if isinstance(value, str):
                segments.append(value)
            elif isinstance(value, int):
                segments.append(PathSegment.LIST_INDEX)
            else:
                return None
            current = current.node
        else:
            break
    if isinstance(current, nodes.Name):
        return current.name, list(reversed(segments))
    return None


def unwrap_filters(node: nodes.Node) -> nodes.Node:
    """Strip filter applications from an expression, so `items | sort | unique` yields `items`."""
    while isinstance(node, nodes.Filter) and node.node:
        node = node.node
    return node


def target_names(target: nodes.Node) -> list[str]:
    """Names bound by a for-loop target or set assignment (handles tuple unpacking)."""
    if isinstance(target, nodes.Name):
        return [target.name]
    if isinstance(target, nodes.Tuple):
        return [item.name for item in target.items if isinstance(item, nodes.Name)]
    return []
