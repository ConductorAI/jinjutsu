"""
Warnings:
- Mismatched loop tags                         {% for %} and {% endfor %} counts differ
- Mismatched conditional tags                  {% if %} and {% endif %} counts differ
- Cell merge is not inside a loop              {% vm %} or {% hm %} with no enclosing {% for %}
"""

import re

from ..utils.string_utils import warning_to_string
from ..utils.tag_utils import Tag, statement_closing, statement_keyword, statement_opening


def check_mismatched_tags(source: str) -> list[str]:
    warnings = []

    for_count = len(re.findall(statement_opening("for"), source))
    endfor_count = len(re.findall(statement_closing("endfor"), source))
    if for_count != endfor_count:
        warnings.append(
            warning_to_string(
                title="Mismatched loop tags",
                found=f"{for_count} {{% for %}} tag(s) but {endfor_count} {{% endfor %}} tag(s)",
                fix="Each {% for %} must have a corresponding {% endfor %}",
            )
        )

    if_count = len(re.findall(statement_opening("if"), source))
    endif_count = len(re.findall(statement_closing("endif"), source))
    if if_count != endif_count:
        warnings.append(
            warning_to_string(
                title="Mismatched conditional tags",
                found=f"{if_count} {{% if %}} tag(s) but {endif_count} {{% endif %}} tag(s)",
                fix="Each {% if %} must have a corresponding {% endif %}",
            )
        )

    return warnings


def check_merge_tags_outside_loops(tags: list[Tag]) -> list[str]:
    """
    Check for a docxtpl cell merge, {% vm %} or {% hm %}, used outside a loop

    Since docxtpl expands these into {% if loop.first %}, the document fails to render without a closing {% for %}
    we drop these tags before parsing, so the jinja validator can't report this on its own
    """
    warnings = []
    depth = 0
    for line_num, line, tag_text in tags:
        if match := re.match(statement_keyword("for|endfor|vm|hm"), tag_text):
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
                        fix="Move it into the {% for %} whose rows it should merge across, or delete it",
                        reason=(
                            f"'{keyword}' merges a cell with the copies a loop makes of it, so docxtpl "
                            f"renders it as a check on the first iteration. With no loop to belong to, "
                            f"the document fails with \"'loop' is undefined\"."
                        ),
                        source_line=line,
                    )
                )
    return warnings
