"""
Jinja template analysis which returns what data a template needs, and what is wrong with it:

    report = analyze_jinja_template(template_text)
    report.variables    # dict[str, VariableNode] -> variable names and their shapes
    report.diagnostics  # list[str] -> list of warnings
"""

from .analysis import TemplateReport, analyze_jinja_template
from .variable_tree import VariableNode

__all__ = [
    "TemplateReport",
    "VariableNode",
    "analyze_jinja_template",
]
