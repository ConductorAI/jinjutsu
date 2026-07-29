import re
from collections.abc import Iterator
from typing import NamedTuple

from .docxtpl_utils import DOCXTPL_TAG_PREFIX
from .string_utils import replace_comments_with_spaces

# A whole tag, {{ }} or {% %}, stopping at the next opening delimiter so an unclosed one runs out
TAG_SHAPE = r"\{[%{](?:(?!\{[%{]).)*?[%}]\}"

STATEMENT_KEYWORD = r"if|elif|else|endif|for|endfor|set|endset"

# Line number, the line as the author wrote it, and the tag itself folded onto one line
Tag = tuple[int, str, str]


class TemplateText(NamedTuple):
    """
    Every view of the template the checks need, derived once instead of once per check

    Checks match against `source` and `source_lines`, where comments are blanked out
    They quote `lines` back to the author, so a warning shows what they actually wrote
    """

    lines: list[str]
    source: str
    source_lines: list[str]
    tags: list[Tag]


def read_template(full_text: str) -> TemplateText:
    source = replace_comments_with_spaces(full_text)
    lines = full_text.split("\n")
    return TemplateText(lines, source, source.split("\n"), list(_find_tags(source, lines)))


def statement_opening(keywords: str) -> str:
    """Regex for a block-opening tag such as {% for %} or {%tr if %}, which is followed by an expression"""
    return rf"\{{%-?{DOCXTPL_TAG_PREFIX}?\s*({keywords})\s+"


def statement_closing(keywords: str) -> str:
    """Regex for a complete end tag such as {% endfor %} or {%- endif -%}, which takes no expression"""
    return rf"\{{%-?{DOCXTPL_TAG_PREFIX}?\s*({keywords})\s*-?%\}}"


def statement_keyword(keywords: str) -> str:
    """Regex reading the keyword off a tag find_tags already extracted, so the tag shape is known good"""
    return rf"\{{%-?\s*{DOCXTPL_TAG_PREFIX}?\s*({keywords})\b"


def _find_tags(source: str, lines: list[str]) -> Iterator[Tag]:
    """Yield every jinja tag in the template. A tag can span multiple lines"""
    for match in re.finditer(TAG_SHAPE, source, re.DOTALL):
        line_no = source.count("\n", 0, match.start()) + 1
        yield line_no, lines[line_no - 1], re.sub(r"\s*\n\s*", " ", match.group())
