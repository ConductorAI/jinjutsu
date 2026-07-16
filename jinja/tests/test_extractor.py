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
