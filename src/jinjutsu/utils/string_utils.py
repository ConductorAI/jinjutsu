import re


def blank_out(text: str) -> str:
    """Replace every character with a space, keeping newlines so line numbers don't move"""
    return re.sub(r"[^\n]", " ", text)


def replace_comments_with_spaces(full_text: str) -> str:
    """Replace {# #} spans so jinja doesn't read commented-out tags as template code"""
    return re.sub(r"\{#.*?#\}", lambda m: blank_out(m.group()), full_text, flags=re.DOTALL)


def read_source_line(lines: list[str], line_no: int) -> str:
    """The line as the author wrote it, empty only if jinja blames a line past the end of the template"""
    return lines[line_no - 1] if 0 < line_no <= len(lines) else ""
