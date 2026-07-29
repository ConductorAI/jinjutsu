"""
Warnings:
- Mismatched loop tags                         {% for %} and {% endfor %} counts differ
- Mismatched conditional tags                  {% if %} and {% endif %} counts differ

Jinja's own parse errors, rewritten for readability:
- Use '==' to compare                          {% if a = 1 %}
- Unexpected '...' after the expression        {% if a b c %}
- '...' is a curly quote                       {% if a == “x” %}
- Missing closing tag like '{% endfor %}'      unexpected end of template
- Invalid variable name in '{{ }}' or '{% %}'  {{ a. }}
- Check for typos or formatting issues         anything we do not recognise
"""

import re

from ..utils.docxtpl_utils import DOCXTPL_TAG_PREFIX
from ..utils.string_utils import replace_comments_with_spaces, warning_to_string
from ..utils.tag_utils import find_tags


def check_mismatched_tags(full_text: str) -> list[str]:
    warnings = []
    full_text = replace_comments_with_spaces(full_text)

    for_count = len(re.findall(rf"\{{%-?{DOCXTPL_TAG_PREFIX}?\s*for\s+", full_text))
    endfor_count = len(re.findall(rf"\{{%-?{DOCXTPL_TAG_PREFIX}?\s*endfor\s*-?%\}}", full_text))
    if for_count != endfor_count:
        warnings.append(
            _tag_count(
                title="Mismatched loop tags",
                found=f"{for_count} {{% for %}} tag(s) but {endfor_count} {{% endfor %}} tag(s)",
                fix="Each {% for %} must have a corresponding {% endfor %}",
            )
        )

    if_count = len(re.findall(rf"\{{%-?{DOCXTPL_TAG_PREFIX}?\s*if\s+", full_text))
    endif_count = len(re.findall(rf"\{{%-?{DOCXTPL_TAG_PREFIX}?\s*endif\s*-?%\}}", full_text))
    if if_count != endif_count:
        warnings.append(
            _tag_count(
                title="Mismatched conditional tags",
                found=f"{if_count} {{% if %}} tag(s) but {endif_count} {{% endif %}} tag(s)",
                fix="Each {% if %} must have a corresponding {% endif %}",
            )
        )

    return warnings


def _tag_count(*, title: str, found: str, fix: str) -> str:
    return f"{title}\n  Found: {found}\n  Fix: {fix}"


def check_merge_tags_outside_loops(full_text: str) -> list[str]:
    """
    Check for a docxtpl cell merge, {% vm %} or {% hm %}, used outside a loop.

    docxtpl expands both into {% if loop.first %}, so without an enclosing {% for %} the document
    fails to render. normalize_docxtpl_prefixes drops these tags before parsing, so Jinja never
    sees them and the syntax fallback cannot report this on its own.
    """
    warnings = []
    depth = 0
    for line_num, line, tag_text in find_tags(full_text):
        if match := re.match(rf"\{{%-?\s*{DOCXTPL_TAG_PREFIX}?\s*(for|endfor|vm|hm)\b", tag_text):
            keyword = match.group(1)
            if keyword == "for":
                depth += 1
            elif keyword == "endfor":
                depth = max(depth - 1, 0)
            elif not depth:
                warnings.append(
                    warning_to_string(
                        line_no=line_num,
                        title="Cell merge is not inside a loop",
                        found="{% " + keyword + " %}",
                        fix="move it into the {% for %} whose rows it should merge across, or delete it",
                        reason=(
                            f"'{keyword}' merges a cell with the copies a loop makes of it, so docxtpl "
                            f"renders it as a check on the first iteration. With no loop to belong to, "
                            f"the document fails with \"'loop' is undefined\"."
                        ),
                        source_line=line,
                    )
                )
    return warnings
