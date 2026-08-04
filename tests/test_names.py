from .helpers import warnings_for


def test_builtin_method_field_is_reported_with_bracket_fix():
    text = "Recipients:\n{% for r in rows %}{{ r.items }}{% endfor %}"

    warnings = warnings_for(text)

    assert any("Line 2: Field 'items' collides with a built-in method" in w for w in warnings)
    assert any("Fix:    {{ r['items'] }}" in w for w in warnings)


def test_list_method_field_is_reported_with_bracket_fix():
    text = "{% for r in rows %}{{ r.count }}{% endfor %}"

    warnings = warnings_for(text)

    assert any("Field 'count' collides with a built-in method" in w for w in warnings)
    assert any("Fix:    {{ r['count'] }}" in w for w in warnings)


def test_explicit_list_method_call_is_not_reported():
    text = "{% for r in rows.copy() %}{{ r.name }}{% endfor %}"

    warnings = warnings_for(text)

    assert not warnings


def test_field_name_merely_starting_with_a_method_name_is_not_reported():
    text = "{{ a.counterparty }} {{ b.indexed_at }} {{ c.sorting_code }}"

    warnings = warnings_for(text)

    assert not warnings


def test_explicit_dict_method_call_is_not_reported():
    text = "{% for k, v in mapping.items() %}{{ k }}{{ v }}{% endfor %}"

    warnings = warnings_for(text)

    assert not warnings


def test_builtin_method_name_outside_a_tag_is_not_reported():
    text = "See r.items in the appendix and obj.values in Exhibit B"

    warnings = warnings_for(text)

    assert not warnings


def test_bracket_access_to_dict_method_name_is_not_reported():
    text = "{{ r['items'] }}"

    warnings = warnings_for(text)

    assert not warnings


def test_builtin_method_name_inside_a_string_literal_is_not_reported():
    text = '{{ "see section.items here" }}'

    warnings = warnings_for(text)

    assert not warnings


def test_two_different_dict_method_fields_in_a_tag_are_one_warning():
    text = "{{ a.items if flag else b.values }}"

    warnings = warnings_for(text)

    assert len(warnings) == 1
    assert "Fields 'items' and 'values' collide with built-in methods" in warnings[0]
    assert "Fix:    {{ a['items'] if flag else b['values'] }}" in warnings[0]


def test_escaped_quote_inside_a_literal_does_not_leak_code_out_of_it():
    text = r"{{ x if 'John\'s r.keys' else y }}"

    assert not warnings_for(text)


def test_escaped_quote_inside_a_literal_does_not_swallow_a_real_collision():
    text = r"{{ 'John\'s' ~ r.items ~ 'x' }}"

    warnings = warnings_for(text)

    assert any("Field 'items' collides with a built-in method" in w for w in warnings)


def test_numeric_subtraction_is_not_flagged_as_a_hyphenated_variable():
    text = "{{ 2024-1 }} and {{ 1.5-0.5 }}"

    warnings = warnings_for(text)

    assert not warnings


def test_numeric_subtraction_leaves_a_real_syntax_error_intact():
    # Jinja rejects the leading zero in '01' on its own
    # We only suppress the rename suggestion
    text = "{{ 2024-01 }}"

    warnings = warnings_for(text)

    assert not any("hyphen" in w for w in warnings)
    assert any("expected token 'end of print statement'" in w for w in warnings)


def test_hyphen_warning_does_not_hide_a_syntax_error():
    text = "{{ fiscal-year }}\n{% set g %}Hello"

    warnings = warnings_for(text)

    assert any("Variable name contains hyphen(s)" in w for w in warnings)
    assert any("Missing closing tag" in w for w in warnings)


def test_hyphenated_variable_name_is_still_flagged():
    text = "{{ fiscal-year }}"

    warnings = warnings_for(text)

    assert any("Variable name contains hyphen(s)" in w for w in warnings)


def test_hyphen_warning_offers_a_spaced_form_that_clears_it():
    warnings = warnings_for("{{ total-discount }}")

    assert any("write total - discount with spaces" in w for w in warnings)
    assert not warnings_for("{{ total - discount }}")


def test_hyphenated_name_inside_a_statement_tag_is_flagged():
    warnings = warnings_for("{% if fiscal-year %}x{% endif %}")

    assert any("Variable name contains hyphen(s)" in w for w in warnings)
    assert any("Fix:    fiscal_year" in w for w in warnings)


def test_hyphenated_loop_source_is_flagged():
    warnings = warnings_for("{% for r in funding-rows %}{{ r.name }}{% endfor %}")

    assert any("Found:  funding-rows" in w for w in warnings)


def test_hyphen_inside_a_string_literal_is_not_flagged():
    text = "{% if scope == 'fiscal-year' %}x{% endif %}"

    warnings = warnings_for(text)

    assert not warnings


def test_ordinary_field_names_are_not_reported():
    text = "{% for r in rows %}{{ r.name }}{{ r.title }}{% endfor %}"

    warnings = warnings_for(text)

    assert not warnings


def test_builtin_method_field_does_not_suppress_syntax_errors():
    text = "{{ r.items }}\n{if% sales_rep == true %}"

    warnings = warnings_for(text)

    assert any("Misplaced '%' in statement tag" in w for w in warnings)
    assert any("collides with a built-in method" in w for w in warnings)


def test_a_real_collision_after_a_comment_is_still_reported():
    text = "{# old: {{ a.keys }} #}\n{{ r.items }}"

    warnings = warnings_for(text)

    assert any("Line 2: Field 'items' collides with a built-in method" in w for w in warnings)
    assert not any("Field 'keys'" in w for w in warnings)


def test_the_same_bad_name_twice_on_one_line_warns_once():
    # The UI keys each warning by its text, so byte-identical duplicates cannot both be shown
    text = "{{ a-b }} and {{ a-b }}"

    assert len(warnings_for(text)) == 1, warnings_for(text)


def test_the_same_bad_name_on_two_lines_warns_twice():
    text = "{{ a-b }}\n{{ a-b }}"

    assert len(warnings_for(text)) == 2, warnings_for(text)


def test_a_collision_in_a_print_tag_says_the_method_renders():
    warnings = warnings_for("{{ archive.keys }}")

    assert any("renders the method instead of your value" in w for w in warnings)


def test_a_collision_in_a_loop_says_the_render_fails_rather_than_renders():
    warnings = warnings_for("{% for entry in archive.keys %}{{ entry }}{% endfor %}")

    assert any("the render fails, leaving no document" in w for w in warnings)
    assert not any("renders the method instead of your value" in w for w in warnings)


def test_a_collision_in_a_condition_says_the_test_always_passes():
    warnings = warnings_for("{% if archive.keys %}SEALED{% endif %}")

    assert any("the test passes whatever your data holds" in w for w in warnings)
    assert not any("renders the method instead of your value" in w for w in warnings)


def test_an_elif_collision_is_described_as_a_condition():
    warnings = warnings_for("{% if a %}x{% elif archive.keys %}y{% endif %}")

    assert any("the test passes whatever your data holds" in w for w in warnings)


def test_a_collision_in_a_set_tag_falls_back_to_the_printed_symptom():
    warnings = warnings_for("{% set k = archive.keys %}{{ k }}")

    assert any("renders the method instead of your value" in w for w in warnings)


def test_two_collisions_in_one_loop_tag_read_as_plural():
    warnings = warnings_for("{% for e in archive.keys if archive.values %}{{ e }}{% endfor %}")

    assert any("Fields 'keys' and 'values' collide" in w for w in warnings)
    assert any("iterate a method instead of your list" in w for w in warnings)
