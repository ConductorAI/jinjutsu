import re
from collections.abc import Iterator

from .string_utils import replace_comments_with_spaces


def find_tags(full_text: str) -> Iterator[tuple[int, str, str]]:
    """
    Yield (line number, source line, tag text) for every Jinja tag, in document order.

    Word puts a paragraph break wherever the author pressed Enter, so a tag can arrive split over
    two lines. docxtpl rejoins those before rendering, which makes them valid templates that a
    line-scoped regex would never see. Matching over the whole text keeps them visible, with the
    newlines folded out so the tag reads as one line in the warning.

    A tag body stops at the next opening delimiter, so an unclosed '{{' runs out rather than
    swallowing the prose between it and whatever '}}' comes next.
    """
    lines = full_text.split("\n")
    for match in re.finditer(r"\{[%{](?:(?!\{[%{]).)*?[%}]\}", replace_comments_with_spaces(full_text), re.DOTALL):
        line_no = full_text.count("\n", 0, match.start()) + 1
        yield line_no, lines[line_no - 1], re.sub(r"\s*\n\s*", " ", match.group())
