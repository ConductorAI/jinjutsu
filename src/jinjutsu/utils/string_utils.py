import re


def blank_out(text: str) -> str:
    """Replace every character with a space, keeping newlines so line numbers don't move"""
    return re.sub(r"[^\n]", " ", text)


def replace_comments_with_spaces(full_text: str) -> str:
    """Replace {# #} spans so jinja doesn't read commented-out tags as template code"""
    return re.sub(r"\{#.*?#\}", lambda m: blank_out(m.group()), full_text, flags=re.DOTALL)


def warning_to_string(
    *,
    title: str,
    found: str,
    fix: str,
    line_no: int | None = None,
    reason: str | None = None,
    source_line: str | None = None,
) -> str:
    """`line_no` is None for a count that is wrong across the whole template, with no one line to blame"""
    parts = [title if line_no is None else f"Line {line_no}: {title}", f"  Found: {found}", f"  Fix:   {fix}"]
    if reason:
        parts.append(f"  Reason: {reason}")
    if source_line:
        parts.append(f"  {source_line}")
    return "\n".join(parts)
