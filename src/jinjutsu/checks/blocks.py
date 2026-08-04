"""
Warnings:
- Mismatched loop tags                         {% for %} and {% endfor %} counts differ
- Mismatched conditional tags                  {% if %} and {% endif %} counts differ
- Cell merge is not inside a loop              {% vm %} or {% hm %} with no enclosing {% for %}
"""

import re

from ..diagnostic import Diagnostic
from ..utils.string_utils import read_source_line
from ..utils.tag_utils import (
    STATEMENT_KEYWORD,
    Tag,
    TemplateText,
    statement_closing,
    statement_keyword,
    statement_opening,
)

# What each docxtpl prefix makes its tag consume. 'r' is a run, a span inside a paragraph, so two of
# them can share a line without either being destroyed
PREFIXED_ELEMENTS = {"tr": "table row", "tc": "table cell", "p": "paragraph"}


def check_mismatched_tags(text: TemplateText) -> list[Diagnostic]:
    warnings = []

    for opener, closer, title in [("for", "endfor", "loop"), ("if", "endif", "conditional")]:
        open_positions = [match.start() for match in re.finditer(statement_opening(opener), text.source)]
        close_positions = [match.start() for match in re.finditer(statement_closing(closer), text.source)]
        if len(open_positions) == len(close_positions):
            continue
        line_no = _line_no_for_unbalanced_tag_error(text.source, open_positions, close_positions)
        warnings.append(
            Diagnostic(
                line_no=line_no,
                title=f"Mismatched {title} tags",
                found=(
                    f"{len(open_positions)} {{% {opener} %}} tag(s) "
                    f"but {len(close_positions)} {{% {closer} %}} tag(s)"
                ),
                fix=f"Each {{% {opener} %}} must have a corresponding {{% {closer} %}}",
                reason=(
                    f"Jinja pairs each {{% {opener} %}} with the next {{% {closer} %}}, so an unpaired one "
                    f"swallows the rest of the template and nothing renders."
                ),
                source_line=read_source_line(text.lines, line_no),
            )
        )

    return warnings


def check_prefixed_tags_share_an_element(source_lines: list[str]) -> list[Diagnostic]:
    """
    Check for two docxtpl prefixed statement tags inside the one Word element they each claim

    docxtpl replaces that element with the first tag, which deletes the second along with it, and jinja
    then reports the survivor's partner as an unknown tag. One tag per element is the only safe shape
    """
    warnings = []
    for line_no, line in enumerate(source_lines, 1):
        for prefix, element_name in PREFIXED_ELEMENTS.items():
            # A row is a whole line of extracted text; a cell or paragraph is one tab-separated field of it
            for element in [line] if prefix == "tr" else line.split("\t"):
                tag_shape = rf"\{{%{prefix}\s+(?:{STATEMENT_KEYWORD})\b.*?%\}}"
                if not (found := re.findall(tag_shape, element)):
                    continue
                shares_with = re.sub(tag_shape, "", element).strip()
                if len(found) > 1:
                    # The survivor loses its partner, so jinja reports the leftover as an unknown tag
                    warnings.append(
                        Diagnostic(
                            line_no=line_no,
                            title=f"Two '{prefix}' tags in one {element_name}",
                            found=" and ".join(found[:2]),
                            fix=f"Put each tag in its own {element_name}",
                            reason=(
                                f"'{prefix}' makes docxtpl replace the whole {element_name} with the first "
                                f"tag, which deletes the second one with it. The document then fails to "
                                f"render, blaming whichever tag was left without its partner."
                            ),
                            source_line=line,
                        )
                    )
                elif shares_with:
                    # Renders without complaint, so the loss only shows up by reading the finished document
                    warnings.append(
                        Diagnostic(
                            line_no=line_no,
                            title=f"'{prefix}' tag shares its {element_name} with other content",
                            found=f"{found[0]} beside '{shares_with}'",
                            fix=f"Give the tag a {element_name} of its own",
                            reason=(
                                f"'{prefix}' makes docxtpl replace the whole {element_name} with the tag, so "
                                f"'{shares_with}' is deleted with it. The document renders without any error "
                                f"and that content is simply missing."
                            ),
                            source_line=line,
                        )
                    )
    return warnings


def check_merge_tags_outside_loops(tags: list[Tag]) -> list[Diagnostic]:
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
                    Diagnostic(
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


def _line_no_for_unbalanced_tag_error(source: str, open_positions: list[int], close_positions: list[int]) -> int:
    """Returns line number of the first tag that doesn't have a corresponding closing tag"""
    depth = 0
    unpaired = 0  # the counts differ, so a tag below always claims this, and line 1 is the fallback if none does
    for position, is_opener in sorted([(p, True) for p in open_positions] + [(p, False) for p in close_positions]):
        if is_opener:
            if depth == 0:
                unpaired = position
            depth += 1
        else:
            depth -= 1
            if depth < 0:  # a closer with nothing open before it
                unpaired = position
                break
    return source.count("\n", 0, unpaired) + 1
