from conduit.server.features.doj.templates.validation import validate_template_jinja


def test_warning_titles_render_jinja_delimiters_literally():
    assert any("Missing closing '%}' in statement tag" in w for w in validate_template_jinja("{% oops }"))
    assert any("Missing closing '}}' in variable tag" in w for w in validate_template_jinja("{{ oops }"))
    assert any(
        "A single '=' only assigns, and only in '{% set %}'" in w
        for w in validate_template_jinja("{% if status = 'FINAL' %}y{% endif %}")
    )
    assert any(
        "Missing closing tag like '{% endfor %}' or '{% endif %}'" in w
        for w in validate_template_jinja("{% set greeting %}Hello")
    )


def test_single_equals_in_a_condition_suggests_the_comparison_operator():
    warnings = validate_template_jinja("{% if status = 'FINAL' %}y{% endif %}")

    assert any("Use '==' to compare" in w for w in warnings)


def test_comparison_operator_is_not_reported():
    warnings = validate_template_jinja("{% if status == 'FINAL' %}y{% endif %}")

    assert not warnings


def test_curly_double_quote_from_word_is_named():
    warnings = validate_template_jinja("{% if status == “FINAL” %}y{% endif %}")

    assert any("is a curly quote, which Word substitutes as you type" in w for w in warnings)
    assert any("“" in w for w in warnings)


def test_curly_single_quote_from_word_is_named():
    warnings = validate_template_jinja("{% if status == ‘FINAL’ %}y{% endif %}")

    assert any("is a curly quote, which Word substitutes as you type" in w for w in warnings)


def test_straight_quotes_are_not_reported():
    warnings = validate_template_jinja("{% if status == 'FINAL' %}y{% endif %}{{ note == \"x\" }}")

    assert not warnings


def test_leftover_token_in_a_tag_names_the_token():
    warnings = validate_template_jinja("{% if a b c %}x{% endif %}")

    assert any("Unexpected 'b' after the expression" in w for w in warnings)


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


def test_docxtpl_table_tags_are_not_syntax_errors():
    text = (
        "{%tr for r in rows %}{% vm %}{% hm %}{% colspan col_count %}{% cellbg row_color %}{{ r.name }}{%tr endfor %}"
    )

    warnings = validate_template_jinja(text)

    assert not warnings


def test_cell_merge_outside_a_loop_is_reported():
    text = "intro\nApproved {% vm %} by the board"

    warnings = validate_template_jinja(text)

    assert any("Line 2: Cell merge is not inside a loop" in w for w in warnings)
    assert any("Found: {% vm %}" in w for w in warnings)


def test_horizontal_merge_outside_a_loop_is_reported():
    warnings = validate_template_jinja("{% hm %}Total")

    assert any("Cell merge is not inside a loop" in w for w in warnings)


def test_cell_merge_inside_a_docxtpl_loop_is_not_reported():
    text = "{%tr for r in rows %}{% vm %}{% hm %}{{ r.name }}{%tr endfor %}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_cell_merge_after_a_loop_closes_is_reported():
    text = "{% for r in rows %}{{ r.name }}{% endfor %}\n{% vm %}Total"

    warnings = validate_template_jinja(text)

    assert any("Line 2: Cell merge is not inside a loop" in w for w in warnings)


def test_commented_out_tags_are_not_validated():
    text = "{# old: {{ r.items }} and {{ fiscal-year }} and {% vm %} #}{{ r.name }}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_commented_out_conditional_does_not_trip_mismatch_check():
    text = "{# note: {% if x %} #}{{ y }}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_a_real_collision_after_a_comment_is_still_reported():
    text = "{# old: {{ a.keys }} #}\n{{ r.items }}"

    warnings = validate_template_jinja(text)

    assert any("Line 2: Field 'items' collides with a built-in method" in w for w in warnings)
    assert not any("Field 'keys'" in w for w in warnings)


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


