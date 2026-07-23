from conduit.server.features.doj.templates.validation import validate_template_jinja


def test_docxtpl_prefixed_tags_do_not_trip_mismatch_check():
    text = "{%tr for row in funding_rows %}{%tr if row.active %}{{ row.source }}{%tr endif %}{%tr endfor %}"

    warnings = validate_template_jinja(text)

    assert not any("Mismatched" in w for w in warnings)


def test_docxtpl_paragraph_conditional_is_not_a_syntax_error():
    text = "{%p if strategic_requirement_1 or strategic_requirement_2 %}{{ strategic_requirement_1 }}{%p endif %}"

    warnings = validate_template_jinja(text)

    assert not warnings


def test_docxtpl_prefixed_variable_is_not_a_syntax_error():
    text = "{{r rich_text_field }}"

    warnings = validate_template_jinja(text)

    assert not warnings
