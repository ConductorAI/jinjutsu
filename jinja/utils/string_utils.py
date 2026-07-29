import re


# Replace {# #} spans so commented-out tags are not read as template code
def replace_comments_with_spaces(full_text: str) -> str:
    return re.sub(r"\{#.*?#\}", lambda m: re.sub(r"[^\n]", " ", m.group()), full_text, flags=re.DOTALL)


def warning_to_string(
    *,
    line_no: int,
    title: str,
    found: str,
    fix: str,
    reason: str | None = None,
    source_line: str | None = None,
) -> str:
    parts = [f"Line {line_no}: {title}", f"  Found: {found}", f"  Fix:   {fix}"]
    if reason:
        parts.append(f"  Reason: {reason}")
    if source_line:
        parts.append(f"  {source_line}")
    return "\n".join(parts)