def test_split_opening_brace_is_reported():
    text = "Total: { { amount }} due"

    warnings = validate_template_jinja(text)

    assert any("Line 1: Extra space after '{' in variable tag" in w for w in warnings)
    assert any("Fix:   {{ amount }}" in w for w in warnings)


def test_doubled_opening_delimiter_is_not_offered_a_third_brace():
    text = "{{ {{ name }}"

    warnings = validate_template_jinja(text)

    assert warnings
    assert not any("{{{" in w for w in warnings)


def test_split_braces_on_both_ends_are_reported_with_one_fix():
    text = "{ { amount } }"

    warnings = validate_template_jinja(text)

    assert any("Fix:   {{ amount }}" in w for w in warnings)


def test_extra_space_before_closing_brace_is_reported():
    text = "{% if alpha % }body{% endif %}"

    warnings = validate_template_jinja(text)

    assert any("Line 1: Extra space before '}' in tag" in w for w in warnings)
    assert any("Fix:   {% if alpha %}" in w for w in warnings)


def test_unclosed_loop_is_reported_as_a_loop_mismatch():
    text = "{% for row in rows %}{{ row.name }}"

    warnings = validate_template_jinja(text)

    assert any("1 {% for %} tag(s) but 0 {% endfor %} tag(s)" in w for w in warnings)


def test_tag_mismatch_does_not_hide_an_unrelated_syntax_error():
    text = "{% for row in rows %}{{ row.name }}\n{% if a b c %}x{% endif %}"

    warnings = validate_template_jinja(text)

    assert any("{% endfor %} tag(s)" in w for w in warnings)
    assert any("Unexpected 'b' after the expression" in w for w in warnings)


def test_tag_mismatch_absorbs_the_syntax_error_that_only_restates_it():
    for text in ("{% for row in rows %}{{ row.name }}", "{% if x %}yes", "{% endif %}", "{% endfor %}"):
        warnings = validate_template_jinja(text)

        assert not any("Missing closing tag" in w for w in warnings), text
        assert not any("Check for typos" in w for w in warnings), text


def test_broken_delimiter_suppresses_the_end_tag_it_orphans():
    # '{ % if x %}' lexes as text, so Jinja blames the {% endif %} four lines below for being alone
    text = "{ % if x %}\nf\nf\nf\n{% endif %}"

    warnings = validate_template_jinja(text)

    assert any("Extra space after '{' in tag" in w for w in warnings)
    assert not any("Line 5" in w for w in warnings)


def test_invalid_name_after_a_dot_reports_the_variable_name_guidance():
    text = "{{ a. }}"

    warnings = validate_template_jinja(text)

    assert any("Invalid variable name in '{{ }}' or '{% %}' tag" in w for w in warnings)


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


def test_builtin_method_field_is_reported_with_bracket_fix():
    text = "Recipients:\n{% for r in rows %}{{ r.items }}{% endfor %}"

    warnings = validate_template_jinja(text)

    assert any("Line 2: Field 'items' collides with a built-in method" in w for w in warnings)
    assert any("Fix:   {{ r['items'] }}" in w for w in warnings)


def test_list_method_field_is_reported_with_bracket_fix():
    text = "{% for r in rows %}{{ r.count }}{% endfor %}"

    warnings = validate_template_jinja(text)

    assert any("Field 'count' collides with a built-in method" in w for w in warnings)
    assert any("Fix:   {{ r['count'] }}" in w for w in warnings)


def test_explicit_list_method_call_is_not_reported():
    text = "{% for r in rows.copy() %}{{ r.name }}{% endfor %}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_field_name_merely_starting_with_a_method_name_is_not_reported():
    text = "{{ a.counterparty }} {{ b.indexed_at }} {{ c.sorting_code }}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_explicit_dict_method_call_is_not_reported():
    text = "{% for k, v in mapping.items() %}{{ k }}{{ v }}{% endfor %}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_builtin_method_name_outside_a_tag_is_not_reported():
    text = "See r.items in the appendix and obj.values in Exhibit B"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_bracket_access_to_dict_method_name_is_not_reported():
    text = "{{ r['items'] }}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_builtin_method_name_inside_a_string_literal_is_not_reported():
    text = '{{ "see section.items here" }}'

    warnings = validate_template_jinja(text)

    assert not warnings


