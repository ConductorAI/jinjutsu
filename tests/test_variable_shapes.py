from jinjutsu.types import ListNode, ObjectNode, StringNode, UnknownNode

from .helpers import variables_for


def test_indexed_access_builds_list_of_objects():
    text = "{{ items[0].name }}"

    variables = variables_for(text)

    assert variables["items"] == ListNode(items=ObjectNode(properties={"name": StringNode()}))


def test_dot_number_access_builds_list_of_objects():
    text = "{{ items.0.name }}"

    variables = variables_for(text)

    assert variables["items"] == ListNode(items=ObjectNode(properties={"name": StringNode()}))


def test_bare_indexed_access_is_list_of_strings():
    text = "{{ items[0] }}"

    variables = variables_for(text)

    assert variables["items"] == ListNode(items=StringNode())


def test_indexed_access_nested_under_object():
    text = "{{ a.b[0].c }}"

    variables = variables_for(text)

    assert variables["a"] == ObjectNode(
        properties={"b": ListNode(items=ObjectNode(properties={"c": StringNode()}))},
    )


def test_repeated_subscript_builds_a_list_of_lists():
    text = "{{ matrix[0][1] }}"

    variables = variables_for(text)

    assert variables["matrix"] == ListNode(items=ListNode(items=StringNode()))


def test_nested_loop_over_the_loop_target_builds_a_list_of_lists():
    text = "{% for row in grid %}{% for cell in row %}{{ cell }}{% endfor %}{% endfor %}"

    variables = variables_for(text)

    assert variables["grid"] == ListNode(items=ListNode(items=StringNode()))


def test_loop_target_never_used_leaves_its_element_unknown():
    text = "{% for x in xs %}body{% endfor %}"

    variables = variables_for(text)

    assert variables["xs"] == ListNode(items=UnknownNode())


def test_string_subscript_is_a_property_not_an_index():
    text = "{{ r['items'] }}"

    variables = variables_for(text)

    assert variables["r"] == ObjectNode(properties={"items": StringNode()})


def test_string_subscript_is_never_mistaken_for_an_index_marker():
    text = "{{ r['[]'] }}"

    variables = variables_for(text)

    assert variables["r"] == ObjectNode(properties={"[]": StringNode()})


def test_indexed_access_merges_with_loop_over_same_list():
    text = "{{ items[0].name }}{% for i in items %}{{ i.other }}{% endfor %}"

    variables = variables_for(text)

    assert variables["items"] == ListNode(
        items=ObjectNode(properties={"name": StringNode(), "other": StringNode()}),
    )


def test_dynamic_subscript_is_not_resolved():
    text = "{{ items[i] }}"

    variables = variables_for(text)

    assert set(variables) == {"items", "i"}
    assert variables["items"] == StringNode()


def test_top_level_object_access_builds_nested_object():
    text = "{{ section.header.title }}"

    variables = variables_for(text)

    assert variables["section"] == ObjectNode(
        properties={"header": ObjectNode(properties={"title": StringNode()})},
    )


def test_nested_loops_build_nested_list_of_objects():
    text = "{% for s in sections %}{{ s.title }}{% for a in s.authorized %}{{ a.name }}{% endfor %}{% endfor %}"

    variables = variables_for(text)

    assert variables["sections"] == ListNode(
        items=ObjectNode(
            properties={
                "title": StringNode(),
                "authorized": ListNode(items=ObjectNode(properties={"name": StringNode()})),
            },
        ),
    )


def test_filtered_iterable_is_still_a_list():
    text = "{% for x in items | sort %}{{ x.name }}{% endfor %}"

    variables = variables_for(text)

    assert variables["items"] == ListNode(items=ObjectNode(properties={"name": StringNode()}))


def test_filter_arguments_are_still_extracted():
    text = "{% for row in rows | batch(columns) %}{{ row.name }}{% endfor %}"

    variables = variables_for(text)

    assert isinstance(variables["rows"], ListNode)
    assert variables["columns"] == UnknownNode()


def test_bare_loop_item_is_list_of_strings():
    text = "{% for c in countries %}{{ c }}{% endfor %}"

    variables = variables_for(text)

    assert variables["countries"] == ListNode(items=StringNode())


def test_non_name_iterable_extracts_argument_not_loop_local():
    text = "{% for i in range(count) %}{{ i }}{% endfor %}"

    variables = variables_for(text)

    assert set(variables) == {"count"}
    assert variables["count"] == StringNode()


def test_plain_for_loop_still_extracted():
    text = "{% for row in rows %}{{ row.value }}{% endfor %}"

    variables = variables_for(text)

    assert "rows" in variables


def test_plain_variable_still_extracted():
    text = "{{ plain_var }}"

    variables = variables_for(text)

    assert "plain_var" in variables


def test_empty_string_key_is_kept_as_a_field():
    # '' is a real key, so it must not be read as "no key left to place"
    text = "{{ r[''] }}"

    assert variables_for(text) == {"r": ObjectNode(properties={"": StringNode()})}
