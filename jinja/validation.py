"""
Run every check and decide which of their answers the author should actually see.

The checks themselves are in checks/, one module per kind of thing a check reads. The suppression rule below is the only logic here, and README.md explains it.
"""

from .checks.delimiters import check_malformed_tags, check_misplaced_statement_delimiters
from .checks.syntax import check_jinja_syntax, check_mismatched_tags
from .checks.tags import check_builtin_method_attributes, check_hyphenated_variables, check_merge_tags_outside_loops
from .diagnostics import Diagnostic
from .jinja_utils import ParseResult


def validate_template_jinja(full_text: str, parsed: ParseResult) -> list[Diagnostic]:
    "Run every text check, falling back to Jinja's parser for what they do not cover"
    lines = full_text.split("\n")

    # A broken delimiter changes how the rest of the template lexes, so neither Jinja's error nor
    # the tag counts mean anything after one. README.md, "Why custom checks instead of Jinja's parser".
    broken_delimiters = check_malformed_tags(lines) + check_misplaced_statement_delimiters(lines)
    unbalanced_blocks = check_mismatched_tags(full_text)

    warnings = list(broken_delimiters or unbalanced_blocks)
    if not broken_delimiters:
        warnings.extend(check_jinja_syntax(full_text, parsed, blocks_already_counted=bool(unbalanced_blocks)))

    # None of these says anything about whether the template parses, so none may hide a syntax
    # error from the fallback above.
    warnings.extend(check_hyphenated_variables(full_text))
    warnings.extend(check_builtin_method_attributes(full_text))
    warnings.extend(check_merge_tags_outside_loops(full_text))
    return warnings
