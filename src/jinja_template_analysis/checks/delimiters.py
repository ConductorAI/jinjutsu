"""
Warnings:
- Extra space after '{' in tag                 { % if x %}
- Extra space before '}' in tag                {% if x % }
- Extra space after '{' in variable tag        { { amount }}
- Missing closing '}}' in variable tag         {{ amount }
- Missing closing '%}' in statement tag        {% if x }
- Misplaced '%' in statement tag               {if% if x %}
"""

import re

from ..utils.string_utils import warning_to_string
from ..utils.tag_utils import STATEMENT_KEYWORD, TemplateText


def check_malformed_tags(text: TemplateText) -> list[str]:
    warnings = []
    for line_num, (line, scanned) in enumerate(zip(text.lines, text.source_lines, strict=True), start=1):
        # Check for { % instead of {%
        if re.search(r"\{\s+%", scanned):
            match = re.search(r"\{\s+%.*?%\s*\}", scanned)
            if match:
                malformed_tag = match.group(0)
                warnings.append(
                    warning_to_string(
                        line_no=line_num,
                        title="Extra space after '{' in tag",
                        found=malformed_tag,
                        fix=malformed_tag.replace("{ ", "{").replace(" }", "}"),
                        source_line=line,
                    )
                )
        # Check for % } instead of %}
        elif re.search(r"%\s+\}", scanned):
            match = re.search(r"\{%.*?%\s+\}", scanned)
            if match:
                malformed_tag = match.group(0)
                warnings.append(
                    warning_to_string(
                        line_no=line_num,
                        title="Extra space before '}' in tag",
                        found=malformed_tag,
                        fix=malformed_tag.replace("{ ", "{").replace(" }", "}"),
                        source_line=line,
                    )
                )

        # Check for { { instead of {{
        if match := re.search(r"(?<!\{)\{\s+\{(?!\{).*?\}\s*\}", scanned):
            malformed_tag = match.group(0)
            warnings.append(
                warning_to_string(
                    line_no=line_num,
                    title="Extra space after '{' in variable tag",
                    found=malformed_tag,
                    fix=re.sub(r"\}\s+\}", "}}", re.sub(r"\{\s+\{", "{{", malformed_tag)),
                    reason="Jinja reads this as plain text, so the value never reaches the document.",
                    source_line=line,
                )
            )

        # Check for incomplete variable tags ({{ without }} or with only one })
        if match := re.search(r"\{\{[^}]*\}(?!\})", scanned):
            incomplete_tag = match.group(0)
            warnings.append(
                warning_to_string(
                    line_no=line_num,
                    title="Missing closing '}}' in variable tag",
                    found=incomplete_tag,
                    fix=incomplete_tag + "}",
                    source_line=line,
                )
            )

        # Check for incomplete statement tags ({% without %} or with only one %)
        if (
            re.search(r"\{%[^}]*(?<!%)(?<!%\s)\}(?!\})", scanned)
            and not re.search(r"\{%[^}]*%\}", scanned)
            and (match := re.search(r"\{%[^}]*\}", scanned))
        ):
            incomplete_tag = match.group(0)
            warnings.append(
                warning_to_string(
                    line_no=line_num,
                    title="Missing closing '%}' in statement tag",
                    found=incomplete_tag,
                    fix=incomplete_tag[:-1] + "%}",
                    source_line=line,
                )
            )

    return warnings


def check_misplaced_statement_delimiters(text: TemplateText) -> list[str]:
    """Check for statement tags whose opening '%' is missing or out of position, like '{if% x %}'"""
    warnings = []
    for line_num, (line, scanned) in enumerate(zip(text.lines, text.source_lines, strict=True), start=1):
        for match in re.finditer(r"\{(?![%{#])([^{}]*?)%\}", scanned):
            content = match.group(1)
            if not re.search(rf"\b(?:{STATEMENT_KEYWORD})\b", content):
                continue
            if re.match(r"\s*%", content):
                # '{ % if x %}' is the extra-space case, already reported by check_malformed_tags
                continue
            warnings.append(
                warning_to_string(
                    line_no=line_num,
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
