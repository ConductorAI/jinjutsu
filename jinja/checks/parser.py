"""
Jinja's own parse errors, rewritten in plainer words:
- Use '==' to compare                          {% if a = 1 %}
- Unexpected '...' after the expression        {% if a b c %}
- '...' is a curly quote                       {% if a == “x” %}
- Missing closing tag like '{% endfor %}'      unexpected end of template
- Invalid variable name in '{{ }}' or '{% %}'  {{ a. }}
- Check for typos or formatting issues         anything we don't recognise
"""

import re

from jinja2 import TemplateSyntaxError

BLOCK_BALANCE_ERROR = re.compile(r"unexpected end of template|unknown tag 'end\w+'", re.IGNORECASE)


def check_jinja_syntax(lines: list[str], error: TemplateSyntaxError | None) -> list[str]:
    """Replace jinja's own parsing errors in more readable language when we recognise the message"""
    warnings = []

    if e := error:
        error_msg = str(e)
        source_line = None

        if e.lineno:
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


def should_defer_to_tag_counts(error: TemplateSyntaxError) -> bool:
    return bool(BLOCK_BALANCE_ERROR.search(str(error)))


def _syntax_error(*, title: str, error: str, line: int | None, source_line: str | None) -> str:
    if line and source_line is not None:
        return f"Line {line}: {title}\n  {source_line}\n  Error: {error}"
    return f"Jinja2 syntax error: {title}\n  Error: {error}"
