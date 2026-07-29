"""
Jinja template analysis: what data a template needs, and what is wrong with it. See README.md.

    report = analyze(template_text)
    report.variables    # name -> VariableNode, the shape of each variable
    report.diagnostics  # Diagnostic, one per problem found
"""

from .analysis import TemplateReport, analyze
from .diagnostics import Diagnostic, Layout
from .variable_tree import VariableNode

__all__ = [
    "Diagnostic",
    "Layout",
    "TemplateReport",
    "VariableNode",
    "analyze",
]
