import re
from collections.abc import Iterator

from .docxtpl_utils import DOCXTPL_TAG_PREFIX
from .string_utils import replace_comments_with_spaces

# A whole tag, {{ }} or {% %}, stopping at the next opening delimiter so an unclosed one runs out
TAG_SHAPE = r"\{[%{](?:(?!\{[%{]).)*?[%}]\}"

STATEMENT_KEYWORD = r"if|elif|else|endif|for|endfor|set|endset"


def statement_opening(keywords: str) -> str:
    """Regex for a block-opening tag such as {% for %} or {%tr if %}, which is followed by an expression"""
    return rf"\{{%-?{DOCXTPL_TAG_PREFIX}?\s*({keywords})\s+"


def statement_closing(keywords: str) -> str:
    """Regex for a complete end tag such as {% endfor %} or {%- endif -%}, which takes no expression"""
    return rf"\{{%-?{DOCXTPL_TAG_PREFIX}?\s*({keywords})\s*-?%\}}"


def statement_keyword(keywords: str) -> str:
    """Regex reading the keyword off a tag find_tags already extracted, so the tag shape is known good"""
    return rf"\{{%-?\s*{DOCXTPL_TAG_PREFIX}?\s*({keywords})\b"


def find_tags(full_text: str) -> Iterator[tuple[int, str, str]]:
    """Generator that yields a list of jinja tags. These can be across multiple lines"""
    lines = full_text.split("\n")
    for match in re.finditer(TAG_SHAPE, replace_comments_with_spaces(full_text), re.DOTALL):
        line_no = full_text.count("\n", 0, match.start()) + 1
        yield line_no, lines[line_no - 1], re.sub(r"\s*\n\s*", " ", match.group())
