from conduit.server.features.doj.templates.extraction import extract_template_variables, find_schema_conflicts


def test_extracts_docxtpl_tr_loop_variable():
    text = "{%tr for row in funding_rows %}{{ row.source }}{%tr endfor %}"

    variables = extract_template_variables(text)

    assert variables["funding_rows"] == {
        "type": "list",
        "item_format": "object",
        "properties": {"source": {"type": "string"}},
    }


def test_extracts_all_docxtpl_loop_prefixes():
    for prefix in ("tr", "tc", "p", "r"):
        text = f"{{%{prefix} for item in items %}}{{{{ item.name }}}}{{%{prefix} endfor %}}"

        variables = extract_template_variables(text)

        assert "items" in variables, prefix


def test_plain_for_loop_still_extracted():
    text = "{% for row in rows %}{{ row.value }}{% endfor %}"

    variables = extract_template_variables(text)

    assert "rows" in variables


def test_extracts_docxtpl_prefixed_variable():
    text = "{{r rich_text_field }}"

    variables = extract_template_variables(text)

    assert "rich_text_field" in variables


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


def test_indexed_access_builds_list_of_objects():
    text = "{{ items[0].name }}"

    variables = extract_template_variables(text)

    assert variables["items"] == {
        "type": "list",
        "item_format": "object",
        "properties": {"name": {"type": "string"}},
    }


def test_dot_number_access_builds_list_of_objects():
    text = "{{ items.0.name }}"

    variables = extract_template_variables(text)

    assert variables["items"] == {
        "type": "list",
        "item_format": "object",
        "properties": {"name": {"type": "string"}},
    }


def test_bare_indexed_access_is_list_of_strings():
    text = "{{ items[0] }}"

    variables = extract_template_variables(text)

    assert variables["items"] == {"type": "list", "item_format": "string"}


def test_indexed_access_nested_under_object():
    text = "{{ a.b[0].c }}"

    variables = extract_template_variables(text)

    assert variables["a"] == {
        "type": "object",
        "properties": {
            "b": {"type": "list", "item_format": "object", "properties": {"c": {"type": "string"}}},
        },
    }


def test_string_subscript_is_a_property_not_an_index():
    text = "{{ r['items'] }}"

    variables = extract_template_variables(text)

    assert variables["r"] == {"type": "object", "properties": {"items": {"type": "string"}}}


def test_string_subscript_is_never_mistaken_for_an_index_marker():
    text = "{{ r['[]'] }}"

    variables = extract_template_variables(text)

    assert variables["r"] == {"type": "object", "properties": {"[]": {"type": "string"}}}


def test_indexed_access_merges_with_loop_over_same_list():
    text = "{{ items[0].name }}{% for i in items %}{{ i.other }}{% endfor %}"

    variables = extract_template_variables(text)

    assert variables["items"] == {
        "type": "list",
        "item_format": "object",
        "properties": {"name": {"type": "string"}, "other": {"type": "string"}},
    }


def test_dynamic_subscript_is_not_resolved():
    text = "{{ items[i] }}"

    variables = extract_template_variables(text)

    assert set(variables) == {"items", "i"}
    assert variables["items"] == {"type": "string"}


def test_comparison_against_boolean_literal_is_boolean():
    assert extract_template_variables("{% if sales_rep == true %}x{% endif %}") == {
        "sales_rep": {"type": "boolean"},
    }
    assert extract_template_variables("{% if sales_rep == false %}x{% endif %}") == {
        "sales_rep": {"type": "boolean"},
    }
    assert extract_template_variables("{% if sales_rep != true %}x{% endif %}") == {
        "sales_rep": {"type": "boolean"},
    }


def test_quoted_comparison_against_true_is_string():
    text = "{% if phase == 'true' %}x{% endif %}"

    variables = extract_template_variables(text)

    assert variables["phase"] == {"type": "string"}


def test_comparison_against_number_is_string():
    text = "{% if count == 1 %}x{% endif %}"

    variables = extract_template_variables(text)

    assert variables["count"] == {"type": "string"}


def test_boolean_comparison_on_nested_attribute_is_boolean():
    text = "{% for r in rows %}{% if r.active == true %}{{ r.name }}{% endif %}{% endfor %}"

    variables = extract_template_variables(text)

    assert variables["rows"] == {
        "type": "list",
        "item_format": "object",
        "properties": {"active": {"type": "boolean"}, "name": {"type": "string"}},
    }


def test_boolean_comparison_demoted_to_string_when_also_output():
    text = "{% if sales_rep == true %}{{ sales_rep }}{% endif %}"

    variables = extract_template_variables(text)

    assert variables["sales_rep"] == {"type": "string"}


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


def test_malformed_template_returns_empty_schema():
    text = "{% for row in funding_rows %}{{ row.source }}"

    variables = extract_template_variables(text)

    assert variables == {}


def test_nested_loops_build_nested_list_of_objects():
    text = "{% for s in sections %}{{ s.title }}{% for a in s.authorized %}{{ a.name }}{% endfor %}{% endfor %}"

    variables = extract_template_variables(text)

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

    variables = extract_template_variables(text)

    assert variables["items"] == {
        "type": "list",
        "item_format": "object",
        "properties": {"name": {"type": "string"}},
    }


def test_filter_arguments_are_still_extracted():
    text = "{% for row in rows | batch(columns) %}{{ row.name }}{% endfor %}"

    variables = extract_template_variables(text)

    assert variables["rows"]["type"] == "list"
    assert variables["columns"] == {"type": "string"}


