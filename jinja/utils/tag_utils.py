import re
from collections.abc import Iterator

from .string_utils import replace_comments_with_spaces


def find_tags(full_text: str) -> Iterator[tuple[int, str, str]]:
    """Generator that yields a list of jinja tags. These can be across multiple lines"""
    lines = full_text.split("\n")
    for match in re.finditer(r"\{[%{](?:(?!\{[%{]).)*?[%}]\}", replace_comments_with_spaces(full_text), re.DOTALL):
        line_no = full_text.count("\n", 0, match.start()) + 1
        yield line_no, lines[line_no - 1], re.sub(r"\s*\n\s*", " ", match.group())
