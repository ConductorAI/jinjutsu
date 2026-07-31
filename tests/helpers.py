from jinja2 import Environment, TemplateSyntaxError

from jinjutsu import analyze_jinja_template
from jinjutsu.analyze import _build_variable_tree
from jinjutsu.utils.docxtpl_utils import normalize_docxtpl_prefixes


def warnings_for(text: str) -> list[str]:
    return analyze_jinja_template(text).diagnostics


def schema_for(text: str) -> dict:
    return analyze_jinja_template(text).schema


def variables_for(text: str):
    "The internal tree, which the public report no longer carries"
    return _build_variable_tree(_ast_for(text))[0]


def conflicts_for(text: str) -> list[str]:
    "Just what the walk noticed, without the text checks analyze_jinja_template() merges in alongside"
    return _build_variable_tree(_ast_for(text))[1]


def _ast_for(text: str):
    try:
        return Environment().parse(normalize_docxtpl_prefixes(text))
    except TemplateSyntaxError:
        return None
