"""
Jinja template analysis which returns what data a template needs, and what is wrong with it:

    report = analyze_jinja_template(template_text)
    report.variables    # dict[str, VariableNode] -> variable names and their shapes
    report.diagnostics  # list[str] -> list of warnings
"""

from .analyze import analyze_jinja_template
from .types import (
    BooleanNode,
    ListNode,
    NumberNode,
    ObjectNode,
    StringNode,
    TemplateReport,
    UnknownNode,
    VariableNode,
    child_properties,
)

__all__ = [
    "BooleanNode",
    "ListNode",
    "NumberNode",
    "ObjectNode",
    "StringNode",
    "TemplateReport",
    "UnknownNode",
    "VariableNode",
    "analyze_jinja_template",
    "child_properties",
]
