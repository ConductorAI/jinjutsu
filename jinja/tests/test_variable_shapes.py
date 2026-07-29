from conduit.server.features.doj.templates.jinja.tests.helpers import variables_for


def test_indexed_access_builds_list_of_objects():
    text = "{{ items[0].name }}"

    variables = variables_for(text)

    assert variables["items"] == {
        "type": "list",
        "item_format": "object",
        "properties": {"name": {"type": "string"}},
    }


def test_dot_number_access_builds_list_of_objects():
    text = "{{ items.0.name }}"

    variables = variables_for(text)

    assert variables["items"] == {
        "type": "list",
        "item_format": "object",
        "properties": {"name": {"type": "string"}},
    }


def test_bare_indexed_access_is_list_of_strings():
    text = "{{ items[0] }}"

    variables = variables_for(text)

    assert variables["items"] == {"type": "list", "item_format": "string"}


def test_indexed_access_nested_under_object():
    text = "{{ a.b[0].c }}"

    variables = variables_for(text)

    assert variables["a"] == {
        "type": "object",
        "properties": {
            "b": {"type": "list", "item_format": "object", "properties": {"c": {"type": "string"}}},
        },
    }


def test_string_subscript_is_a_property_not_an_index():
    text = "{{ r['items'] }}"

    variables = variables_for(text)

    assert variables["r"] == {"type": "object", "properties": {"items": {"type": "string"}}}


def test_string_subscript_is_never_mistaken_for_an_index_marker():
    text = "{{ r['[]'] }}"

    variables = variables_for(text)

    assert variables["r"] == {"type": "object", "properties": {"[]": {"type": "string"}}}


def test_indexed_access_merges_with_loop_over_same_list():
    text = "{{ items[0].name }}{% for i in items %}{{ i.other }}{% endfor %}"

    variables = variables_for(text)

    assert variables["items"] == {
        "type": "list",
        "item_format": "object",
        "properties": {"name": {"type": "string"}, "other": {"type": "string"}},
    }


def test_dynamic_subscript_is_not_resolved():
    text = "{{ items[i] }}"

    variables = variables_for(text)

    assert set(variables) == {"items", "i"}
    assert variables["items"] == {"type": "string"}


def test_top_level_object_access_builds_nested_object():
    text = "{{ section.header.title }}"

    variables = variables_for(text)

    assert variables["section"] == {
        "type": "object",
        "properties": {
            "header": {"type": "object", "properties": {"title": {"type": "string"}}},
        },
    }


def test_nested_loops_build_nested_list_of_objects():
    text = "{% for s in sections %}{{ s.title }}{% for a in s.authorized %}{{ a.name }}{% endfor %}{% endfor %}"

    variables = variables_for(text)

    assert variables["sections"] == {
        "type": "list",
        "item_format": "object",
        "properties": {
            "title": {"type": "string"},
            "authorized": {
                "type": "list",
                "item_format": "object",
                "properties": {"name": {"type": "string"}},
            },
        },
    }


def test_filtered_iterable_is_still_a_list():
    text = "{% for x in items | sort %}{{ x.name }}{% endfor %}"

    variables = variables_for(text)

    assert variables["items"] == {
        "type": "list",
        "item_format": "object",
        "properties": {"name": {"type": "string"}},
    }


def test_filter_arguments_are_still_extracted():
    text = "{% for row in rows | batch(columns) %}{{ row.name }}{% endfor %}"

    variables = variables_for(text)

    assert variables["rows"]["type"] == "list"
    assert variables["columns"] == {"type": "string"}


def test_bare_loop_item_is_list_of_strings():
    text = "{% for c in countries %}{{ c }}{% endfor %}"

    variables = variables_for(text)

    assert variables["countries"] == {"type": "list", "item_format": "string"}


def test_non_name_iterable_extracts_argument_not_loop_local():
    text = "{% for i in range(count) %}{{ i }}{% endfor %}"

    variables = variables_for(text)

    assert set(variables) == {"count"}
    assert variables["count"] == {"type": "string"}


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

    assert variables_for(text) == {"r": {"type": "object", "properties": {"": {"type": "string"}}}}
