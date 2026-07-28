import re
from collections.abc import Iterable

from jinja2 import TemplateSyntaxError

from .jinja_utils import DOCXTPL_TAG_PREFIX, parse_template

# Statement keywords that identify a brace-delimited chunk as an attempted Jinja tag
_JINJA_STATEMENT_KEYWORD = r"(?:if|elif|else|endif|for|endfor|set|endset)"

# Dict methods that win over a same-named key during Jinja attribute lookup, e.g. {{ r.items }}
_DICT_METHOD = r"(?:clear|copy|fromkeys|get|items|keys|pop|popitem|setdefault|update|values)"


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
        # Fall back to Jinja's own parser only when the checks above found nothing. It reports the
        # same problems in less readable terms, so running both would duplicate every error.
        warnings.extend(_check_jinja_syntax(full_text))

    # Runs outside the gate above: a valid template can still contain this, and it must not
    # suppress the syntax errors that gate reports.
    warnings.extend(_check_dict_method_attributes(lines))
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
        if match := re.search(r"\{\{[^}]*\}(?!\})", line):
            incomplete_tag = match.group(0)
            fixed_tag = incomplete_tag + "}"
            warnings.append(
                f"Line {line_num}: Missing closing '}}}}' in variable tag\n"
                f"  Found: {incomplete_tag}\n"
                f"  Fix:   {fixed_tag}\n"
                f"  {line}"
            )

        # Check for incomplete statement tags ({% without %} or with only one %)
        if (
            re.search(r"\{%[^}]*(?<!%)(?<!%\s)\}(?!\})", line)
            and not re.search(r"\{%[^}]*%\}", line)
            and (match := re.search(r"\{%[^}]*\}", line))
        ):
            incomplete_tag = match.group(0)
            fixed_tag = incomplete_tag[:-1] + "%}"
            warnings.append(
                f"Line {line_num}: Missing closing '%}}}}' in statement tag\n"
                f"  Found: {incomplete_tag}\n"
                f"  Fix:   {fixed_tag}\n"
                f"  {line}"
            )

    warnings.extend(_check_misplaced_statement_delimiters(lines))
    warnings.extend(_check_hyphenated_variables(lines))

    return warnings


def _check_misplaced_statement_delimiters(lines: list[str]) -> list[str]:
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
                # '{ % if x %}' is the extra-space case, already reported by _check_malformed_tags
                continue
            malformed_tag = match.group(0)
            fixed_tag = f"{{% {content.replace('%', '').strip()} %}}"
            warnings.append(
                f"Line {line_num}: Misplaced '%' in statement tag\n"
                f"  Found: {malformed_tag}\n"
                f"  Fix:   {fixed_tag}\n"
                f"  Reason: A statement tag must open with '{{%'. Jinja reads this as plain text, "
                f"so its matching end tag will be reported as an error elsewhere.\n"
                f"  {line}"
            )
    return warnings


def _check_hyphenated_variables(lines: list[str]) -> list[str]:
    """Check for variables containing hyphens, which Jinja2 interprets as subtraction."""
    warnings = []
    for line_num, line in enumerate(lines, start=1):
        for match in re.finditer(r"\{\{\s*([\w.\-]+)\s*\}\}", line):
            var_name = match.group(1)
            if re.fullmatch(r"[\d.\-]+", var_name):
                # {{ 2024-01 }} is arithmetic on literals, not a variable name
                continue
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

    for_count = len(re.findall(rf"\{{%-?{DOCXTPL_TAG_PREFIX}?\s*for\s+", full_text))
    endfor_count = len(re.findall(rf"\{{%-?{DOCXTPL_TAG_PREFIX}?\s*endfor\s*-?%\}}", full_text))
    if for_count != endfor_count:
        warnings.append(
            f"Mismatched loop tags\n"
            f"  Found: {for_count} {{% for %}} tag(s) but {endfor_count} {{% endfor %}} tag(s)\n"
            f"  Fix: Each {{% for %}} must have a corresponding {{% endfor %}}"
        )

    if_count = len(re.findall(rf"\{{%-?{DOCXTPL_TAG_PREFIX}?\s*if\s+", full_text))
    endif_count = len(re.findall(rf"\{{%-?{DOCXTPL_TAG_PREFIX}?\s*endif\s*-?%\}}", full_text))
    if if_count != endif_count:
        warnings.append(
            f"Mismatched conditional tags\n"
            f"  Found: {if_count} {{% if %}} tag(s) but {endif_count} {{% endif %}} tag(s)\n"
            f"  Fix: Each {{% if %}} must have a corresponding {{% endif %}}"
        )

    return warnings


def _check_dict_method_attributes(lines: list[str]) -> list[str]:
    """
    Check for fields read with dot syntax whose name is also a built-in dict method.

    Jinja resolves x.items to the dict's own method before looking for an "items" key, so the
    document renders the method object. Bracket syntax has no such ambiguity. An explicit call
    like x.items() is deliberate and is left alone.
    """
    warnings = []
    for line_num, line in enumerate(lines, start=1):
        for tag in re.finditer(r"\{[%{].*?[%}]\}", line):
            tag_text = tag.group()
            matches = list(re.finditer(rf"\.({_DICT_METHOD})\b(?!\s*\()", _blank_string_literals(tag_text)))
            if not matches:
                continue
            fields = list(dict.fromkeys(match.group(1) for match in matches))
            if len(fields) == 1:
                headline = f"Field '{fields[0]}' collides with a built-in dict method"
                reason = (
                    f"Jinja reads '.{fields[0]}' as the dictionary's own method, so the document "
                    f"renders the method instead of your value."
                )
            else:
                headline = f"Fields {_join_quoted(fields)} collide with built-in dict methods"
                reason = (
                    f"Jinja reads {_join_quoted(f'.{field}' for field in fields)} as the dictionary's "
                    f"own methods, so the document renders the methods instead of your values."
                )
            warnings.append(
                f"Line {line_num}: {headline}\n"
                f"  Found: {tag_text}\n"
                f"  Fix:   {_bracket_matches(tag_text, matches)}\n"
                f"  Reason: {reason} Use bracket syntax.\n"
                f"  {line}"
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


def _bracket_matches(tag_text: str, matches: list[re.Match[str]]) -> str:
    """Rewrite each '.field' match as bracket access, right to left so earlier offsets stay valid."""
    for match in reversed(matches):
        tag_text = f"{tag_text[: match.start()]}[{match.group(1)!r}]{tag_text[match.end() :]}"
    return tag_text


def _join_quoted(names: Iterable[str]) -> str:
    quoted = [f"'{name}'" for name in names]
    if len(quoted) == 2:
        return " and ".join(quoted)
    return ", ".join(quoted[:-1]) + f", and {quoted[-1]}"


def _blank_string_literals(tag_text: str) -> str:
    """
    Replace the contents of quoted literals with spaces, keeping the tag's length and offsets.

    Text inside a literal is data, not a field path, so it must not be matched by the attribute
    checks above.
    """
    return re.sub(r"'[^']*'|\"[^\"]*\"", lambda m: " " * len(m.group()), tag_text)
