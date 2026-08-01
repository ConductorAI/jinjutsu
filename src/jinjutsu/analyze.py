"""
The one way in: hand it template text, get back what the template needs and what is wrong with it

Everything else in this package is an internal step
Parsing happens once here, then variable_tree.py walks the result and checks/ inspects the text
The shapes both halves return are defined in types.py
"""

from jinja2 import Environment, TemplateAssertionError, TemplateSyntaxError, meta, nodes

from .checks.blocks import check_merge_tags_outside_loops, check_mismatched_tags
from .checks.delimiters import check_malformed_tags, check_misplaced_statement_delimiters
from .checks.names import check_builtin_method_attributes, check_hyphenated_variables
from .checks.objects import check_no_objects_printed_directly
from .checks.parser import check_jinja_syntax, should_defer_to_tag_counts
from .schema import context_schema
from .types import TemplateReport, UnknownNode, VariableNode
from .utils.docxtpl_utils import normalize_docxtpl_prefixes
from .utils.tag_utils import TemplateText, read_template
from .variable_tree import VariableTreeVisitor

JINJA_ENV = Environment()


def analyze_jinja_template(template_text: str) -> TemplateReport:
    jinja_ast, syntax_error = None, None
    try:
        jinja_ast = JINJA_ENV.parse(normalize_docxtpl_prefixes(template_text))
    except TemplateSyntaxError as e:
        syntax_error = e
    validation_errors = _validate(read_template(template_text), syntax_error)
    variables, variable_conflict_errors = _build_variable_tree(jinja_ast)
    return TemplateReport(context_schema(variables), validation_errors + variable_conflict_errors)


def _validate(text: TemplateText, error: TemplateSyntaxError | None) -> list[str]:
    """Run every check, falling back to jinja's parser for what we don't cover"""
    # A broken delimiter makes Jinja read the tag as plain text, so nothing after it can be trusted
    # Neither Jinja's own error nor the tag counts mean anything in this case, so hide those errors
    broken_delimiters = check_malformed_tags(text) + check_misplaced_statement_delimiters(text)
    unbalanced_blocks = check_mismatched_tags(text.source)
    # Jinja fails to parse an unbalanced block too, and the tag counts above already said it in plainer words
    defers_to_tag_counts = bool(unbalanced_blocks and error and should_defer_to_tag_counts(error))

    warnings = list(broken_delimiters or unbalanced_blocks)
    if not broken_delimiters and not defers_to_tag_counts:
        warnings.extend(check_jinja_syntax(text.lines, error))

    # A template can be perfectly valid and still hit these, so they must never hide a real syntax errors above
    warnings.extend(check_hyphenated_variables(text.tags))
    warnings.extend(check_builtin_method_attributes(text.tags))
    warnings.extend(check_merge_tags_outside_loops(text.tags))

    # The same mistake twice on one line reads as one problem, and the UI keys each warning by its text
    return list(dict.fromkeys(warnings))


def _build_variable_tree(ast: nodes.Template | None) -> tuple[dict[str, VariableNode], list[str]]:
    """Build the variable tree using nodes from a previously parsed template, and warn about issues it finds"""
    if not ast:
        return {}, []

    walked = VariableTreeVisitor().walk(ast)
    warnings = list(dict.fromkeys(walked.warnings + check_no_objects_printed_directly(walked)))

    # Jinja decides which names the template actually asks for
    # The walk only says what shape each one has
    # Anything the walk sees but jinja didn't ask for is dropped
    try:
        required = meta.find_undeclared_variables(ast)
    except TemplateAssertionError:
        return {}, warnings

    # A name jinja requires that the walk never shaped carries no evidence at all, so it stays unknown
    variables: dict[str, VariableNode] = {name: walked.root.get(name, UnknownNode()) for name in sorted(required)}
    return variables, warnings
