"""
What is written inside a well-formed tag: names that will not resolve the way the author expects.
"""

import re
from collections.abc import Iterable, Iterator

from ..diagnostics import Diagnostic, Layout
from ..jinja_utils import DOCXTPL_TAG_PREFIX, blank_comments, blank_string_literals

_HYPHENATED_NAME = re.compile(r"(?<![\w.])[A-Za-z_]\w*(?:\.\w+)*(?:-[A-Za-z_]\w*)+")

_BUILTIN_METHOD = (
    r"(?:append|clear|copy|count|extend|fromkeys|get|index|insert|items|keys|pop|popitem|remove"
    r"|reverse|setdefault|sort|update|values)"
)


def check_hyphenated_variables(full_text: str) -> list[Diagnostic]:
    """
    Check for names containing hyphens, which Jinja2 interprets as subtraction.

    Both sides of the hyphen must start a name, so {{ 2024-01 }} is arithmetic on literals and is
    left alone, as is the spaced {{ a - b }} form and the whitespace control in {%- if x %}.
    """
    warnings = []
    for line_num, line, tag_text in iter_tags(full_text):
        for match in _HYPHENATED_NAME.finditer(blank_string_literals(tag_text)):
            name = match.group()
            warnings.append(
                Diagnostic(
                    code="hyphenated-name",
                    layout=Layout.DETAIL,
                    line=line_num,
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


def check_builtin_method_attributes(full_text: str) -> list[Diagnostic]:
    """
    Check for fields read with dot syntax whose name is also a built-in dict or list method.

    Jinja resolves x.items to the value's own method before looking for an "items" field, so the
    document renders the method object. Which names collide depends on whether the value arrives
    as a dict or a list, so every name either type defines is reported. Bracket syntax is never
    ambiguous, so following the fix is safe even where the dotted form would have worked. An
    explicit call like x.items() is deliberate and is left alone.
    """
    warnings = []
    for line_num, line, tag_text in iter_tags(full_text):
        matches = list(re.finditer(rf"\.({_BUILTIN_METHOD})\b(?!\s*\()", blank_string_literals(tag_text)))
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
            Diagnostic(
                code="builtin-method-collision",
                layout=Layout.DETAIL,
                line=line_num,
                title=headline,
                found=tag_text,
                fix=_bracket_matches(tag_text, matches),
                reason=f"{reason} Use bracket syntax.",
                source_line=line,
            )
        )
    return warnings


def check_merge_tags_outside_loops(full_text: str) -> list[Diagnostic]:
    """
    Check for a docxtpl cell merge, {% vm %} or {% hm %}, used outside a loop.

    docxtpl expands both into {% if loop.first %}, so without an enclosing {% for %} the document
    fails to render. normalize_docxtpl_prefixes drops these tags before parsing, so Jinja never
    sees them and the syntax fallback cannot report this on its own.
    """
    warnings = []
    depth = 0
    for line_num, line, tag_text in iter_tags(full_text):
        if match := re.match(rf"\{{%-?\s*{DOCXTPL_TAG_PREFIX}?\s*(for|endfor|vm|hm)\b", tag_text):
            keyword = match.group(1)
            if keyword == "for":
                depth += 1
            elif keyword == "endfor":
                depth = max(depth - 1, 0)
            elif not depth:
                warnings.append(
                    Diagnostic(
                        code="merge-tag-outside-loop",
                        layout=Layout.DETAIL,
                        line=line_num,
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


def iter_tags(full_text: str) -> Iterator[tuple[int, str, str]]:
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
    for match in re.finditer(r"\{[%{](?:(?!\{[%{]).)*?[%}]\}", blank_comments(full_text), re.DOTALL):
        line_no = full_text.count("\n", 0, match.start()) + 1
        yield line_no, lines[line_no - 1], re.sub(r"\s*\n\s*", " ", match.group())


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
