"""
Jinja template analysis which returns what data a template needs, and what is wrong with it:

    report = analyze_jinja_template(template_text)
    report.schema       # dict -> JSON Schema for the context the template expects
    report.diagnostics  # list[Diagnostic] -> line_no, title, source_line, found, fix, reason; str() formats it

For a Word template, extract_docx_text(path) gives the text to analyze:

    report = analyze_jinja_template(extract_docx_text("invoice.docx"))
"""

from .analyze import analyze_jinja_template
from .diagnostic import Diagnostic
from .shapes import TemplateReport
from .utils.docx_utils import extract_docx_text

__all__ = [
    "Diagnostic",
    "TemplateReport",
    "analyze_jinja_template",
    "extract_docx_text",
]
