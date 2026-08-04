"""
Jinja's own parse errors, rewritten in plainer words:
- Single '=' in a condition                    {% if a = 1 %}
- Unexpected '...' after the expression        {% if a b c %}
- Curly quote from Word                        {% if a == “x” %}
- Missing closing tag                          unexpected end of template
- Invalid variable name                        {{ a. }}
- Jinja could not parse this tag               anything we don't recognise
"""

import re

from jinja2 import TemplateSyntaxError

from ..diagnostic import Diagnostic
from ..utils.string_utils import read_source_line
from ..utils.tag_utils import TAG_SHAPE

BLOCK_BALANCE_ERROR = re.compile(r"unexpected end of template|unknown tag 'end\w+'", re.IGNORECASE)

# Jinja names the token it choked on, whether the tag prints a value or runs a statement
LEFTOVER_TOKEN = re.compile(r"expected token 'end of (?:statement block|print statement)', got '(.+?)'")
CURLY_QUOTE = re.compile(r"unexpected char '([“”‘’])'")
STRAIGHTENED = {"“": '"', "”": '"', "‘": "'", "’": "'"}

# A single '=' that is not part of ==, !=, <= or >=
LONE_EQUALS = re.compile(r"(?<![=!<>])=(?!=)")

# Block tags jinja closes with a matching end tag. 'set' only opens a block in its bodiless form,
# so {% set total = 0 %} is excluded by requiring no '=' before the tag closes
BLOCK_OPENERS = {
    "for": r"\{%-?\s*for\b",
    "if": r"\{%-?\s*if\b",
    "set": r"\{%-?\s*set\s+[^=%]*?-?%\}",
    "block": r"\{%-?\s*block\b",
    "macro": r"\{%-?\s*macro\b",
    "call": r"\{%-?\s*call\b",
    "filter": r"\{%-?\s*filter\b",
    "with": r"\{%-?\s*with\b",
    "raw": r"\{%-?\s*raw\b",
}


def check_jinja_syntax(lines: list[str], error: TemplateSyntaxError | None) -> list[Diagnostic]:
    """Replace jinja's own parsing errors in more readable language when we recognise the message"""
    if not error:
        return []

    error_msg = str(error)
    source_line = read_source_line(lines, error.lineno)
    tag = _tag_on(source_line)

    # The fix is the corrected tag wherever the correction is mechanical, and says what to do where it isn't,
    # so it is never a guess at what the author meant
    if leftover := LEFTOVER_TOKEN.search(error_msg):
        token = leftover.group(1)
        if token == "=":
            title = "Single '=' in a condition"
            fix = LONE_EQUALS.sub("==", tag, count=1)
        else:
            title = f"Unexpected '{token}' after the expression"
            fix = f"Remove '{token}'. Tags should only hold one expression"
    elif CURLY_QUOTE.search(error_msg):
        title = "Curly quote from Word"
        fix = tag.translate(str.maketrans(STRAIGHTENED))
    elif "unexpected end of template" in error_msg.lower():
        title = "Missing closing tag"
        keyword = _unclosed_block_keyword("\n".join(lines))
        fix = f"Add {{% end{keyword} %}} to close the {{% {keyword} %}} above" if keyword else "Close every block tag"
    elif "expected name or number" in error_msg.lower():
        title = "Invalid variable name"
        fix = "Use a plain name like {{ total }}, with no stray dots or symbols"
    else:
        title = "Jinja could not parse this tag"
        fix = "Check the tag for typos, missing quotes, or a missing operand"

    return [
        Diagnostic(
            line_no=error.lineno,
            title=title,
            found=tag,
            fix=fix,
            reason=f'Jinja stopped here with "{error_msg}", so the document never renders.',
            source_line=source_line,
        )
    ]


def should_defer_to_tag_counts(error: TemplateSyntaxError) -> bool:
    return bool(BLOCK_BALANCE_ERROR.search(str(error)))


def _tag_on(source_line: str) -> str:
    """The tag the author has to edit, picked off the line jinja blamed"""
    match = re.search(TAG_SHAPE, source_line, re.DOTALL)
    return match.group() if match else source_line.strip() or "this template"


def _unclosed_block_keyword(source: str) -> str | None:
    """Which kind of block was left open, so the fix can name the end tag the author is missing"""
    for keyword, opener in BLOCK_OPENERS.items():
        opened = len(re.findall(opener, source))
        closed = len(re.findall(rf"\{{%-?\s*end{keyword}\s*-?%\}}", source))
        if opened > closed:
            return keyword
    return None
