import re
from collections.abc import Iterable, Iterator

from .jinja_utils import DOCXTPL_TAG_PREFIX, format_warning, parse_result

_JINJA_STATEMENT_KEYWORD = r"(?:if|elif|else|endif|for|endfor|set|endset)"
_HYPHENATED_NAME = re.compile(r"(?<![\w.])[A-Za-z_]\w*(?:\.\w+)*(?:-[A-Za-z_]\w*)+")
_BUILTIN_METHOD = (
    r"(?:append|clear|copy|count|extend|fromkeys|get|index|insert|items|keys|pop|popitem|remove"
    r"|reverse|setdefault|sort|update|values)"
)


def validate_template_jinja(full_text: str) -> list[str]:
    """
    Validate Jinja2 syntax in a docx template.

    Returns:
        List of warning messages describing any malformed Jinja2 syntax.
    """
    lines = full_text.split("\n")

    warnings = []
    warnings.extend(_check_malformed_tags(lines))
    warnings.extend(_check_misplaced_statement_delimiters(lines))
    warnings.extend(_check_mismatched_tags(full_text))

    if not warnings:
        # Fall back to Jinja's own parser only when the checks above found nothing
        warnings.extend(_check_jinja_syntax(full_text))

    # These run below the gate. A template can be valid and still hit them, and none of them says
    # anything about whether it parses, so none may hide a syntax error from the fallback.
    warnings.extend(_check_hyphenated_variables(full_text))
    warnings.extend(_check_builtin_method_attributes(full_text))
    warnings.extend(_check_merge_tags_outside_loops(full_text))
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
                warnings.append(
                    format_warning(
                        line_no=line_num,
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
                    format_warning(
                        line_no=line_num,
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
                format_warning(
                    line_no=line_num,
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
                format_warning(
                    line_no=line_num,
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
                format_warning(
                    line_no=line_num,
                    title="Missing closing '%}' in statement tag",
                    found=incomplete_tag,
                    fix=incomplete_tag[:-1] + "%}",
                    source_line=line,
                )
            )

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
            warnings.append(
                format_warning(
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


def _check_hyphenated_variables(full_text: str) -> list[str]:
    """
    Check for names containing hyphens, which Jinja2 interprets as subtraction.

    Both sides of the hyphen must start a name, so {{ 2024-01 }} is arithmetic on literals and is
    left alone, as is the spaced {{ a - b }} form and the whitespace control in {%- if x %}.
    """
    warnings = []
    for line_num, line, tag_text in _iter_tags(full_text):
        for match in _HYPHENATED_NAME.finditer(_blank_string_literals(tag_text)):
            name = match.group()
            warnings.append(
                format_warning(
                    line_no=line_num,
                    title="Variable name contains hyphen(s)",
                    found=name,
                    fix=name.replace("-", "_"),
                    reason=(
                        f"Jinja2 reads the hyphen as subtraction, not as part of a name. If you "
                        f"meant a single variable, use the underscored form above. If you meant "
                        f"to subtract, write {name.replace('-', ' - ')} with spaces and this "
                        f"warning will clear."
                    ),
                    source_line=line,
                )
            )
    return warnings


def _check_mismatched_tags(full_text: str) -> list[str]:
    """Check for mismatched loop and conditional tags."""
    warnings = []
    full_text = _blank_comments(full_text)

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


def _check_builtin_method_attributes(full_text: str) -> list[str]:
    """
    Check for fields read with dot syntax whose name is also a built-in dict or list method.

    Jinja resolves x.items to the value's own method before looking for an "items" field, so the
    document renders the method object. Which names collide depends on whether the value arrives
    as a dict or a list, so every name either type defines is reported. Bracket syntax is never
    ambiguous, so following the fix is safe even where the dotted form would have worked. An
    explicit call like x.items() is deliberate and is left alone.
    """
    warnings = []
    for line_num, line, tag_text in _iter_tags(full_text):
        matches = list(re.finditer(rf"\.({_BUILTIN_METHOD})\b(?!\s*\()", _blank_string_literals(tag_text)))
        if not matches:
            continue
        fields = list(dict.fromkeys(match.group(1) for match in matches))
        if len(fields) == 1:
            headline = f"Field '{fields[0]}' collides with a built-in method"
            reason = (
                f"Jinja reads '.{fields[0]}' as the value's own method, so the document "
                f"renders the method instead of your value."
            )
        else:
            headline = f"Fields {_join_quoted(fields)} collide with built-in methods"
            reason = (
                f"Jinja reads {_join_quoted(f'.{field}' for field in fields)} as the value's "
                f"own methods, so the document renders the methods instead of your values."
            )
        warnings.append(
            format_warning(
                line_no=line_num,
                title=headline,
                found=tag_text,
                fix=_bracket_matches(tag_text, matches),
                reason=f"{reason} Use bracket syntax.",
                source_line=line,
            )
        )
    return warnings


def _check_merge_tags_outside_loops(full_text: str) -> list[str]:
    """
    Check for a docxtpl cell merge, {% vm %} or {% hm %}, used outside a loop.

    docxtpl expands both into {% if loop.first %}, so without an enclosing {% for %} the document
    fails to render. normalize_docxtpl_prefixes drops these tags before parsing, so Jinja never
    sees them and the syntax fallback cannot report this on its own.
    """
    warnings = []
    depth = 0
    for line_num, line, tag_text in _iter_tags(full_text):
        if match := re.match(rf"\{{%-?\s*{DOCXTPL_TAG_PREFIX}?\s*(for|endfor|vm|hm)\b", tag_text):
            keyword = match.group(1)
            if keyword == "for":
                depth += 1
            elif keyword == "endfor":
                depth = max(depth - 1, 0)
            elif not depth:
                warnings.append(
                    format_warning(
                        line_no=line_num,
                        title="Cell merge is not inside a loop",
                        found="{% " + keyword + " %}",
                        fix="move it into the {% for %} whose rows it should merge across, or delete it",
                        reason=(
                            f"'{keyword}' merges a cell with the copies a loop makes of it, so docxtpl "
                            f"renders it as a check on the first iteration. With no loop to belong to, "
                            f"the document fails with \"'loop' is undefined\"."
                        ),
                        source_line=line,
                    )
                )
    return warnings


def _check_jinja_syntax(full_text: str) -> list[str]:
    """Check Jinja2 syntax by attempting to parse the template."""
    warnings = []

    if e := parse_result(full_text).error:
        error_msg = str(e)
        line_preview = ""

        if e.lineno:
            lines = full_text.split("\n")
            if 0 < e.lineno <= len(lines):
                line_preview = f"  {lines[e.lineno - 1]}"

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


def _iter_tags(full_text: str) -> Iterator[tuple[int, str, str]]:
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
    for match in re.finditer(r"\{[%{](?:(?!\{[%{]).)*?[%}]\}", _blank_comments(full_text), re.DOTALL):
        line_no = full_text.count("\n", 0, match.start()) + 1
        yield line_no, lines[line_no - 1], re.sub(r"\s*\n\s*", " ", match.group())


def _blank_string_literals(tag_text: str) -> str:
    "Replace the contents of quoted literals so validation regex doesn't run on them"
    return re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", lambda m: " " * len(m.group()), tag_text)


def _blank_comments(full_text: str) -> str:
    """
    Replace {# #} spans so commented-out tags are not read as template code.

    Line breaks are kept and every other character becomes a space, which leaves offsets and line
    numbers unchanged for the checks that report them.
    """
    return re.sub(r"\{#.*?#\}", lambda m: re.sub(r"[^\n]", " ", m.group()), full_text, flags=re.DOTALL)
