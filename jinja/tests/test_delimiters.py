from conduit.server.features.doj.templates.jinja.tests.helpers import warnings_for


def test_warning_titles_render_jinja_delimiters_literally():
    assert any("Missing closing '%}' in statement tag" in w for w in warnings_for("{% oops }"))
    assert any("Missing closing '}}' in variable tag" in w for w in warnings_for("{{ oops }"))
    assert any(
        "A single '=' only assigns, and only in '{% set %}'" in w
        for w in warnings_for("{% if status = 'FINAL' %}y{% endif %}")
    )
    assert any(
        "Missing closing tag like '{% endfor %}' or '{% endif %}'" in w for w in warnings_for("{% set greeting %}Hello")
    )


def test_transposed_statement_delimiter_is_reported_with_line_number():
    text = "intro\n{if% sales_rep == true %}\nbody\n{%- endif %}"

    warnings = warnings_for(text)

    assert any("Line 2: Misplaced '%' in statement tag" in w for w in warnings)
    assert any("Fix:   {% if sales_rep == true %}" in w for w in warnings)


def test_extra_space_after_brace_is_reported_only_once():
    text = "{ % if alpha %}body{% endif %}"

    warnings = warnings_for(text)

    assert any("Extra space after '{' in tag" in w for w in warnings)
    assert not any("Misplaced '%' in statement tag" in w for w in warnings)


def test_split_opening_brace_is_reported():
    text = "Total: { { amount }} due"

    warnings = warnings_for(text)

    assert any("Line 1: Extra space after '{' in variable tag" in w for w in warnings)
    assert any("Fix:   {{ amount }}" in w for w in warnings)


def test_doubled_opening_delimiter_is_not_offered_a_third_brace():
    text = "{{ {{ name }}"

    warnings = warnings_for(text)

    assert warnings
    assert not any("{{{" in w for w in warnings)


def test_split_braces_on_both_ends_are_reported_with_one_fix():
    text = "{ { amount } }"

    warnings = warnings_for(text)

    assert any("Fix:   {{ amount }}" in w for w in warnings)


def test_extra_space_before_closing_brace_is_reported():
    text = "{% if alpha % }body{% endif %}"

    warnings = warnings_for(text)

    assert any("Line 1: Extra space before '}' in tag" in w for w in warnings)
    assert any("Fix:   {% if alpha %}" in w for w in warnings)


def test_statement_tag_missing_opening_percent_is_reported():
    text = "{ if sales_rep %}body{% endif %}"

    warnings = warnings_for(text)

    assert any("Misplaced '%' in statement tag" in w for w in warnings)


def test_braced_literal_without_jinja_keyword_is_not_reported():
    text = "The fee is {50%} of the total"

    warnings = warnings_for(text)

    assert not warnings


def test_valid_tags_are_not_flagged_as_misplaced_delimiters():
    text = "{% if a %}{{ b }}{%- endif %}{%tr for r in rows %}{{r r.name }}{%tr endfor %}"

    warnings = warnings_for(text)

    assert not warnings


def test_broken_delimiter_does_not_also_report_a_tag_mismatch():
    # The counts can't see an opener they don't recognize, so they would claim 0 {% if %} tags
    for text in ("{ % if x %}y{% endif %}", "{if% if x %}y{% endif %}"):
        warnings = warnings_for(text)

        assert len(warnings) == 1, warnings
        assert not any("Mismatched" in w for w in warnings), text


def test_broken_delimiter_suppresses_the_end_tag_it_orphans():
    # '{ % if x %}' lexes as text, so Jinja blames the {% endif %} four lines below for being alone
    text = "{ % if x %}\nf\nf\nf\n{% endif %}"

    warnings = warnings_for(text)

    assert any("Extra space after '{' in tag" in w for w in warnings)
    assert not any("Line 5" in w for w in warnings)


def test_broken_delimiters_inside_a_comment_are_not_flagged():
    for text in ("{# {{ x } #}", "{# {% if x } #}", "{# { % if x %} #}", "{# {if% x %} #}", "{# { { x }} #}"):
        warnings = warnings_for(text)

        assert not warnings, text


def test_comment_on_the_same_line_does_not_hide_a_real_broken_delimiter():
    text = "{# note #} {{ x }"

    warnings = warnings_for(text)

    assert any("Missing closing '}}' in variable tag" in w for w in warnings)
    # The author sees the line as they wrote it, comment included, not the blanked copy we match against
    assert any(w.endswith(text) for w in warnings)
