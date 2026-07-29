"""
One problem found in a template, as data rather than as a finished sentence.

Diagnostics are stored on the template row and rendered straight into the upload panel, so render()
reproduces the exact bytes the checks used to build by hand. Rows written before this existed are
never recomputed, and they sit in the same list as new ones, so a wording change here would show up
as two styles in one panel. Change the wording only alongside a backfill.

Three layouts earned their differences before the type existed and are kept verbatim:

    DETAIL      Line 4: 'a' is used as both a value and an object
                  Found: a.b
                  Fix:   give the two uses different names          <- three spaces, aligned
                  Reason: ...                                       <- optional
                  {{ a.b }}                                         <- optional source line

    TAG_COUNT   Mismatched loop tags                                <- no line, nothing to point at
                  Found: 1 {% for %} tag(s) but 0 {% endfor %} tag(s)
                  Fix: Each {% for %} must have a corresponding {% endfor %}   <- one space

    SYNTAX      Line 2: Unexpected 'b' after the expression
                  {% if a b c %}                                    <- preview, already indented
                  Error: expected token 'end of statement block', got 'b'
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
