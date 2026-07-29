"""
The one way in: hand it template text, get back what the template needs and what is wrong with it.

Everything else in this package is an internal step. Callers used to reach for the tree walk and the
text checks separately and concatenate the two lists of warnings themselves, which meant knowing
that a syntax error is reported by one of them and a variable conflict by the other. Asking only the
walk left you with an empty tree and no reason for it, because the reason lived in the other half.

Parsing happens here, exactly once, and both halves are handed the same result.
"""

from typing import NamedTuple

from .diagnostics import Diagnostic
from .extraction import analyze_template
from .jinja_utils import parse_result
from .validation import validate_template_jinja
from .variable_tree import VariableNode


class TemplateReport(NamedTuple):
    """
    variables: the variable tree described in variable_tree.py, empty when the template will not parse
    diagnostics: every problem found, in the order a reader should see them
    """

    variables: dict[str, VariableNode]
    diagnostics: list[Diagnostic]


def analyze(text: str) -> TemplateReport:
    parsed = parse_result(text)
    variables, conflicts = analyze_template(parsed)
    return TemplateReport(variables, validate_template_jinja(text, parsed) + conflicts)
