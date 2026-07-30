from jinja2 import Environment, TemplateSyntaxError

from .. import analyze_jinja_template
from ..analysis import _build_variable_tree
from ..utils.docxtpl_utils import normalize_docxtpl_prefixes


def warnings_for(text: str) -> list[str]:
    return analyze_jinja_template(text).diagnostics


def variables_for(text: str):
    return analyze_jinja_template(text).variables


def conflicts_for(text: str) -> list[str]:
    "Just what the walk noticed, without the text checks analyze_jinja_template() merges in alongside"
    try:
        ast = Environment().parse(normalize_docxtpl_prefixes(text))
    except TemplateSyntaxError:
        ast = None
    return _build_variable_tree(ast)[1]
