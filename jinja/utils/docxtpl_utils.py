import re

# These docxtpl prefixes add row/cell/paragraph/run prefixes to Jinja tags to preserve format
# Example: {%tr for ... %} or {{r ... }}
DOCXTPL_TAG_PREFIX = r"(?:tr|tc|p|r)"

# These preserve formatting on docx tables
DOCXTPL_MERGE_TAG = r"\{%\s*(?:vm|hm)\s*%\}"
DOCXTPL_CELL_TAG = r"\{%\s*(?:colspan|cellbg)\s+([^%]*?)\s*%\}"


def normalize_docxtpl_prefixes(text: str) -> str:
    """Rewrite docxtpl's own tag syntax as vanilla Jinja so the parser accepts it"""
    text = re.sub(rf"(\{{[%{{])({DOCXTPL_TAG_PREFIX})(?=\s)", lambda m: m.group(1) + _blank(m.group(2)), text)
    text = re.sub(DOCXTPL_MERGE_TAG, lambda m: _blank(m.group()), text)
    return re.sub(DOCXTPL_CELL_TAG, _pad_cell_tag, text)


def _blank(text: str) -> str:
    """Replace every character with a space, keeping newlines so line numbers don't move"""
    return re.sub(r"[^\n]", " ", text)


def _pad_cell_tag(match: re.Match[str]) -> str:
    """Rewrite {% colspan n %} as {{ n }}, padded inside the braces back to the original width"""
    expression = match.group(1)
    newlines = "\n" * (match.group().count("\n") - expression.count("\n"))
    padding = len(match.group()) - len("{{  }}") - len(expression) - len(newlines)
    return "{{ " + expression + " " * padding + newlines + " }}"
