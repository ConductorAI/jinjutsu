from jinjutsu.types import BooleanNode, ListNode, StringNode

from .helpers import conflicts_for, schema_for, variables_for, warnings_for


def test_loop_locals_and_set_targets_are_not_extracted():
    text = "{% for k, v in mapping %}{{ k }}{{ v }}{% endfor %}{% set total = a + b %}{{ total }}"

    variables = variables_for(text)

    assert set(variables) == {"mapping", "a", "b"}


def test_set_block_target_is_shadowed():
    text = "{% set greeting %}Hello {{ name }}{% endset %}{{ greeting }}"

    variables = variables_for(text)

    assert set(variables) == {"name"}


def test_with_block_locals_are_scoped():
    text = "{% with a = obj %}{{ a }}{{ a.b }}{% endwith %}"

    assert conflicts_for(text) == []
    assert variables_for(text) == {"obj": StringNode()}


def test_with_block_reads_its_value_before_binding_the_name():
    text = "{% with a = a %}{{ a }}{% endwith %}"

    assert variables_for(text) == {"a": StringNode()}


def test_macro_and_call_block_parameters_are_scoped():
    macro = "{% macro row(cfg) %}{{ cfg.a }}{% endmacro %}{% for x in cfg %}{{ x }}{% endfor %}"
    call_block = "{% call(item) render() %}{{ item.a }}{% endcall %}"

    assert conflicts_for(macro) == []
    assert variables_for(macro) == {"cfg": ListNode(items=StringNode())}
    assert "item" not in variables_for(call_block)


def test_extracts_ternary_and_filter_argument_variables():
    text = "{{ value if show_it else fallback }}{{ price | default(fallback_price) }}"

    variables = variables_for(text)

    assert variables["show_it"] == BooleanNode()
    assert set(variables) == {"value", "show_it", "fallback", "price", "fallback_price"}


def test_commented_out_variables_are_ignored():
    text = "{# {{ commented_out }} #}{{ real_var }}"

    variables = variables_for(text)

    assert set(variables) == {"real_var"}


def test_unknown_filter_keeps_the_variables_and_names_the_filter():
    text = "{{ amount | to_json }}{{ client.name }}"

    assert set(schema_for(text)["properties"]) == {"amount", "client"}
    assert "Unknown filter 'to_json'" in warnings_for(text)[0]


def test_unknown_filter_close_to_a_builtin_suggests_it():
    warnings = warnings_for("{{ name | uppercase }}")

    assert "Unknown filter 'uppercase'" in warnings[0]
    assert "Did you mean 'upper'?" in warnings[0]


def test_unknown_filter_with_no_lookalike_offers_registering_it():
    warnings = warnings_for("{{ total | usd }}")

    assert "Unknown filter 'usd'" in warnings[0]
    assert "Register 'usd'" in warnings[0]


def test_unknown_test_is_reported_and_keeps_the_variable():
    text = "{% if x is weird %}hi{% endif %}"

    assert "Unknown test 'weird'" in warnings_for(text)[0]
    assert "x" in schema_for(text)["properties"]


def test_builtin_filters_and_tests_are_not_flagged():
    text = "{{ x | upper }}{{ y | default('z') }}{% if n is defined %}{% endif %}"

    assert warnings_for(text) == []


def test_unknown_filter_still_reports_what_the_walk_found():
    printed = "{{ case.title }}{{ case }}{{ amount | to_json }}"
    clashed = "{{ total }}{{ total.amount }}{{ amount | to_json }}"

    assert "'case' is an object and can't be printed directly" in warnings_for(printed)[0]
    assert "'total' is used as both a value and an object" in warnings_for(clashed)[0]


def test_malformed_template_returns_empty_schema():
    text = "{% for row in funding_rows %}{{ row.source }}"

    variables = variables_for(text)

    assert variables == {}
