from conduit.server.features.doj.templates.jinja.tests.helpers import conflicts_for


def test_path_used_as_both_value_and_object_is_reported():
    text = "{{ a }}{{ a.b }}"

    conflicts = conflicts_for(text)

    assert len(conflicts) == 1
    assert "'a' is used as both a value and an object" in conflicts[0]


def test_whole_object_printed_is_reported():
    text = "{{ a.b }}{{ a }}"

    conflicts = conflicts_for(text)

    assert len(conflicts) == 1
    assert "'a' is an object and cannot be printed directly" in conflicts[0]


def test_whole_list_printed_is_reported():
    text = "{% for x in items %}{{ x.c }}{% endfor %}{{ items }}"

    conflicts = conflicts_for(text)

    assert len(conflicts) == 1
    assert "'items' is a list and cannot be printed directly" in conflicts[0]


def test_truthiness_guard_before_field_access_is_not_a_conflict():
    assert conflicts_for("{% if section %}{{ section.title }}{% endif %}") == []
    assert conflicts_for("{% if s.header %}{{ s.header.title }}{% endif %}") == []
    assert conflicts_for("{% for r in rows %}{% if r.meta %}{{ r.meta.id }}{% endif %}{% endfor %}") == []


def test_boolean_comparison_before_field_access_is_still_a_conflict():
    text = "{% if section == true %}{{ section.title }}{% endif %}"

    conflicts = conflicts_for(text)

    assert len(conflicts) == 1
    assert "'section' is used as both a value and an object" in conflicts[0]


def test_guarded_path_printed_as_a_value_is_still_a_conflict():
    text = "{% if section %}{{ section }}{{ section.title }}{% endif %}"

    conflicts = conflicts_for(text)

    assert len(conflicts) == 1
    assert "'section' is used as both a value and an object" in conflicts[0]


def test_repeated_whole_container_print_is_reported_once():
    text = "{{ a.b }}{{ a }} and {{ a }}"

    conflicts = conflicts_for(text)

    assert len(conflicts) == 1


def test_conflict_cites_the_line_of_the_offending_expression():
    text = "intro\n{{ alpha }}\nmiddle\n{{ alpha.beta }}"

    conflicts = conflicts_for(text)

    assert any("Line 4:" in c for c in conflicts)


def test_tag_spanning_lines_does_not_shift_later_line_numbers():
    text = "{%\n  if alpha %}{{ alpha }}{% endif %}\n{{ alpha.beta }}"

    conflicts = conflicts_for(text)

    assert any("Line 3:" in c for c in conflicts)


def test_docxtpl_tag_spanning_lines_does_not_shift_later_line_numbers():
    text = "{%tr\n  for r in rows %}{{ r.a }}{%tr endfor %}\n{{ alpha }}\n{{ alpha.beta }}"

    conflicts = conflicts_for(text)

    assert any("Line 4:" in c for c in conflicts)


def test_filtered_list_is_not_a_conflict():
    text = '{% for x in items %}{{ x.c }}{% endfor %}Total: {{ items | length }}{{ items | join(", ") }}'

    assert conflicts_for(text) == []


def test_consistent_nested_access_is_not_a_conflict():
    text = "{{ a.b.c }}{{ a.b.d }}{{ section.header.title }}{{ line_items[0].label }}"

    assert conflicts_for(text) == []


def test_loop_locals_are_not_conflicts():
    text = "{% for r in rows %}{{ r.name }}{{ r }}{% endfor %}"

    assert conflicts_for(text) == []


def test_unparseable_template_has_no_conflicts():
    text = "{{ a }}{{ a.b }}{% for x in rows %}"

    assert conflicts_for(text) == []


def test_conflict_inside_a_call_block_cites_the_call_line():
    text = "{{ a }}\nX\nX\n{% call m(a.b) %}{% endcall %}"

    assert any("Line 4:" in c for c in conflicts_for(text)), conflicts_for(text)


def test_conflict_inside_a_macro_cites_the_macro_line():
    text = "{{ a }}\nX\n{% macro m(p) %}{{ a.b }}{% endmacro %}"

    assert any("Line 3:" in c for c in conflicts_for(text)), conflicts_for(text)
