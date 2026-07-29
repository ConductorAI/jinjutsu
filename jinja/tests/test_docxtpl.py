from conduit.server.features.doj.templates.jinja.tests.helpers import variables_for, warnings_for
from conduit.server.features.doj.templates.jinja.utils.docxtpl_utils import normalize_docxtpl_prefixes


def test_extracts_docxtpl_tr_loop_variable():
    text = "{%tr for row in funding_rows %}{{ row.source }}{%tr endfor %}"

    variables = variables_for(text)

    assert variables["funding_rows"] == {
        "type": "list",
        "item_format": "object",
        "properties": {"source": {"type": "string"}},
    }


def test_extracts_all_docxtpl_loop_prefixes():
    for prefix in ("tr", "tc", "p", "r"):
        text = f"{{%{prefix} for item in items %}}{{{{ item.name }}}}{{%{prefix} endfor %}}"

        variables = variables_for(text)

        assert "items" in variables, prefix


def test_docxtpl_cell_tags_supply_their_argument_as_a_variable():
    text = "{% colspan col_count %}{% cellbg row_color %}{{ title }}"

    variables = variables_for(text)

    assert variables["col_count"] == {"type": "string"}
    assert variables["row_color"] == {"type": "string"}
    assert variables["title"] == {"type": "string"}


def test_cell_tag_split_across_a_line_keeps_its_newline():
    text = "{% colspan\ncol %}"

    normalized = normalize_docxtpl_prefixes(text)

    assert len(normalized) == len(text)
    assert normalized.count("\n") == text.count("\n")


def test_cell_tag_split_across_a_line_does_not_shift_later_line_numbers():
    text = "line one\n{% colspan\ncol %}\nline four\n{% if a b c %}x{% endif %}"

    warnings = warnings_for(text)

    assert any("Line 5:" in w for w in warnings)
    assert any("{% if a b c %}x{% endif %}" in w for w in warnings)


def test_cell_tag_split_across_a_line_still_supplies_its_variable():
    text = "{% colspan\ncol_count %}{{ title }}"

    variables = variables_for(text)

    assert sorted(variables) == ["col_count", "title"]


def test_docxtpl_merge_tags_supply_no_variable():
    text = "{%tr for r in rows %}{% vm %}{% hm %}{{ r.name }}{%tr endfor %}"

    variables = variables_for(text)

    assert sorted(variables) == ["rows"]


def test_merge_tag_name_is_still_usable_as_a_variable():
    text = "{{ vm }} and {% if hm %}{{ hm.label }}{% endif %}"

    variables = variables_for(text)

    assert sorted(variables) == ["hm", "vm"]


def test_extracts_docxtpl_prefixed_variable():
    text = "{{r rich_text_field }}"

    variables = variables_for(text)

    assert "rich_text_field" in variables
