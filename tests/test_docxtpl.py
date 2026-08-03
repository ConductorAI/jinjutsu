from jinjutsu.types import ListNode, ObjectNode, StringNode
from jinjutsu.utils.docxtpl_utils import normalize_docxtpl_prefixes

from .helpers import schema_for, variables_for, warnings_for


def test_extracts_docxtpl_tr_loop_variable():
    text = "{%tr for row in funding_rows %}{{ row.source }}{%tr endfor %}"

    variables = variables_for(text)

    assert variables["funding_rows"] == ListNode(items=ObjectNode(properties={"source": StringNode()}))


def test_extracts_all_docxtpl_loop_prefixes():
    for prefix in ("tr", "tc", "p", "r"):
        text = f"{{%{prefix} for item in items %}}{{{{ item.name }}}}{{%{prefix} endfor %}}"

        variables = variables_for(text)

        assert "items" in variables, prefix


def test_docxtpl_cell_tags_supply_their_argument_as_a_variable():
    text = "{% colspan col_count %}{% cellbg row_color %}{{ title }}"

    variables = variables_for(text)

    assert variables["col_count"] == StringNode()
    assert variables["row_color"] == StringNode()
    assert variables["title"] == StringNode()


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


def test_a_paragraph_conditional_written_on_one_line_is_reported():
    # Renders as: TemplateSyntaxError: Encountered unknown tag 'endif'
    text = "{%p if invoice.paid %}PAID{%p endif %}"

    warnings = warnings_for(text)

    assert "Two 'p' tags in one paragraph" in warnings[0]
    assert "{%p if invoice.paid %} and {%p endif %}" in warnings[0]
    assert "Put each tag in its own paragraph" in warnings[0]


def test_a_loop_opened_and_closed_in_one_table_row_is_reported():
    # Renders as: TemplateSyntaxError: Encountered unknown tag 'endfor'
    text = "{%tr for line in lines %}\t{%tr endfor %}"

    assert "Two 'tr' tags in one table row" in warnings_for(text)[0]


def test_a_loop_opened_and_closed_in_one_table_cell_is_reported():
    # Renders as: TemplateSyntaxError: Encountered unknown tag 'endfor'
    text = "{%tc for c in cols %}{{ c }}{%tc endfor %}"

    assert "Two 'tc' tags in one table cell" in warnings_for(text)[0]


def test_the_line_and_the_two_tags_are_named():
    text = "Invoice\n{%p if paid %}PAID{%p endif %}"

    warning = warnings_for(text)[0]

    assert warning.startswith("Line 2:")
    assert "{%p if paid %}PAID{%p endif %}" in warning


def test_one_tag_per_element_is_not_reported():
    text = "{%p if show %}\nBODY\n{%p endif %}"

    assert warnings_for(text) == []


def test_a_tag_sharing_its_paragraph_with_text_is_reported():
    # Renders with no error, but 'BODY' is gone: ['Before', 'After']
    text = "{%p if show %}BODY\n{%p endif %}"

    warning = warnings_for(text)[0]

    assert "'p' tag shares its paragraph with other content" in warning
    assert "beside 'BODY'" in warning
    assert "renders without any error and that content is simply missing" in warning


def test_a_row_tag_sharing_its_row_with_another_cell_is_reported():
    # Renders with no error, but the 'Amount' cell never reaches the document
    text = "{%tr for line in lines %}\tAmount\n{{ line.desc }}\n{%tr endfor %}"

    assert "'tr' tag shares its table row with other content" in warnings_for(text)[0]


def test_cell_tags_in_different_cells_of_one_row_are_not_reported():
    # Each tag has its own cell, so each consumes only its own
    text = "{%tc for c in cols %}\t{{ c }}\t{%tc endfor %}"

    assert warnings_for(text) == []


def test_paragraph_tags_in_different_cells_of_one_row_are_not_reported():
    text = "{%p if show %}\tBODY\t{%p endif %}"

    assert warnings_for(text) == []


def test_unprefixed_tags_on_one_line_are_not_reported():
    # Plain jinja deletes only the text between the tags, so it has no element to lose
    text = "{% if show %}BODY{% endif %}"

    assert warnings_for(text) == []


def test_run_tags_on_one_line_are_not_reported():
    # A run is a span inside a paragraph, so two of them coexist on one line
    text = "{%r for x in xs %}{{ x }}{%r endfor %}"

    assert warnings_for(text) == []


def test_a_commented_out_tag_does_not_count_as_the_second_tag():
    # Unbalanced, since the endif is commented out, but that is the only thing wrong with it
    text = "{%p if show %}{# {%p endif %} #}"

    warnings = warnings_for(text)

    assert not any("in one paragraph" in warning for warning in warnings)
    assert any("Mismatched conditional tags" in warning for warning in warnings)


def test_the_shape_the_docs_recommend_still_yields_its_variables():
    text = "{%tr for line in invoice.lines %}\n{{ line.desc }}\t{{ line.amount }}\n{%tr endfor %}"

    properties = schema_for(text)["properties"]

    assert properties["invoice"]["properties"]["lines"]["items"]["properties"]["desc"] == {"type": "string"}
