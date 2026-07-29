import re
from typing import NamedTuple

from jinja2 import Environment, TemplateSyntaxError, nodes

JINJA_ENV = Environment()

# docxtpl adds row/cell/paragraph/run prefixes to Jinja tags, e.g. {%tr for ... %} or {{r ... }}
DOCXTPL_TAG_PREFIX = r"(?:tr|tc|p|r)"

_DOCXTPL_MERGE_TAG = r"\{%\s*(?:vm|hm)\s*%\}"
_DOCXTPL_CELL_TAG = r"\{%\s*(?:colspan|cellbg)\s+([^%]*?)\s*%\}"

# A property name, or a list subscript such as the 0 in items[0].name
NamePathSegment = str | int


class ParseResult(NamedTuple):
    """Exactly one of these is set: a template either parses or it does not."""

    ast: nodes.Template | None
    error: TemplateSyntaxError | None


def normalize_docxtpl_prefixes(text: str) -> str:
    """
    Rewrite docxtpl's own tag syntax as vanilla Jinja so the parser accepts it.

    Every rewrite keeps the character count and the newline positions of what it replaces, so a
    line number taken from the AST is a line number in the file the author uploaded. See README.md
    for which tags are rewritten and why the widths have to match.
    """
    text = re.sub(rf"(\{{[%{{])({DOCXTPL_TAG_PREFIX})(?=\s)", lambda m: m.group(1) + _blank(m.group(2)), text)
    text = re.sub(_DOCXTPL_MERGE_TAG, lambda m: _blank(m.group()), text)
    return re.sub(_DOCXTPL_CELL_TAG, _pad_cell_tag, text)


def parse_result(text: str) -> ParseResult:
    """
    Normalize docxtpl prefixes and parse the template, reporting failure instead of raising.

    Returning the outcome lets analyze() call this once and hand the same result to the tree walk
    and the syntax check, which each need a different half of it.
    """
    try:
        return ParseResult(JINJA_ENV.parse(normalize_docxtpl_prefixes(text)), None)
    except TemplateSyntaxError as e:
        return ParseResult(None, e)


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


def blank_comments(full_text: str) -> str:
    """
    Replace {# #} spans so commented-out tags are not read as template code.

    Line breaks are kept and every other character becomes a space, which leaves offsets and line
    numbers unchanged for the checks that report them.
    """
    return re.sub(r"\{#.*?#\}", lambda m: re.sub(r"[^\n]", " ", m.group()), full_text, flags=re.DOTALL)


def blank_string_literals(tag_text: str) -> str:
    "Replace the contents of quoted literals so validation regex doesn't run on them"
    return re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", lambda m: " " * len(m.group()), tag_text)


def _blank(text: str) -> str:
    "Replace every character with a space, keeping newlines so line numbers do not move"
    return re.sub(r"[^\n]", " ", text)


def _pad_cell_tag(match: re.Match[str]) -> str:
    """
    Rewrite {% colspan n %} as {{ n }}, padded inside the braces back to the original width.

    The shortest form the pattern can match is {%colspan n %}, which leaves room for the padding.
    """
    expression = match.group(1)
    padding = len(match.group()) - len("{{  }}") - len(expression)
    return "{{ " + expression + " " * padding + " }}"
