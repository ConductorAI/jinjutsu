"""
Warnings:
- Variable name contains hyphen(s)             {{ total-discount }}
- Field '...' collides with a built-in method  {{ store.items }}
"""

import re
from collections.abc import Iterable

from ..utils.string_utils import warning_to_string
from ..utils.tag_utils import find_tags

HYPHENATED_NAME = re.compile(r"(?<![\w.])[A-Za-z_]\w*(?:\.\w+)*(?:-[A-Za-z_]\w*)+")

BUILTIN_METHOD = (
    r"(?:append|clear|copy|count|extend|fromkeys|get|index|insert|items|keys|pop|popitem|remove"
    r"|reverse|setdefault|sort|update|values)"
)


def check_hyphenated_variables(full_text: str) -> list[str]:
    """
    Confirm intent for names containing hyphens, which jinja interprets as subtraction

    Both sides of the hyphen must start a name, so {{ 2024-01 }} is math and not flagged
    The spaced {{ a - b }} form is also not flagged as well as the whitespace control in {%- if x %}
    """
    warnings = []
    for line_num, line, tag_text in find_tags(full_text):
        for match in HYPHENATED_NAME.finditer(_replace_string_literals_with_spaces(tag_text)):
            name = match.group()
            warnings.append(
                warning_to_string(
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


def check_builtin_method_attributes(full_text: str) -> list[str]:
    """
    Check for fields read with dot syntax whose name is also a built-in dict or list method

    Jinja resolves x.items to the value's own method before looking for an "items" field, so the
    document renders the method object which looks like `<built-in method items of dict object at 0x105993a40>`
    Bracket syntax is never ambiguous, so following the fix is safe even where the dotted form would have worked
    Explicit calls like x.items() are deliberate and not flagged
    """
    warnings = []
    for line_num, line, tag_text in find_tags(full_text):
        matches = list(re.finditer(rf"\.({BUILTIN_METHOD})\b(?!\s*\()", _replace_string_literals_with_spaces(tag_text)))
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
            warning_to_string(
                line_no=line_num,
                title=headline,
                found=tag_text,
                fix=_bracket_matches(tag_text, matches),
                reason=f"{reason} Use bracket syntax.",
                source_line=line,
            )
        )
    return warnings


def _bracket_matches(tag_text: str, matches: list[re.Match[str]]) -> str:
    """Rewrite each '.field' match as bracket access, right to left so earlier offsets stay valid"""
    for match in reversed(matches):
        tag_text = f"{tag_text[: match.start()]}[{match.group(1)!r}]{tag_text[match.end() :]}"
    return tag_text


def _join_quoted(names: Iterable[str]) -> str:
    quoted = [f"'{name}'" for name in names]
    if len(quoted) == 2:
        return " and ".join(quoted)
    return ", ".join(quoted[:-1]) + f", and {quoted[-1]}"


def _replace_string_literals_with_spaces(tag_text: str) -> str:
    return re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", lambda m: " " * len(m.group()), tag_text)
