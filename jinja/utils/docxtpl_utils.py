import re

from jinja2 import Environment

JINJA_ENV = Environment()

# docxtpl adds row/cell/paragraph/run prefixes to Jinja tags, e.g. {%tr for ... %} or {{r ... }}
DOCXTPL_TAG_PREFIX = r"(?:tr|tc|p|r)"

DOCXTPL_MERGE_TAG = r"\{%\s*(?:vm|hm)\s*%\}"
DOCXTPL_CELL_TAG = r"\{%\s*(?:colspan|cellbg)\s+([^%]*?)\s*%\}"


def normalize_docxtpl_prefixes(text: str) -> str:
    """
    Rewrite docxtpl's own tag syntax as vanilla Jinja so the parser accepts it.

    Every rewrite keeps the character count and the newline positions of what it replaces, so a
    line number taken from the AST is a line number in the file the author uploaded. See README.md
    for which tags are rewritten and why the widths have to match.
    """
    text = re.sub(rf"(\{{[%{{])({DOCXTPL_TAG_PREFIX})(?=\s)", lambda m: m.group(1) + _blank(m.group(2)), text)
    text = re.sub(DOCXTPL_MERGE_TAG, lambda m: _blank(m.group()), text)
    return re.sub(DOCXTPL_CELL_TAG, _pad_cell_tag, text)


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
