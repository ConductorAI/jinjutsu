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

    Returning the outcome lets analyze_jinja_template() call this once and hand the same result to the tree walk
    and the syntax check, which each need a different half of it.
    """
    try:
        return ParseResult(JINJA_ENV.parse(normalize_docxtpl_prefixes(text)), None)
    except TemplateSyntaxError as e:
        return ParseResult(None, e)


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


def warning_to_string(
    *,
    line_no: int,
    title: str,
    found: str,
    fix: str,
    reason: str | None = None,
    source_line: str | None = None,
) -> str:
    parts = [f"Line {line_no}: {title}", f"  Found: {found}", f"  Fix:   {fix}"]
    if reason:
        parts.append(f"  Reason: {reason}")
    if source_line:
        parts.append(f"  {source_line}")
    return "\n".join(parts)


def blank_comments(full_text: str) -> str:
    """
    Replace {# #} spans so commented-out tags are not read as template code.

    Line breaks are kept and every other character becomes a space, which leaves offsets and line
    numbers unchanged for the checks that report them.
    """
    return re.sub(r"\{#.*?#\}", lambda m: re.sub(r"[^\n]", " ", m.group()), full_text, flags=re.DOTALL)


def blank_string_literals(tag_text: str) -> str:
    "Blank out anything inside quotes, so a check does not flag words in a quoted string"
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
