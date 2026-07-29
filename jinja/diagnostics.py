"""
One problem found in a template, as data rather than as a finished sentence.

render() reproduces the display text. The three layouts and the reason they differ are in README.md,
along with the warning that matters most here: diagnostics are stored per template row and never
recomputed, so changing the wording shows old and new styles together. Backfill if you change it.
"""

from dataclasses import dataclass
from enum import Enum, auto


class Layout(Enum):
    DETAIL = auto()
    TAG_COUNT = auto()
    SYNTAX = auto()


@dataclass(frozen=True)
class Diagnostic:
    """
    code identifies the check that produced this, for callers that want to group or suppress.
    line is None when the problem belongs to the whole template rather than one place in it.

    Every field is plain data, so callers write Jinja snippets literally instead of escaping braces
    past an f-string.
    """

    code: str
    layout: Layout
    title: str
    line: int | None = None
    found: str | None = None
    fix: str | None = None
    reason: str | None = None
    source_line: str | None = None
    error: str | None = None

    def render(self) -> str:
        if self.layout is Layout.TAG_COUNT:
            return f"{self.title}\n  Found: {self.found}\n  Fix: {self.fix}"
        if self.layout is Layout.SYNTAX:
            # A blank source_line still means Jinja pointed at a real line, so it keeps the heading
            # that names it. Only when there is no line at all does the wording fall back.
            if self.line and self.source_line is not None:
                return f"Line {self.line}: {self.title}\n  {self.source_line}\n  Error: {self.error}"
            return f"Jinja2 syntax error: {self.title}\n  Error: {self.error}"
        parts = [f"Line {self.line}: {self.title}", f"  Found: {self.found}", f"  Fix:   {self.fix}"]
        if self.reason:
            parts.append(f"  Reason: {self.reason}")
        if self.source_line:
            parts.append(f"  {self.source_line}")
        return "\n".join(parts)
