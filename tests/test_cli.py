import json
import os

import pytest

from jinjutsu.main import main

from .helpers import docx_bytes, paragraph


def write(tmp_path, text, name="template.jinja"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_a_clean_template_exits_zero_and_prints_its_tree(tmp_path, capsys):
    template = write(tmp_path, "{{ case.title }}{% for s in case.sections %}{{ s.name }}{% endfor %}")

    assert main([template]) == 0

    out = capsys.readouterr().out
    assert "case          object" in out
    assert "|-- title     string" in out
    assert "`-- sections  list of objects" in out


def test_a_template_with_a_problem_exits_one_and_says_what_is_wrong(tmp_path, capsys):
    template = write(tmp_path, "{{ store.items }}")

    assert main([template]) == 1

    assert "built-in method" in capsys.readouterr().out


def test_several_templates_are_labelled_by_filename(tmp_path, capsys):
    first = write(tmp_path, "{{ a }}", "first.jinja")
    second = write(tmp_path, "{{ b }}", "second.jinja")

    main([first, second])

    out = capsys.readouterr().out
    assert "== " + first in out
    assert "== " + second in out


def test_template_text_is_analyzed_in_place_of_a_filename(capsys):
    assert main(["hi {{ variable + 1 }}"]) == 0

    assert capsys.readouterr().out.startswith("variable")


def test_template_text_reports_its_problems_too(capsys):
    assert main(["{{ store.items }}"]) == 1

    assert "built-in method" in capsys.readouterr().out


def test_malformed_template_text_is_still_recognized_as_a_template(capsys):
    assert main(["{ % if alpha %}gated{% endif %}"]) == 1

    assert "Extra space after" in capsys.readouterr().out


def test_template_text_is_labelled_as_a_string_not_a_path(capsys):
    main(["{{ a }}", "{{ b }}"])

    assert "== <string>" in capsys.readouterr().out


def test_a_file_wins_over_template_text_when_both_could_match(tmp_path, capsys):
    path = write(tmp_path, "{{ from_the_file }}", "{{ odd_name }}.jinja")

    main([path, "--tree"])

    out = capsys.readouterr().out
    assert out.startswith("from_the_file")
    assert "odd_name" not in out


def test_an_argument_that_is_neither_a_file_nor_a_template_still_exits_two(capsys):
    assert main(["not-a-template.jinja"]) == 2

    assert "Error: not-a-template.jinja\n  Problem: No such file" in capsys.readouterr().err


def test_warnings_only_omits_the_tree(tmp_path, capsys):
    template = write(tmp_path, "{{ store.items }}")

    assert main([template, "--warnings"]) == 1

    out = capsys.readouterr().out
    assert "built-in method" in out
    assert "store      object" not in out


def test_tree_only_omits_the_warnings(tmp_path, capsys):
    template = write(tmp_path, "{{ store.items }}")

    assert main([template, "--tree"]) == 1

    out = capsys.readouterr().out
    assert "store      object" in out
    assert "built-in method" not in out


def test_schema_prints_the_json_schema(tmp_path, capsys):
    template = write(tmp_path, "{{ title }}")

    assert main([template, "--schema"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["properties"] == {"title": {"type": "string"}}


def test_all_prints_every_section(tmp_path, capsys):
    template = write(tmp_path, "{{ store.items }}")

    assert main([template, "--all"]) == 1

    out = capsys.readouterr().out
    assert "built-in method" in out
    assert "store      object" in out
    assert '"$schema"' in out


def test_sections_compose(tmp_path, capsys):
    template = write(tmp_path, "{{ store.items }}")

    main([template, "--tree", "--schema"])

    out = capsys.readouterr().out
    assert "store      object" in out
    assert '"$schema"' in out
    assert "built-in method" not in out


def test_the_empty_message_only_mentions_the_sections_asked_for(tmp_path, capsys):
    template = write(tmp_path, "plain text")

    main([template, "--warnings"])
    assert capsys.readouterr().out == "Template parsed successfully with no warnings\n"

    main([template, "--tree"])
    assert capsys.readouterr().out == "No variables parsed from template. Warnings:\n"

    main([template])
    assert capsys.readouterr().out == "Template parsed successfully but no variables found\n"


def test_an_empty_tree_prints_the_warnings_below_the_same_message(tmp_path, capsys):
    template = write(tmp_path, "{ % if alpha %}x{% endif %}")

    assert main([template, "--tree"]) == 1

    out = capsys.readouterr().out
    assert out.startswith("No variables parsed from template. Warnings:\n\n")
    assert "Extra space after" in out


def test_every_warning_is_printed_when_the_tree_is_empty(tmp_path, capsys):
    template = write(tmp_path, "{ % if alpha %}x{% endif %}\n{ % if beta %}y{% endif %}")

    main([template, "--tree"])

    out = capsys.readouterr().out
    assert "Line 1:" in out
    assert "Line 2:" in out


def test_several_sections_are_labelled_with_dividers(tmp_path, capsys):
    template = write(tmp_path, "{{ store.items }}")

    main([template])

    out = capsys.readouterr().out
    assert out.startswith("===== warnings ====")
    assert "\n===== tree ====" in out


def test_a_lone_section_is_printed_bare_so_it_can_be_redirected(tmp_path, capsys):
    template = write(tmp_path, "{{ title }}")

    main([template, "--schema"])

    assert json.loads(capsys.readouterr().out)["properties"] == {"title": {"type": "string"}}


def test_a_clean_template_prints_its_tree_without_a_divider(tmp_path, capsys):
    template = write(tmp_path, "{{ a.b }}")

    main([template])

    assert capsys.readouterr().out.startswith("a      object")


def test_the_type_column_follows_the_longest_label_so_every_row_lines_up(tmp_path, capsys):
    template = write(tmp_path, "{{ short }}{{ deep.some_extremely_long_field_name }}")

    main([template, "--tree"])

    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "deep                                object",
        "`-- some_extremely_long_field_name  string",
        "short                               string",
    ]


def test_a_missing_file_exits_two_without_analyzing(tmp_path, capsys):
    assert main([str(tmp_path / "nope.jinja")]) == 2

    captured = capsys.readouterr()
    assert "No such file" in captured.err
    assert captured.out == ""


def test_a_docx_is_extracted_and_analyzed_directly(tmp_path, capsys):
    path = tmp_path / "report.docx"
    path.write_bytes(docx_bytes(paragraph("Hello {{ title }}")))

    assert main([str(path)]) == 0

    assert "title  string" in capsys.readouterr().out


def test_a_fake_docx_that_is_not_a_zip_is_reported_rather_than_raising(tmp_path, capsys):
    path = tmp_path / "report.docx"
    path.write_bytes(b"PK\x03\x04\x80\x81\x82")

    assert main([str(path)]) == 2

    captured = capsys.readouterr()
    assert f"Error: {path}\n  Problem: Not a Word document" in captured.err
    assert captured.out == ""


def test_an_undecodable_file_that_is_not_a_docx_is_not_called_one(tmp_path, capsys):
    path = tmp_path / "smart_quotes.jinja"
    path.write_bytes(b"{{ client\x92s_total }}")  # cp1252, the apostrophe Word types

    assert main([str(path)]) == 2

    captured = capsys.readouterr()
    assert f"Error: {path}\n  Problem: Not UTF-8 text" in captured.err
    assert ".docx" not in captured.err


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a file whatever its mode says")
def test_a_file_that_will_not_open_is_reported_rather_than_raising(tmp_path, capsys):
    path = tmp_path / "locked.jinja"
    path.write_text("{{ title }}")
    path.chmod(0o000)

    assert main([str(path)]) == 2

    assert f"Error: {path}\n  Problem: Permission denied" in capsys.readouterr().err


def test_a_byte_order_mark_from_word_does_not_become_part_of_a_name(tmp_path, capsys):
    path = tmp_path / "bom.jinja"
    path.write_text("{{ title }}", encoding="utf-8-sig")

    assert main([str(path)]) == 0

    assert capsys.readouterr().out.startswith("title")
