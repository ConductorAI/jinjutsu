"""
Jinja's own parse errors, rewritten in plainer words:
- Use '==' to compare                          {% if a = 1 %}
- Unexpected '...' after the expression        {% if a b c %}
- '...' is a curly quote                       {% if a == “x” %}
- Missing closing tag like '{% endfor %}'      unexpected end of template
- Invalid variable name in '{{ }}' or '{% %}'  {{ a. }}
- Check for typos or formatting issues         anything we do not recognise
"""

import re

from jinja2 import TemplateSyntaxError

BLOCK_BALANCE_ERROR = re.compile(r"unexpected end of template|unknown tag 'end\w+'", re.IGNORECASE)


def check_jinja_syntax(full_text: str, error: TemplateSyntaxError | None, *, blocks_already_counted: bool) -> list[str]:
    """
    Report Jinja's own parse error, in plainer words when we recognise the message.

    blocks_already_counted drops the error when it only repeats an imbalance check_mismatched_tags
    has already counted. Every other error Jinja raises is reported, even alongside other warnings.
    """
    warnings = []

    if e := error:
        error_msg = str(e)
        if blocks_already_counted and BLOCK_BALANCE_ERROR.search(error_msg):
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


def _syntax_error(*, title: str, error: str, line: int | None, source_line: str | None) -> str:
    # A blank source_line still means Jinja pointed at a real line, so it keeps the heading
    if line and source_line is not None:
        return f"Line {line}: {title}\n  {source_line}\n  Error: {error}"
    return f"Jinja2 syntax error: {title}\n  Error: {error}"
