from jinjutsu import BooleanNode, ListNode, ObjectNode, StringNode

from .helpers import variables_for


def test_extracts_condition_only_variable_as_boolean():
    text = "{%tc if fy_col_1_visible %}{{ fy_col_1_label }}{%tc endif %}"

    variables = variables_for(text)

    assert variables["fy_col_1_visible"] == BooleanNode()
    assert variables["fy_col_1_label"] == StringNode()


def test_variable_used_in_condition_and_output_is_string():
    text = "{% if status %}{{ status }}{% endif %}"

    variables = variables_for(text)

    assert variables["status"] == StringNode()


def test_comparison_against_literal_is_string_not_boolean():
    text = "{% if phase == 'FINAL' %}done{% endif %}"

    variables = variables_for(text)

    assert variables["phase"] == StringNode()


def test_comparison_against_boolean_literal_is_boolean():
    assert variables_for("{% if sales_rep == true %}x{% endif %}") == {"sales_rep": BooleanNode()}
    assert variables_for("{% if sales_rep == false %}x{% endif %}") == {"sales_rep": BooleanNode()}
    assert variables_for("{% if sales_rep != true %}x{% endif %}") == {"sales_rep": BooleanNode()}


def test_quoted_comparison_against_true_is_string():
    text = "{% if phase == 'true' %}x{% endif %}"

    variables = variables_for(text)

    assert variables["phase"] == StringNode()


def test_comparison_against_number_is_string():
    text = "{% if count == 1 %}x{% endif %}"

    variables = variables_for(text)

    assert variables["count"] == StringNode()


def test_boolean_comparison_on_nested_attribute_is_boolean():
    text = "{% for r in rows %}{% if r.active == true %}{{ r.name }}{% endif %}{% endfor %}"

    variables = variables_for(text)

    assert variables["rows"] == ListNode(
        items=ObjectNode(properties={"active": BooleanNode(), "name": StringNode()}),
    )


def test_guard_on_a_loop_target_makes_a_list_of_booleans():
    text = "{% for flag in flags %}{% if flag %}x{% endif %}{% endfor %}"

    variables = variables_for(text)

    assert variables["flags"] == ListNode(items=BooleanNode())


def test_boolean_comparison_demoted_to_string_when_also_output():
    text = "{% if sales_rep == true %}{{ sales_rep }}{% endif %}"

    variables = variables_for(text)

    assert variables["sales_rep"] == StringNode()


def test_truthiness_guard_refines_into_an_object():
    text = "{% if section %}{{ section.title }}{% endif %}"

    variables = variables_for(text)

    assert variables["section"] == ObjectNode(properties={"title": StringNode()})


def test_boolean_operators_in_condition_extract_boolean_operands():
    assert variables_for("{% if a and b %}x{% endif %}") == {"a": BooleanNode(), "b": BooleanNode()}
    assert variables_for("{% if not hidden %}x{% endif %}") == {"hidden": BooleanNode()}
