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
    reason: str,
    line_no: int,
    source_line: str,
) -> str:
    return "\n".join(
        [
            f"Line {line_no}: {title}",
            _labelled("Source", source_line),
            _labelled("Found", found),
            _labelled("Fix", fix),
            _labelled("Reason", reason),
        ]
    )


def read_source_line(lines: list[str], line_no: int) -> str:
    """The line as the author wrote it, empty only if jinja blames a line past the end of the template"""
    return lines[line_no - 1] if 0 < line_no <= len(lines) else ""


def _labelled(label: str, value: str) -> str:
    """Every label padded to the longest one, so the values line up in a column under the title"""
    return f"  {f'{label}:':<8}{value}"
