from .helpers import variables_for


def test_extracts_condition_only_variable_as_boolean():
    text = "{%tc if fy_col_1_visible %}{{ fy_col_1_label }}{%tc endif %}"

    variables = variables_for(text)

    assert variables["fy_col_1_visible"] == {"type": "boolean"}
    assert variables["fy_col_1_label"] == {"type": "string"}


def test_variable_used_in_condition_and_output_is_string():
    text = "{% if status %}{{ status }}{% endif %}"

    variables = variables_for(text)

    assert variables["status"] == {"type": "string"}


def test_comparison_against_literal_is_string_not_boolean():
    text = "{% if phase == 'FINAL' %}done{% endif %}"

    variables = variables_for(text)

    assert variables["phase"] == {"type": "string"}


def test_comparison_against_boolean_literal_is_boolean():
    assert variables_for("{% if sales_rep == true %}x{% endif %}") == {
        "sales_rep": {"type": "boolean"},
    }
    assert variables_for("{% if sales_rep == false %}x{% endif %}") == {
        "sales_rep": {"type": "boolean"},
    }
    assert variables_for("{% if sales_rep != true %}x{% endif %}") == {
        "sales_rep": {"type": "boolean"},
    }


def test_quoted_comparison_against_true_is_string():
    text = "{% if phase == 'true' %}x{% endif %}"

    variables = variables_for(text)

    assert variables["phase"] == {"type": "string"}


def test_comparison_against_number_is_string():
    text = "{% if count == 1 %}x{% endif %}"

    variables = variables_for(text)

    assert variables["count"] == {"type": "string"}


def test_boolean_comparison_on_nested_attribute_is_boolean():
    text = "{% for r in rows %}{% if r.active == true %}{{ r.name }}{% endif %}{% endfor %}"

    variables = variables_for(text)

    assert variables["rows"] == {
        "type": "list",
        "item_format": "object",
        "properties": {"active": {"type": "boolean"}, "name": {"type": "string"}},
    }


def test_boolean_comparison_demoted_to_string_when_also_output():
    text = "{% if sales_rep == true %}{{ sales_rep }}{% endif %}"

    variables = variables_for(text)

    assert variables["sales_rep"] == {"type": "string"}


def test_truthiness_guard_refines_into_an_object():
    text = "{% if section %}{{ section.title }}{% endif %}"

    variables = variables_for(text)

    assert variables["section"] == {"type": "object", "properties": {"title": {"type": "string"}}}


def test_boolean_operators_in_condition_extract_boolean_operands():
    assert variables_for("{% if a and b %}x{% endif %}") == {
        "a": {"type": "boolean"},
        "b": {"type": "boolean"},
    }
    assert variables_for("{% if not hidden %}x{% endif %}") == {
        "hidden": {"type": "boolean"},
    }