def test_two_different_dict_method_fields_in_a_tag_are_one_warning():
    text = "{{ a.items if flag else b.values }}"

    warnings = validate_template_jinja(text)

    assert len(warnings) == 1
    assert "Fields 'items' and 'values' collide with built-in methods" in warnings[0]
    assert "Fix:   {{ a['items'] if flag else b['values'] }}" in warnings[0]


def test_escaped_quote_inside_a_literal_does_not_leak_code_out_of_it():
    text = r"{{ x if 'John\'s r.keys' else y }}"

    assert not validate_template_jinja(text)


def test_escaped_quote_inside_a_literal_does_not_swallow_a_real_collision():
    text = r"{{ 'John\'s' ~ r.items ~ 'x' }}"

    warnings = validate_template_jinja(text)

    assert any("Field 'items' collides with a built-in method" in w for w in warnings)


def test_numeric_subtraction_is_not_flagged_as_a_hyphenated_variable():
    text = "{{ 2024-1 }} and {{ 1.5-0.5 }}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_numeric_subtraction_leaves_a_real_syntax_error_intact():
    # Jinja rejects the leading zero in '01' on its own. Only the rename suggestion is suppressed.
    text = "{{ 2024-01 }}"

    warnings = validate_template_jinja(text)

    assert not any("hyphen" in w for w in warnings)
    assert any("Error: expected token 'end of print statement'" in w for w in warnings)


def test_hyphen_warning_does_not_hide_a_syntax_error():
    text = "{{ fiscal-year }}\n{% set g %}Hello"

    warnings = validate_template_jinja(text)

    assert any("Variable name contains hyphen(s)" in w for w in warnings)
    assert any("Missing closing tag" in w for w in warnings)


def test_hyphenated_variable_name_is_still_flagged():
    text = "{{ fiscal-year }}"

    warnings = validate_template_jinja(text)

    assert any("Variable name contains hyphen(s)" in w for w in warnings)


def test_hyphen_warning_offers_a_spaced_form_that_clears_it():
    warnings = validate_template_jinja("{{ total-discount }}")

    assert any("write total - discount with spaces" in w for w in warnings)
    assert not validate_template_jinja("{{ total - discount }}")


def test_hyphenated_name_inside_a_statement_tag_is_flagged():
    warnings = validate_template_jinja("{% if fiscal-year %}x{% endif %}")

    assert any("Variable name contains hyphen(s)" in w for w in warnings)
    assert any("Fix:   fiscal_year" in w for w in warnings)


def test_hyphenated_loop_source_is_flagged():
    warnings = validate_template_jinja("{% for r in funding-rows %}{{ r.name }}{% endfor %}")

    assert any("Found: funding-rows" in w for w in warnings)


def test_hyphen_inside_a_string_literal_is_not_flagged():
    text = "{% if scope == 'fiscal-year' %}x{% endif %}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_ordinary_field_names_are_not_reported():
    text = "{% for r in rows %}{{ r.name }}{{ r.title }}{% endfor %}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_builtin_method_field_does_not_suppress_syntax_errors():
    text = "{{ r.items }}\n{if% sales_rep == true %}"

    warnings = validate_template_jinja(text)

    assert any("Misplaced '%' in statement tag" in w for w in warnings)
    assert any("collides with a built-in method" in w for w in warnings)


def test_whitespace_control_tags_are_counted_in_mismatch_check():
    text = "{%- if flag %}{{ value }}"

    warnings = validate_template_jinja(text)

    assert any("1 {% if %} tag(s) but 0 {% endif %} tag(s)" in w for w in warnings)
