"""
Warnings:
- Variable name contains hyphen(s)             {{ total-discount }}
- Field '...' collides with a built-in method  {{ store.items }}
- Unknown filter '...'                         {{ x | to_json }}
"""

import re
from collections.abc import Iterable
from difflib import get_close_matches

from jinja2 import Environment, nodes

from ..diagnostic import Diagnostic
from ..utils.string_utils import read_source_line
from ..utils.tag_utils import Tag, statement_keyword

KNOWN_FILTERS = frozenset(Environment().filters)
KNOWN_TESTS = frozenset(Environment().tests)

# The filter 'uppercase' scores 0.714 against 'upper' which is an example of a typo this exists for
SUGGESTION_CUTOFF = 0.7

HYPHENATED_NAME = re.compile(r"(?<![\w.])[A-Za-z_]\w*(?:\.\w+)*(?:-[A-Za-z_]\w*)+")

BUILTIN_METHOD = (
    r"(?:append|clear|copy|count|extend|fromkeys|get|index|insert|items|keys|pop|popitem|remove"
    r"|reverse|setdefault|sort|update|values)"
)

LOOP_TAG = re.compile(statement_keyword("for"))
CONDITION_TAG = re.compile(statement_keyword("if|elif"))


def check_hyphenated_variables(tags: list[Tag]) -> list[Diagnostic]:
    """
    Confirm intent for names containing hyphens, which jinja interprets as subtraction

    Both sides of the hyphen must start a name, so {{ 2024-01 }} is math and not flagged
    The spaced {{ a - b }} form is also not flagged as well as the whitespace control in {%- if x %}
    """
    warnings = []
    for line_num, line, tag_text in tags:
        for match in HYPHENATED_NAME.finditer(_replace_string_literals_with_spaces(tag_text)):
            name = match.group()
            warnings.append(
                Diagnostic(
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


def check_unknown_filters(ast: nodes.Template, lines: list[str]) -> list[Diagnostic]:
    """
    Check for filter and test names jinja does not ship, which fail at render rather than at parse

    A name the renderer's environment registers is valid there and unknowable here, so the fix
    offers both readings: the typo of a built-in, and the custom filter this tool cannot see
    """
    warnings = []
    for node in ast.find_all((nodes.Filter, nodes.Test)):
        kind, known = ("filter", KNOWN_FILTERS) if isinstance(node, nodes.Filter) else ("test", KNOWN_TESTS)
        if node.name in known:
            continue
        suggestion = get_close_matches(node.name, known, n=1, cutoff=SUGGESTION_CUTOFF)
        warnings.append(
            Diagnostic(
                line_no=node.lineno,
                title=f"Unknown {kind} '{node.name}'",
                found=f"| {node.name}" if kind == "filter" else f"is {node.name}",
                fix=(
                    f"Did you mean '{suggestion[0]}'?"
                    if suggestion
                    else f"Register '{node.name}' in the environment that renders this template, or check the spelling"
                ),
                reason=(
                    f"Jinja only knows its built-in {kind}s, so the document fails to render with "
                    f"\"No {kind} named '{node.name}'\" unless the renderer registers it first."
                ),
                source_line=read_source_line(lines, node.lineno),
            )
        )
    return warnings


def check_builtin_method_attributes(tags: list[Tag]) -> list[Diagnostic]:
    """
    Check for fields read with dot syntax whose name is also a built-in dict or list method

    Jinja resolves x.items to the value's own method before looking for an "items" field, so the
    document renders the method object which looks like `<built-in method items of dict object at 0x105993a40>`
    Bracket syntax is never ambiguous, so following the fix is safe even where the dotted form would have worked
    Explicit calls like x.items() are deliberate and not flagged
    """
    warnings = []
    for line_num, line, tag_text in tags:
        matches = list(re.finditer(rf"\.({BUILTIN_METHOD})\b(?!\s*\()", _replace_string_literals_with_spaces(tag_text)))
        if not matches:
            continue
        fields = list(dict.fromkeys(match.group(1) for match in matches))
        if len(fields) == 1:
            headline = f"Field '{fields[0]}' collides with a built-in method"
            reads = f"Jinja reads '.{fields[0]}' as the value's own method"
        else:
            headline = f"Fields {_join_quoted(fields)} collide with built-in methods"
            reads = f"Jinja reads {_join_quoted(f'.{field}' for field in fields)} as the value's own methods"
        warnings.append(
            Diagnostic(
                line_no=line_num,
                title=headline,
                found=tag_text,
                fix=_bracket_matches(tag_text, matches),
                reason=f"{reads}, {_collision_symptom(tag_text, plural=len(fields) > 1)}. Use bracket syntax.",
                source_line=line,
            )
        )
    return warnings


def _collision_symptom(tag_text: str, *, plural: bool) -> str:
    """
    What the author will actually see, which is a different failure in each kind of tag

    A tag holds one loop and one test however many collisions it has, so only the printed wording turns plural
    """
    if LOOP_TAG.match(tag_text):
        return "so the loop tries to iterate a method instead of your list and the render fails, leaving no document"
    if CONDITION_TAG.match(tag_text):
        return "so the test passes whatever your data holds, because a method always counts as true"
    if plural:
        return "so the document renders the methods instead of your values"
    return "so the document renders the method instead of your value"


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
    # A tag is folded onto one line before it gets here, so there are no newlines to keep
    return re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", lambda m: " " * len(m.group()), tag_text)
