from .helpers import warnings_for


def test_docxtpl_prefixed_tags_do_not_trip_mismatch_check():
    text = "{%tr for row in funding_rows %}{%tr if row.active %}{{ row.source }}{%tr endif %}{%tr endfor %}"

    warnings = warnings_for(text)

    assert not any("Mismatched" in w for w in warnings)


def test_cell_merge_outside_a_loop_is_reported():
    text = "intro\nApproved {% vm %} by the board"

    warnings = warnings_for(text)

    assert any("Line 2: Cell merge is not inside a loop" in w for w in warnings)
    assert any("Found: {% vm %}" in w for w in warnings)


def test_horizontal_merge_outside_a_loop_is_reported():
    warnings = warnings_for("{% hm %}Total")

    assert any("Cell merge is not inside a loop" in w for w in warnings)


def test_cell_merge_inside_a_docxtpl_loop_is_not_reported():
    text = "{%tr for r in rows %}{% vm %}{% hm %}{{ r.name }}{%tr endfor %}"

    warnings = warnings_for(text)

    assert not warnings


def test_cell_merge_after_a_loop_closes_is_reported():
    text = "{% for r in rows %}{{ r.name }}{% endfor %}\n{% vm %}Total"

    warnings = warnings_for(text)

    assert any("Line 2: Cell merge is not inside a loop" in w for w in warnings)


def test_commented_out_conditional_does_not_trip_mismatch_check():
    text = "{# note: {% if x %} #}{{ y }}"

    warnings = warnings_for(text)

    assert not warnings


def test_whitespace_control_tags_do_not_trip_mismatch_check():
    text = "{%- if flag %}{{ value }}{%- endif %}{%- for row in rows -%}{{ row.name }}{%- endfor -%}"

    warnings = warnings_for(text)

    assert not warnings


def test_unclosed_loop_is_reported_as_a_loop_mismatch():
    text = "{% for row in rows %}{{ row.name }}"

    warnings = warnings_for(text)

    assert any("1 {% for %} tag(s) but 0 {% endfor %} tag(s)" in w for w in warnings)


def test_tag_mismatch_does_not_hide_an_unrelated_syntax_error():
    text = "{% for row in rows %}{{ row.name }}\n{% if a b c %}x{% endif %}"

    warnings = warnings_for(text)

    assert any("{% endfor %} tag(s)" in w for w in warnings)
    assert any("Unexpected 'b' after the expression" in w for w in warnings)


def test_tag_mismatch_absorbs_the_syntax_error_that_only_restates_it():
    for text in ("{% for row in rows %}{{ row.name }}", "{% if x %}yes", "{% endif %}", "{% endfor %}"):
        warnings = warnings_for(text)

        assert not any("Missing closing tag" in w for w in warnings), text
        assert not any("Check for typos" in w for w in warnings), text


def test_whitespace_control_tags_are_counted_in_mismatch_check():
    text = "{%- if flag %}{{ value }}"

    warnings = warnings_for(text)

    assert any("1 {% if %} tag(s) but 0 {% endif %} tag(s)" in w for w in warnings)
