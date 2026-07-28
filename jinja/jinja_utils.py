import re

from jinja2 import Environment, nodes

JINJA_ENV = Environment()

# docxtpl adds row/cell/paragraph/run prefixes to Jinja tags, e.g. {%tr for ... %} or {{r ... }}
DOCXTPL_TAG_PREFIX = r"(?:tr|tc|p|r)"

_DOCXTPL_MERGE_TAG = r"\{%\s*(?:vm|hm)\s*%\}"
_DOCXTPL_CELL_TAG = r"\{%\s*(?:colspan|cellbg)\s+([^%]*?)\s*%\}"

# A property name, or a list subscript such as the 0 in items[0].name
NamePathSegment = str | int


def format_warning(
    *,
    line_no: int,
    title: str,
    found: str,
    fix: str,
    reason: str | None = None,
    source_line: str | None = None,
) -> str:
    """
    Render one template warning in the shared Line / Found / Fix / Reason layout.

    Every field is plain data, so callers write Jinja snippets literally instead of escaping
    braces past an f-string.
    """
    parts = [f"Line {line_no}: {title}", f"  Found: {found}", f"  Fix:   {fix}"]
    if reason:
        parts.append(f"  Reason: {reason}")
    if source_line:
        parts.append(f"  {source_line}")
    return "\n".join(parts)


def normalize_docxtpl_prefixes(text: str) -> str:
    """
    Rewrite docxtpl's own tag syntax as vanilla Jinja so the parser accepts it.

    Strips the row/cell/paragraph/run prefixes, drops the {% vm %} and {% hm %} cell merges, and
    rewrites {% colspan n %} and {% cellbg c %} to {{ n }} and {{ c }}, the substitution docxtpl
    itself performs.
    """
    text = re.sub(rf"(\{{[%{{]){DOCXTPL_TAG_PREFIX}?\s+", r"\1 ", text)
    text = re.sub(_DOCXTPL_MERGE_TAG, "", text)
    return re.sub(_DOCXTPL_CELL_TAG, r"{{ \1 }}", text)


def parse_template(text: str) -> nodes.Template:
    """Normalize docxtpl prefixes and parse the template into a Jinja AST.

    Raises TemplateSyntaxError if the template is malformed.
    """
    return JINJA_ENV.parse(normalize_docxtpl_prefixes(text))


def name_path(node: nodes.Node) -> tuple[str, list[NamePathSegment]] | None:
    """
    Reduce a Name / Getattr / constant Getitem chain to (root_name, path_segments), else None.

    A string subscript is a property name, so r['items'] resolves the same as r.items
    An integer subscript is a list index, kept as the int itself
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
    "Handles tuple unpacking and set assignments"
    if isinstance(target, nodes.Name):
        return [target.name]
    if isinstance(target, nodes.Tuple):
        return [item.name for item in target.items if isinstance(item, nodes.Name)]
    return []
