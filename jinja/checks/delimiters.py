"""
Tags whose delimiters are broken, so Jinja never sees them as tags at all.

These work a line at a time rather than through iter_tags, because that helper matches a
well-formed pair of delimiters and these are the tags missing theirs. README.md notes the
coverage gap that follows: a broken tag split across a newline is not reported.
"""

import re

from ..diagnostics import Diagnostic, Layout

_JINJA_STATEMENT_KEYWORD = r"(?:if|elif|else|endif|for|endfor|set|endset)"
# How Jinja words an unbalanced block, either too few end tags or one too many


def check_malformed_tags(lines: list[str]) -> list[Diagnostic]:
    """Check for malformed Jinja2 tags with extra spaces or missing braces."""
    warnings = []
    for line_num, line in enumerate(lines, start=1):
        # Check for { % instead of {%
        if re.search(r"\{\s+%", line):
            match = re.search(r"\{\s+%.*?%\s*\}", line)
            if match:
                malformed_tag = match.group(0)
                warnings.append(
                    Diagnostic(
                        code="malformed-tag",
                        layout=Layout.DETAIL,
                        line=line_num,
                        title="Extra space after '{' in tag",
                        found=malformed_tag,
                        fix=malformed_tag.replace("{ ", "{").replace(" }", "}"),
                        source_line=line,
                    )
                )
        # Check for % } instead of %}
        elif re.search(r"%\s+\}", line) and not re.search(r"\{\s+%", line):
            match = re.search(r"\{%.*?%\s+\}", line)
            if match:
                malformed_tag = match.group(0)
                warnings.append(
                    Diagnostic(
                        code="malformed-tag",
                        layout=Layout.DETAIL,
                        line=line_num,
                        title="Extra space before '}' in tag",
                        found=malformed_tag,
                        fix=malformed_tag.replace("{ ", "{").replace(" }", "}"),
                        source_line=line,
                    )
                )

        # Check for { { instead of {{
        if match := re.search(r"(?<!\{)\{\s+\{(?!\{).*?\}\s*\}", line):
            malformed_tag = match.group(0)
            warnings.append(
                Diagnostic(
                    code="malformed-tag",
                    layout=Layout.DETAIL,
                    line=line_num,
                    title="Extra space after '{' in variable tag",
                    found=malformed_tag,
                    fix=re.sub(r"\}\s+\}", "}}", re.sub(r"\{\s+\{", "{{", malformed_tag)),
                    reason="Jinja reads this as plain text, so the value never reaches the document.",
                    source_line=line,
                )
            )

        # Check for incomplete variable tags ({{ without }} or with only one })
        if match := re.search(r"\{\{[^}]*\}(?!\})", line):
            incomplete_tag = match.group(0)
            warnings.append(
                Diagnostic(
                    code="malformed-tag",
                    layout=Layout.DETAIL,
                    line=line_num,
                    title="Missing closing '}}' in variable tag",
                    found=incomplete_tag,
                    fix=incomplete_tag + "}",
                    source_line=line,
                )
            )

        # Check for incomplete statement tags ({% without %} or with only one %)
        if (
            re.search(r"\{%[^}]*(?<!%)(?<!%\s)\}(?!\})", line)
            and not re.search(r"\{%[^}]*%\}", line)
            and (match := re.search(r"\{%[^}]*\}", line))
        ):
            incomplete_tag = match.group(0)
            warnings.append(
                Diagnostic(
                    code="malformed-tag",
                    layout=Layout.DETAIL,
                    line=line_num,
                    title="Missing closing '%}' in statement tag",
                    found=incomplete_tag,
                    fix=incomplete_tag[:-1] + "%}",
                    source_line=line,
                )
            )

    return warnings


def check_misplaced_statement_delimiters(lines: list[str]) -> list[Diagnostic]:
    """
    Check for statement tags whose opening '%' is missing or out of position, e.g. '{if% x %}'.

    Jinja cannot report these: without a leading '{%' the tag lexes as literal text, so the only
    error it raises is an unmatched end tag further down the template.
    """
    warnings = []
    for line_num, line in enumerate(lines, start=1):
        for match in re.finditer(r"\{(?![%{#])([^{}]*?)%\}", line):
            content = match.group(1)
            if not re.search(rf"\b{_JINJA_STATEMENT_KEYWORD}\b", content):
                continue
            if re.match(r"\s*%", content):
                # '{ % if x %}' is the extra-space case, already reported by check_malformed_tags
                continue
            warnings.append(
                Diagnostic(
                    code="misplaced-delimiter",
                    layout=Layout.DETAIL,
                    line=line_num,
                    title="Misplaced '%' in statement tag",
                    found=match.group(0),
                    fix="{% " + content.replace("%", "").strip() + " %}",
                    reason=(
                        "A statement tag must open with '{%'. Jinja reads this as plain text, so "
                        "its matching end tag will be reported as an error elsewhere."
                    ),
                    source_line=line,
                )
            )
    return warnings
