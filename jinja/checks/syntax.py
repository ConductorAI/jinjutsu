"""
Warnings:
- Mismatched loop tags                         {% for %} and {% endfor %} counts differ
- Mismatched conditional tags                  {% if %} and {% endif %} counts differ

Jinja's own parse errors, rewritten for readability:
- Use '==' to compare                          {% if a = 1 %}
- Unexpected '...' after the expression        {% if a b c %}
- '...' is a curly quote                       {% if a == “x” %}
- Missing closing tag like '{% endfor %}'      unexpected end of template
- Invalid variable name in '{{ }}' or '{% %}'  {{ a. }}
- Check for typos or formatting issues         anything we do not recognise
"""

import re

from ..jinja_utils import DOCXTPL_TAG_PREFIX, ParseResult, blank_comments

_BLOCK_BALANCE_ERROR = re.compile(r"unexpected end of template|unknown tag 'end\w+'", re.IGNORECASE)


def check_mismatched_tags(full_text: str) -> list[str]:
    warnings = []
    full_text = blank_comments(full_text)

    for_count = len(re.findall(rf"\{{%-?{DOCXTPL_TAG_PREFIX}?\s*for\s+", full_text))
    endfor_count = len(re.findall(rf"\{{%-?{DOCXTPL_TAG_PREFIX}?\s*endfor\s*-?%\}}", full_text))
    if for_count != endfor_count:
        warnings.append(
            _tag_count(
                title="Mismatched loop tags",
                found=f"{for_count} {{% for %}} tag(s) but {endfor_count} {{% endfor %}} tag(s)",
                fix="Each {% for %} must have a corresponding {% endfor %}",
            )
        )

    if_count = len(re.findall(rf"\{{%-?{DOCXTPL_TAG_PREFIX}?\s*if\s+", full_text))
    endif_count = len(re.findall(rf"\{{%-?{DOCXTPL_TAG_PREFIX}?\s*endif\s*-?%\}}", full_text))
    if if_count != endif_count:
        warnings.append(
            _tag_count(
                title="Mismatched conditional tags",
                found=f"{if_count} {{% if %}} tag(s) but {endif_count} {{% endif %}} tag(s)",
                fix="Each {% if %} must have a corresponding {% endif %}",
            )
        )

    return warnings


def check_jinja_syntax(full_text: str, parsed: ParseResult, *, blocks_already_counted: bool) -> list[str]:
    """
    Report Jinja's own parse error, in plainer words when we recognise the message.

    blocks_already_counted drops the error when it only repeats an imbalance check_mismatched_tags
    has already counted. Every other error Jinja raises is reported, even alongside other warnings.
    """
    warnings = []

    if e := parsed.error:
        error_msg = str(e)
        if blocks_already_counted and _BLOCK_BALANCE_ERROR.search(error_msg):
            return []
        source_line = None

        if e.lineno:
            lines = full_text.split("\n")
            if 0 < e.lineno <= len(lines):
                source_line = lines[e.lineno - 1]

        if leftover := re.search(r"expected token 'end of statement block', got '(.+?)'", error_msg):
            token = leftover.group(1)
            if token == "=":
                guidance = "Use '==' to compare. A single '=' only assigns, and only in '{% set %}'"
            else:
                guidance = f"Unexpected '{token}' after the expression. The tag holds one expression, nothing more"
        elif curly := re.search(r"unexpected char '([“”‘’])'", error_msg):
            guidance = (
                f"'{curly.group(1)}' is a curly quote, which Word substitutes as you type. "
                f"Replace it with a straight ' or \""
            )
        elif "unexpected end of template" in error_msg.lower():
            guidance = "Missing closing tag like '{% endfor %}' or '{% endif %}'"
        elif "expected name or number" in error_msg.lower():
            guidance = "Invalid variable name in '{{ }}' or '{% %}' tag"
        else:
            guidance = "Check for typos or formatting issues"

        warnings.append(
            _syntax_error(
                title=guidance,
                line=e.lineno,
                error=error_msg,
                source_line=source_line,
            )
        )

    return warnings


def _tag_count(*, title: str, found: str, fix: str) -> str:
    return f"{title}\n  Found: {found}\n  Fix: {fix}"


def _syntax_error(*, title: str, error: str, line: int | None, source_line: str | None) -> str:
    # A blank source_line still means Jinja pointed at a real line, so it keeps the heading
    if line and source_line is not None:
        return f"Line {line}: {title}\n  {source_line}\n  Error: {error}"
    return f"Jinja2 syntax error: {title}\n  Error: {error}"
