"""
The one way in: hand it template text, get back what the template needs and what is wrong with it.

Everything else in this package is an internal step. Parsing happens here, exactly once, and both
halves are handed the same result: the walk in variable_tree.py, and the checks in checks/.
"""

from typing import NamedTuple

from jinja2 import Environment, TemplateAssertionError, TemplateSyntaxError, meta, nodes

from .checks.blocks import check_merge_tags_outside_loops, check_mismatched_tags
from .checks.delimiters import check_malformed_tags, check_misplaced_statement_delimiters
from .checks.names import check_builtin_method_attributes, check_hyphenated_variables
from .checks.objects import check_no_objects_printed_directly
from .checks.parser import check_jinja_syntax
from .utils.docxtpl_utils import normalize_docxtpl_prefixes
from .utils.tree_utils import refine_list_formats
from .variable_tree import VariableNode, VariableTreeVisitor

JINJA_ENV = Environment()


class TemplateReport(NamedTuple):
    """
    variables: the variable tree described in README.md, empty when the template will not parse
    diagnostics: every problem found, in the order a reader should see them
    """

    variables: dict[str, VariableNode]
    diagnostics: list[str]


def analyze_jinja_template(template_text: str) -> TemplateReport:
    jinja_ast, syntax_error = None, None
    try:
        jinja_ast = JINJA_ENV.parse(normalize_docxtpl_prefixes(template_text))
    except TemplateSyntaxError as e:
        syntax_error = e
    validation_errors = validate(template_text, syntax_error)
    variables, variable_conflict_errors = walk(jinja_ast)
    return TemplateReport(variables, validation_errors + variable_conflict_errors)


def validate(full_text: str, error: TemplateSyntaxError | None) -> list[str]:
    "Run every text check, falling back to Jinja's parser for what they do not cover"
    lines = full_text.split("\n")

    # A broken delimiter makes Jinja read the tag as plain text, so nothing after it can be
    # trusted. Neither Jinja's own error nor the tag counts mean anything. See the README.
    broken_delimiters = check_malformed_tags(lines) + check_misplaced_statement_delimiters(lines)
    unbalanced_blocks = check_mismatched_tags(full_text)

    warnings = list(broken_delimiters or unbalanced_blocks)
    if not broken_delimiters:
        warnings.extend(check_jinja_syntax(full_text, error, blocks_already_counted=bool(unbalanced_blocks)))

    # A template can be perfectly valid and still hit these, so they must never hide a real
    # syntax error from the fallback above.
    warnings.extend(check_hyphenated_variables(full_text))
    warnings.extend(check_builtin_method_attributes(full_text))
    warnings.extend(check_merge_tags_outside_loops(full_text))
    return warnings


def walk(ast: nodes.Template | None) -> tuple[dict[str, VariableNode], list[str]]:
    """Build the variable tree from an already-parsed template, and warn about what it finds."""
    if not ast:
        return {}, []

    visitor = VariableTreeVisitor()
    visitor.visit(ast)

    # Jinja decides which names the template actually asks for. The walk only says what shape
    # each one has. Anything the walk saw but Jinja did not ask for is dropped.
    try:
        required = meta.find_undeclared_variables(ast)
    except TemplateAssertionError:
        # Asking Jinja for the names compiles the template, so an unknown filter fails here rather
        # than at parse time. A template may well use a filter the caller registers later.
        return {}, []

    variables: dict[str, VariableNode] = {name: visitor.root.get(name, {"type": "string"}) for name in sorted(required)}
    refine_list_formats(variables)
    return variables, list(dict.fromkeys(visitor.conflicts + check_no_objects_printed_directly(visitor)))
