from conduit.server.features.doj.templates.validation import validate_template_jinja


def test_docxtpl_prefixed_tags_do_not_trip_mismatch_check():
    text = "{%tr for row in funding_rows %}{%tr if row.active %}{{ row.source }}{%tr endif %}{%tr endfor %}"

    warnings = validate_template_jinja(text)

    assert not any("Mismatched" in w for w in warnings)


def test_docxtpl_paragraph_conditional_is_not_a_syntax_error():
    text = "{%p if strategic_requirement_1 or strategic_requirement_2 %}{{ strategic_requirement_1 }}{%p endif %}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_docxtpl_prefixed_variable_is_not_a_syntax_error():
    text = "{{r rich_text_field }}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_whitespace_control_tags_do_not_trip_mismatch_check():
    text = "{%- if flag %}{{ value }}{%- endif %}{%- for row in rows -%}{{ row.name }}{%- endfor -%}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_transposed_statement_delimiter_is_reported_with_line_number():
    text = "intro\n{if% sales_rep == true %}\nbody\n{%- endif %}"

    warnings = validate_template_jinja(text)

    assert any("Line 2: Misplaced '%' in statement tag" in w for w in warnings)
    assert any("Fix:   {% if sales_rep == true %}" in w for w in warnings)


def test_extra_space_after_brace_is_reported_only_once():
    text = "{ % if alpha %}body{% endif %}"

    warnings = validate_template_jinja(text)

    assert any("Extra space after '{' in tag" in w for w in warnings)
    assert not any("Misplaced '%' in statement tag" in w for w in warnings)


def test_statement_tag_missing_opening_percent_is_reported():
    text = "{ if sales_rep %}body{% endif %}"

    warnings = validate_template_jinja(text)

    assert any("Misplaced '%' in statement tag" in w for w in warnings)


def test_braced_literal_without_jinja_keyword_is_not_reported():
    text = "The fee is {50%} of the total"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_valid_tags_are_not_flagged_as_misplaced_delimiters():
    text = "{% if a %}{{ b }}{%- endif %}{%tr for r in rows %}{{r r.name }}{%tr endfor %}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_dict_method_field_is_reported_with_bracket_fix():
    text = "Recipients:\n{% for r in rows %}{{ r.items }}{% endfor %}"

    warnings = validate_template_jinja(text)

    assert any("Line 2: Field 'items' collides with a built-in dict method" in w for w in warnings)
    assert any("Fix:   {{ r['items'] }}" in w for w in warnings)


def test_explicit_dict_method_call_is_not_reported():
    text = "{% for k, v in mapping.items() %}{{ k }}{{ v }}{% endfor %}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_dict_method_name_outside_a_tag_is_not_reported():
    text = "See r.items in the appendix and obj.values in Exhibit B"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_bracket_access_to_dict_method_name_is_not_reported():
    text = "{{ r['items'] }}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_ordinary_field_names_are_not_reported():
    text = "{% for r in rows %}{{ r.name }}{{ r.title }}{% endfor %}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_dict_method_field_does_not_suppress_syntax_errors():
    text = "{{ r.items }}\n{if% sales_rep == true %}"

    warnings = validate_template_jinja(text)

    assert any("Misplaced '%' in statement tag" in w for w in warnings)
    assert any("collides with a built-in dict method" in w for w in warnings)


def test_whitespace_control_tags_are_counted_in_mismatch_check():
    text = "{%- if flag %}{{ value }}"

    warnings = validate_template_jinja(text)

    assert any("1 {% if %} tag(s) but 0 {% endif %} tag(s)" in w for w in warnings)
