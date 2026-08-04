from jinjutsu.shapes import BooleanNode, ListNode, NumberNode, ObjectNode, StringNode

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


def test_operators_a_string_cannot_survive_make_a_number():
    for text in ("{{ v - 1 }}", "{{ v / 2 }}", "{{ v // 2 }}", "{{ v ** 2 }}", "{{ -v }}"):
        assert variables_for(text) == {"v": NumberNode()}, text


def test_multiplication_makes_every_operand_a_number():
    # "a" * "b" raises, so both operands being strings is not a reading that exists
    assert variables_for("{{ a * b }}") == {"a": NumberNode(), "b": NumberNode()}
    assert variables_for("{{ v * 2 }}") == {"v": NumberNode()}


def test_a_repeated_string_literal_makes_its_count_a_number():
    assert variables_for('{{ "-" * width }}') == {"width": NumberNode()}
    assert variables_for('{{ width * "-" }}') == {"width": NumberNode()}


def test_ambiguous_operators_need_a_numeric_literal_to_mean_arithmetic():
    assert variables_for("{{ v + 1 }}") == {"v": NumberNode()}
    assert variables_for("{{ v % 2 }}") == {"v": NumberNode()}


def test_ambiguous_operators_on_two_names_stay_strings():
    # {{ a + b }} is as likely to be concatenation, and {{ a % b }} printf, so neither is claimed
    assert variables_for("{{ a + b }}") == {"a": StringNode(), "b": StringNode()}
    assert variables_for("{{ a % b }}") == {"a": StringNode(), "b": StringNode()}


def test_a_string_literal_operand_keeps_the_other_side_a_string():
    assert variables_for('{{ v + "x" }}') == {"v": StringNode()}
    assert variables_for('{{ "%s" % v }}') == {"v": StringNode()}


def test_the_explicit_concat_operator_is_not_arithmetic():
    assert variables_for("{{ v ~ w }}") == {"v": StringNode(), "w": StringNode()}


def test_ordered_comparison_against_a_number_is_a_number():
    assert variables_for("{% if v > 5 %}x{% endif %}") == {"v": NumberNode()}
    assert variables_for("{% if 5 < v %}x{% endif %}") == {"v": NumberNode()}


def test_ordered_comparison_without_a_numeric_literal_stays_a_string():
    # strings compare lexicographically, so neither of these says anything about shape
    assert variables_for("{% if v > w %}x{% endif %}") == {"v": StringNode(), "w": StringNode()}
    assert variables_for('{% if v > "m" %}x{% endif %}') == {"v": StringNode()}


def test_arithmetic_wins_over_being_printed_or_guarded():
    assert variables_for("{{ v }}{{ v - 1 }}") == {"v": NumberNode()}
    assert variables_for("{{ v - 1 }}{{ v }}") == {"v": NumberNode()}
    assert variables_for("{% if v %}{{ v - 1 }}{% endif %}") == {"v": NumberNode()}


def test_arithmetic_types_a_field_at_any_depth():
    text = "{% for r in rows %}{{ r.n * 2 }}{% endfor %}"

    assert variables_for(text) == {"rows": ListNode(items=ObjectNode(properties={"n": NumberNode()}))}


def test_arithmetic_nested_inside_a_comparison_is_still_read():
    assert variables_for("{% if count + 1 > 5 %}x{% endif %}") == {"count": NumberNode()}


def test_arithmetic_does_not_overwrite_a_container():
    text = "{{ a.b }}{{ a + 1 }}"

    assert variables_for(text) == {"a": ObjectNode(properties={"b": StringNode()})}


def test_boolean_operators_in_condition_extract_boolean_operands():
    assert variables_for("{% if a and b %}x{% endif %}") == {"a": BooleanNode(), "b": BooleanNode()}
    assert variables_for("{% if not hidden %}x{% endif %}") == {"hidden": BooleanNode()}