def test_truthiness_guard_refines_into_an_object():
    text = "{% if section %}{{ section.title }}{% endif %}"

    variables = extract_template_variables(text)

    assert variables["section"] == {"type": "object", "properties": {"title": {"type": "string"}}}


def test_bare_loop_item_is_list_of_strings():
    text = "{% for c in countries %}{{ c }}{% endfor %}"

    variables = extract_template_variables(text)

    assert variables["countries"] == {"type": "list", "item_format": "string"}


def test_non_name_iterable_extracts_argument_not_loop_local():
    text = "{% for i in range(count) %}{{ i }}{% endfor %}"

    variables = extract_template_variables(text)

    assert set(variables) == {"count"}
    assert variables["count"] == {"type": "string"}


def test_boolean_operators_in_condition_extract_boolean_operands():
    assert extract_template_variables("{% if a and b %}x{% endif %}") == {
        "a": {"type": "boolean"},
        "b": {"type": "boolean"},
    }
    assert extract_template_variables("{% if not hidden %}x{% endif %}") == {
        "hidden": {"type": "boolean"},
    }


def test_set_block_target_is_shadowed():
    text = "{% set greeting %}Hello {{ name }}{% endset %}{{ greeting }}"

    variables = extract_template_variables(text)

    assert set(variables) == {"name"}


def test_with_block_locals_are_scoped():
    text = "{% with a = obj %}{{ a }}{{ a.b }}{% endwith %}"

    assert find_schema_conflicts(text) == []
    assert extract_template_variables(text) == {"obj": {"type": "string"}}


def test_with_block_reads_its_value_before_binding_the_name():
    text = "{% with a = a %}{{ a }}{% endwith %}"

    assert extract_template_variables(text) == {"a": {"type": "string"}}


def test_macro_and_call_block_parameters_are_scoped():
    macro = "{% macro row(cfg) %}{{ cfg.a }}{% endmacro %}{% for x in cfg %}{{ x }}{% endfor %}"
    call_block = "{% call(item) render() %}{{ item.a }}{% endcall %}"

    assert find_schema_conflicts(macro) == []
    assert extract_template_variables(macro) == {"cfg": {"type": "list", "item_format": "string"}}
    assert "item" not in extract_template_variables(call_block)


def test_path_used_as_both_value_and_object_is_reported():
    text = "{{ a }}{{ a.b }}"

    conflicts = find_schema_conflicts(text)

    assert len(conflicts) == 1
    assert "'a' is used as both a value and an object" in conflicts[0]


def test_whole_object_printed_is_reported():
    text = "{{ a.b }}{{ a }}"

    conflicts = find_schema_conflicts(text)

    assert len(conflicts) == 1
    assert "'a' is printed as a whole object" in conflicts[0]


def test_whole_list_printed_is_reported():
    text = "{% for x in items %}{{ x.c }}{% endfor %}{{ items }}"

    conflicts = find_schema_conflicts(text)

    assert len(conflicts) == 1
    assert "'items' is printed as a whole list" in conflicts[0]


def test_truthiness_guard_before_field_access_is_not_a_conflict():
    assert find_schema_conflicts("{% if section %}{{ section.title }}{% endif %}") == []
    assert find_schema_conflicts("{% if s.header %}{{ s.header.title }}{% endif %}") == []
    assert find_schema_conflicts("{% for r in rows %}{% if r.meta %}{{ r.meta.id }}{% endif %}{% endfor %}") == []


def test_boolean_comparison_before_field_access_is_still_a_conflict():
    text = "{% if section == true %}{{ section.title }}{% endif %}"

    conflicts = find_schema_conflicts(text)

    assert len(conflicts) == 1
    assert "'section' is used as both a value and an object" in conflicts[0]


def test_guarded_path_printed_as_a_value_is_still_a_conflict():
    text = "{% if section %}{{ section }}{{ section.title }}{% endif %}"

    conflicts = find_schema_conflicts(text)

    assert len(conflicts) == 1
    assert "'section' is used as both a value and an object" in conflicts[0]


def test_repeated_whole_container_print_is_reported_once():
    text = "{{ a.b }}{{ a }} and {{ a }}"

    conflicts = find_schema_conflicts(text)

    assert len(conflicts) == 1


def test_conflict_cites_the_line_of_the_offending_expression():
    text = "intro\n{{ alpha }}\nmiddle\n{{ alpha.beta }}"

    conflicts = find_schema_conflicts(text)

    assert any("Line 4:" in c for c in conflicts)


def test_filtered_list_is_not_a_conflict():
    text = '{% for x in items %}{{ x.c }}{% endfor %}Total: {{ items | length }}{{ items | join(", ") }}'

    assert find_schema_conflicts(text) == []


def test_consistent_nested_access_is_not_a_conflict():
    text = "{{ a.b.c }}{{ a.b.d }}{{ section.header.title }}{{ line_items[0].label }}"

    assert find_schema_conflicts(text) == []


def test_loop_locals_are_not_conflicts():
    text = "{% for r in rows %}{{ r.name }}{{ r }}{% endfor %}"

    assert find_schema_conflicts(text) == []


def test_unparseable_template_has_no_conflicts():
    text = "{{ a }}{{ a.b }}{% for x in rows %}"

    assert find_schema_conflicts(text) == []
