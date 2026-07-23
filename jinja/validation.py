import re

from jinja2 import TemplateSyntaxError

from .jinja_utils import DOCXTPL_TAG_PREFIX, parse_template


def validate_template_jinja(full_text: str) -> list[str]:
    """
    Validate Jinja2 syntax in a docx template.

    Returns:
        List of warning messages describing any malformed Jinja2 syntax.
        Empty list if template is valid.
    """
    lines = full_text.split("\n")

    warnings = []
    warnings.extend(_check_malformed_tags(lines))
    warnings.extend(_check_mismatched_tags(full_text))

    if not warnings:
        # Only use jinja checker only if the checker we wrote didn't pick up any issues
        # If we use both checkers there will be duplicate errors
        # The jinja checker error messages are not as easy to read as the ones we emit from our custom checks
        warnings.extend(_check_jinja_syntax(full_text))
    return warnings


def _check_malformed_tags(lines: list[str]) -> list[str]:
    """Check for malformed Jinja2 tags with extra spaces or missing braces."""
    warnings = []
    for line_num, line in enumerate(lines, start=1):
        # Check for { % instead of {%
        if re.search(r"\{\s+%", line):
            match = re.search(r"\{\s+%.*?%\s*\}", line)
            if match:
                malformed_tag = match.group(0)
                fixed_tag = malformed_tag.replace("{ ", "{").replace(" }", "}")
                warnings.append(
                    f"Line {line_num}: Extra space after '{{' in tag\n"
                    f"  Found: {malformed_tag}\n"
                    f"  Fix:   {fixed_tag}\n"
                    f"  {line}"
                )
        # Check for % } instead of %}
        elif re.search(r"%\s+\}", line) and not re.search(r"\{\s+%", line):
            match = re.search(r"\{%.*?%\s+\}", line)
            if match:
                malformed_tag = match.group(0)
                fixed_tag = malformed_tag.replace("{ ", "{").replace(" }", "}")
                warnings.append(
                    f"Line {line_num}: Extra space before '}}' in tag\n"
                    f"  Found: {malformed_tag}\n"
                    f"  Fix:   {fixed_tag}\n"
                    f"  {line}"
                )

        # Check for incomplete variable tags ({{ without }} or with only one })
        if re.search(r"\{\{[^}]*\}(?!\})", line):
            match = re.search(r"\{\{[^}]*\}(?!\})", line)
            if match:
                incomplete_tag = match.group(0)
                fixed_tag = incomplete_tag + "}"
                warnings.append(
                    f"Line {line_num}: Missing closing '}}}}' in variable tag\n"
                    f"  Found: {incomplete_tag}\n"
                    f"  Fix:   {fixed_tag}\n"
                    f"  {line}"
                )

        # Check for incomplete statement tags ({% without %} or with only one %)
        if re.search(r"\{%[^}]*(?<!%)(?<!%\s)\}(?!\})", line) and not re.search(r"\{%[^}]*%\}", line):
            match = re.search(r"\{%[^}]*\}", line)
            if match:
                incomplete_tag = match.group(0)
                fixed_tag = incomplete_tag[:-1] + "%}"
                warnings.append(
                    f"Line {line_num}: Missing closing '%}}}}' in statement tag\n"
                    f"  Found: {incomplete_tag}\n"
                    f"  Fix:   {fixed_tag}\n"
                    f"  {line}"
                )

    warnings.extend(_check_hyphenated_variables(lines))

    return warnings


def _check_hyphenated_variables(lines: list[str]) -> list[str]:
    """Check for variables containing hyphens, which Jinja2 interprets as subtraction."""
    warnings = []
    for line_num, line in enumerate(lines, start=1):
        for match in re.finditer(r"\{\{\s*([\w.\-]+)\s*\}\}", line):
            var_name = match.group(1)
            if "-" in var_name:
                suggested_name = var_name.replace("-", "_")
                warnings.append(
                    f"Line {line_num}: Variable name contains hyphen(s)\n"
                    f"  Found: {{{{{var_name}}}}}\n"
                    f"  Fix:   {{{{{suggested_name}}}}}\n"
                    f"  Reason: Jinja2 interprets hyphens as subtraction operators. "
                    f"Use underscores instead.\n"
                    f"  {line}"
                )
    return warnings


def _check_mismatched_tags(full_text: str) -> list[str]:
    """Check for mismatched loop and conditional tags."""
    warnings = []

    for_count = len(re.findall(rf"\{{%{DOCXTPL_TAG_PREFIX}?\s*for\s+", full_text))
    endfor_count = len(re.findall(rf"\{{%{DOCXTPL_TAG_PREFIX}?\s*endfor\s*%\}}", full_text))
    if for_count != endfor_count:
        warnings.append(
            f"Mismatched loop tags\n"
            f"  Found: {for_count} {{% for %}} tag(s) but {endfor_count} {{% endfor %}} tag(s)\n"
            f"  Fix: Each {{% for %}} must have a corresponding {{% endfor %}}"
        )

    if_count = len(re.findall(rf"\{{%{DOCXTPL_TAG_PREFIX}?\s*if\s+", full_text))
    endif_count = len(re.findall(rf"\{{%{DOCXTPL_TAG_PREFIX}?\s*endif\s*%\}}", full_text))
    if if_count != endif_count:
        warnings.append(
            f"Mismatched conditional tags\n"
            f"  Found: {if_count} {{% if %}} tag(s) but {endif_count} {{% endif %}} tag(s)\n"
            f"  Fix: Each {{% if %}} must have a corresponding {{% endif %}}"
        )

    return warnings


def _check_jinja_syntax(full_text: str) -> list[str]:
    """Check Jinja2 syntax by attempting to parse the template."""
    warnings = []

    try:
        parse_template(full_text)
    except TemplateSyntaxError as e:
        error_msg = str(e)
        line_preview = ""

        if e.lineno:
            lines = full_text.split("\n")
            if 0 < e.lineno <= len(lines):
                line_preview = f"  {lines[e.lineno - 1]}"

        if "expected token 'end of statement block'" in error_msg.lower():
            guidance = "Extra spaces in tag? Use '{{% for %}}' not '{{%  for %}}'"
        elif "unexpected end of template" in error_msg.lower():
            guidance = "Missing closing tag like '{{% endfor %}}' or '{{% endif %}}'"
        elif "expected name or number" in error_msg.lower():
            guidance = "Invalid variable name in '{{{{ }}}}' or '{{% %}}' tag"
        else:
            guidance = "Check for typos or formatting issues"

        if e.lineno and line_preview:
            warning = f"Line {e.lineno}: {guidance}\n{line_preview}\n  Error: {error_msg}"
        else:
            warning = f"Jinja2 syntax error: {guidance}\n  Error: {error_msg}"
        warnings.append(warning)

    return warnings
