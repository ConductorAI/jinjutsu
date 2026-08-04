"""Every diagnostic reads the same way, whichever check produced it"""

import pytest

from .helpers import warnings_for

# One template per check, so a missing part fails against the check that dropped it
TEMPLATES = [
    "{{ total-discount }}",
    "{% for r in rows %}{{ r.items }}{% endfor %}",
    "{% if archive.keys %}x{% endif %}",
    "{{ name | to_json }}",
    "{% if name is blankk %}x{% endif %}",
    "{% if case.title %}{{ case }}{% endif %}",
    "Title\n{ % if sealed % }SEALED{% endif %}",
    "{% if sealed % }SEALED{% endif %}",
    "Total: {{ amount }",
    "{% for r in rows }",
    "{% x = 1 %}",
    "Report\n{% for r in rows %}\n  {{ r.name }}",
    "Report\n{% if sealed %}\n  SEALED",
    "{% if status = 'FINAL' %}y{% endif %}",
    "Name: {{ a b }}",
    "{% if status == “FINAL” %}y{% endif %}",
    "{% set note %}hello",
    "{{ a.. }}",
    "{{ 3 + }}",
    "{% vm %}",
]


@pytest.mark.parametrize("template", TEMPLATES)
def test_every_diagnostic_has_the_whole_shape(template):
    warnings = warnings_for(template)

    assert warnings, "template was meant to produce a diagnostic"
    for warning in warnings:
        assert warning.startswith("Line "), warning
        for label in ["Source: ", "Found:  ", "Fix:    ", "Reason: "]:
            assert f"\n  {label}" in warning, f"missing {label.strip()} in:\n{warning}"


@pytest.mark.parametrize("template", TEMPLATES)
def test_the_parts_appear_in_a_fixed_order(template):
    for warning in warnings_for(template):
        positions = [warning.index(f"\n  {label}") for label in ["Source: ", "Found:  ", "Fix:    ", "Reason: "]]
        assert positions == sorted(positions), warning


@pytest.mark.parametrize("template", TEMPLATES)
def test_the_source_line_is_quoted_verbatim_from_the_template(template):
    lines = template.split("\n")

    for warning in warnings_for(template):
        line_no = int(warning.split(":", 1)[0].removeprefix("Line "))
        quoted = warning.split("\n  Source: ", 1)[1].split("\n", 1)[0]
        assert quoted == lines[line_no - 1]
