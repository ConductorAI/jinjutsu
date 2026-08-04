"""
A problem found in a template
"""

from typing import NamedTuple

LABEL_WIDTH = 8

class Diagnostic(NamedTuple):
    line_no: int  # the line the author has to look at, always known
    title: str  # the problem in a few words
    source_line: str  # that line as the author wrote it
    found: str  # the part of it that is wrong
    fix: str  # the corrected text to write instead, or what to do where no rewrite is safe
    reason: str  # why it matters, in terms of what the rendered document will do

    def __str__(self) -> str:
        return "\n".join(
            [
                f"Line {self.line_no}: {self.title}",
                _label_with_value("Source", self.source_line),
                _label_with_value("Found", self.found),
                _label_with_value("Fix", self.fix),
                _label_with_value("Reason", self.reason),
            ]
        )


def _label_with_value(label: str, value: str) -> str:
    return f"  {f'{label}:':<{LABEL_WIDTH}}{value}"
