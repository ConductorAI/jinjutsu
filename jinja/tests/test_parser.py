from conduit.server.features.doj.templates.jinja.tests.helpers import warnings_for


def test_single_equals_in_a_condition_suggests_the_comparison_operator():
    warnings = warnings_for("{% if status = 'FINAL' %}y{% endif %}")

    assert any("Use '==' to compare" in w for w in warnings)


def test_comparison_operator_is_not_reported():
    warnings = warnings_for("{% if status == 'FINAL' %}y{% endif %}")

    assert not warnings


def test_curly_double_quote_from_word_is_named():
    warnings = warnings_for("{% if status == “FINAL” %}y{% endif %}")

    assert any("is a curly quote, which Word substitutes as you type" in w for w in warnings)
    assert any("“" in w for w in warnings)


def test_curly_single_quote_from_word_is_named():
    warnings = warnings_for("{% if status == ‘FINAL’ %}y{% endif %}")

    assert any("is a curly quote, which Word substitutes as you type" in w for w in warnings)


def test_straight_quotes_are_not_reported():
    warnings = warnings_for("{% if status == 'FINAL' %}y{% endif %}{{ note == \"x\" }}")

    assert not warnings


def test_leftover_token_in_a_tag_names_the_token():
    warnings = warnings_for("{% if a b c %}x{% endif %}")

    assert any("Unexpected 'b' after the expression" in w for w in warnings)


def test_invalid_name_after_a_dot_reports_the_variable_name_guidance():
    text = "{{ a. }}"

    warnings = warnings_for(text)

    assert any("Invalid variable name in '{{ }}' or '{% %}' tag" in w for w in warnings)


def test_docxtpl_paragraph_conditional_is_not_a_syntax_error():
    text = "{%p if strategic_requirement_1 or strategic_requirement_2 %}{{ strategic_requirement_1 }}{%p endif %}"

    warnings = warnings_for(text)

    assert not warnings


def test_docxtpl_prefixed_variable_is_not_a_syntax_error():
    text = "{{r rich_text_field }}"

    warnings = warnings_for(text)

    assert not warnings


def test_docxtpl_table_tags_are_not_syntax_errors():
    text = (
        "{%tr for r in rows %}{% vm %}{% hm %}{% colspan col_count %}{% cellbg row_color %}{{ r.name }}{%tr endfor %}"
    )

    warnings = warnings_for(text)

    assert not warnings


def test_commented_out_tags_are_not_validated():
    text = "{# old: {{ r.items }} and {{ fiscal-year }} and {% vm %} #}{{ r.name }}"

    warnings = warnings_for(text)

    assert not warnings
