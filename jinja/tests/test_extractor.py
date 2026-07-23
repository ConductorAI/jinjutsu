from conduit.server.features.doj.templates.extractor import (
    extract_template_variables,
    validate_template_jinja,
)


def test_extracts_docxtpl_tr_loop_variable():
    text = "{%tr for row in funding_rows %}{{ row.source }}{%tr endfor %}"

    variables = extract_template_variables(text)

    assert "funding_rows" in variables
    assert variables["funding_rows"]["type"] == "list"
    assert variables["funding_rows"]["properties"]["source"] == {"type": "string"}


def test_extracts_all_docxtpl_loop_prefixes():
    for prefix in ("tr", "tc", "p", "r"):
        text = f"{{%{prefix} for item in items %}}{{{{ item.name }}}}{{%{prefix} endfor %}}"

        variables = extract_template_variables(text)

        assert "items" in variables, prefix


def test_plain_for_loop_still_extracted():
    text = "{% for row in rows %}{{ row.value }}{% endfor %}"

    variables = extract_template_variables(text)

    assert "rows" in variables


def test_docxtpl_prefixed_tags_do_not_trip_mismatch_check():
    text = "{%tr for row in funding_rows %}{%tr if row.active %}{{ row.source }}{%tr endif %}{%tr endfor %}"

    warnings = validate_template_jinja(text)

    assert not any("Mismatched" in w for w in warnings)


def test_docxtpl_paragraph_conditional_is_not_a_syntax_error():
    text = "{%p if strategic_requirement_1 or strategic_requirement_2 %}{{ strategic_requirement_1 }}{%p endif %}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_extracts_docxtpl_prefixed_variable():
    text = "{{r rich_text_field }}"

    variables = extract_template_variables(text)

    assert "rich_text_field" in variables


def test_docxtpl_prefixed_variable_is_not_a_syntax_error():
    text = "{{r rich_text_field }}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_plain_variable_still_extracted():
    text = "{{ plain_var }}"

    variables = extract_template_variables(text)

    assert "plain_var" in variables


def test_extracts_condition_only_variable_as_boolean():
    text = "{%tc if fy_col_1_visible %}{{ fy_col_1_label }}{%tc endif %}"

    variables = extract_template_variables(text)

    assert variables["fy_col_1_visible"] == {"type": "boolean"}
    assert variables["fy_col_1_label"] == {"type": "string"}


def test_variable_used_in_condition_and_output_is_string():
    text = "{% if status %}{{ status }}{% endif %}"

    variables = extract_template_variables(text)

    assert variables["status"] == {"type": "string"}


def test_comparison_against_literal_is_string_not_boolean():
    text = "{% if phase == 'FINAL' %}done{% endif %}"

    variables = extract_template_variables(text)

    assert variables["phase"] == {"type": "string"}


def test_top_level_object_access_builds_nested_object():
    text = "{{ section.header.title }}"

    variables = extract_template_variables(text)

    assert variables["section"] == {
        "type": "object",
        "properties": {
            "header": {"type": "object", "properties": {"title": {"type": "string"}}},
        },
    }


def test_extracts_ternary_and_filter_argument_variables():
    text = "{{ value if show_it else fallback }}{{ price | default(fallback_price) }}"

    variables = extract_template_variables(text)

    assert variables["show_it"] == {"type": "boolean"}
    assert set(variables) == {"value", "show_it", "fallback", "price", "fallback_price"}


def test_loop_locals_and_set_targets_are_not_extracted():
    text = "{% for k, v in mapping %}{{ k }}{{ v }}{% endfor %}{% set total = a + b %}{{ total }}"

    variables = extract_template_variables(text)

    assert set(variables) == {"mapping", "a", "b"}


def test_commented_out_variables_are_ignored():
    text = "{# {{ commented_out }} #}{{ real_var }}"

    variables = extract_template_variables(text)

    assert set(variables) == {"real_var"}


def test_malformed_template_falls_back_to_best_effort_extraction():
    text = "{% for row in funding_rows %}{{ row.source }}"

    variables = extract_template_variables(text)

    assert "funding_rows" in variables
