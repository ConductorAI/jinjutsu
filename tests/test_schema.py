from jinjutsu.schema import JSON_SCHEMA_DRAFT

from .helpers import schema_for


def test_schema_is_a_standalone_json_schema_for_the_context_object():
    schema = schema_for("{{ title }}")

    assert schema == {
        "$schema": JSON_SCHEMA_DRAFT,
        "type": "object",
        "properties": {"title": {"type": "string"}},
    }


def test_leaf_kinds_map_to_json_schema_types():
    schema = schema_for("{{ name }}{% if sealed == true %}x{% endif %}")

    assert schema["properties"]["name"] == {"type": "string"}
    assert schema["properties"]["sealed"] == {"type": "boolean"}


def test_nothing_is_required_yet_so_the_keyword_is_never_emitted():
    schema = schema_for("{{ always }}{% if maybe %}x{% endif %}{% for r in rows %}{{ r.a }}{% endfor %}")

    assert "required" not in schema
    assert "required" not in schema["properties"]["rows"]["items"]


def test_object_nests_its_own_properties():
    schema = schema_for("{{ case.header.title }}")

    assert schema["properties"]["case"] == {
        "type": "object",
        "properties": {"header": {"type": "object", "properties": {"title": {"type": "string"}}}},
    }


def test_list_describes_its_element_under_items():
    schema = schema_for("{% for r in rows %}{{ r.name }}{% endfor %}")

    assert schema["properties"]["rows"] == {
        "type": "array",
        "items": {"type": "object", "properties": {"name": {"type": "string"}}},
    }


def test_list_of_scalars_describes_its_element_too():
    schema = schema_for("{% for c in countries %}{{ c }}{% endfor %}")

    assert schema["properties"]["countries"] == {"type": "array", "items": {"type": "string"}}


def test_nested_lists_nest_their_items():
    schema = schema_for("{{ matrix[0][1] }}")

    assert schema["properties"]["matrix"] == {
        "type": "array",
        "items": {"type": "array", "items": {"type": "string"}},
    }


def test_unknown_shape_is_reported_as_a_string():
    schema = schema_for("{% for x in xs %}body{% endfor %}")

    assert schema["properties"]["xs"] == {"type": "array", "items": {"type": "string"}}


def test_top_level_properties_are_sorted_so_output_is_stable():
    schema = schema_for("{{ zulu }}{{ alpha }}{{ mike }}")

    assert list(schema["properties"]) == ["alpha", "mike", "zulu"]


def test_a_template_with_no_variables_still_returns_a_valid_schema():
    schema = schema_for("plain text")

    assert schema["type"] == "object"
    assert schema["properties"] == {}


def test_a_template_that_will_not_parse_returns_a_schema_with_no_properties():
    schema = schema_for("{% for row in rows %}{{ row.a }}")

    assert schema["properties"] == {}
