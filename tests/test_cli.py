import json

from jinjutsu.main import main


def write(tmp_path, text, name="template.jinja"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_a_clean_template_exits_zero_and_prints_its_tree(tmp_path, capsys):
    template = write(tmp_path, "{{ case.title }}{% for s in case.sections %}{{ s.name }}{% endfor %}")

    assert main([template]) == 0

    out = capsys.readouterr().out
    assert "case                object" in out
    assert "|-- title           string" in out
    assert "`-- sections        list of objects" in out


def test_a_template_with_a_problem_exits_one_and_says_what_is_wrong(tmp_path, capsys):
    template = write(tmp_path, "{{ store.items }}")

    assert main([template]) == 1

    assert "built-in method" in capsys.readouterr().out


def test_json_output_carries_the_variables_and_diagnostics(tmp_path, capsys):
    template = write(tmp_path, "{{ store.items }}")

    main([template, "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["file"] == template
    assert payload[0]["variables"]["store"]["type"] == "object"
    assert len(payload[0]["diagnostics"]) == 1


def test_several_templates_are_labelled_by_filename(tmp_path, capsys):
    first = write(tmp_path, "{{ a }}", "first.jinja")
    second = write(tmp_path, "{{ b }}", "second.jinja")

    main([first, second])

    out = capsys.readouterr().out
    assert "== " + first in out
    assert "== " + second in out


def test_a_missing_file_exits_two_without_analyzing(tmp_path, capsys):
    assert main([str(tmp_path / "nope.jinja")]) == 2

    captured = capsys.readouterr()
    assert "cannot read" in captured.err
    assert captured.out == ""


def test_a_byte_order_mark_from_word_does_not_become_part_of_a_name(tmp_path, capsys):
    path = tmp_path / "bom.jinja"
    path.write_text("{{ title }}", encoding="utf-8-sig")

    assert main([str(path)]) == 0

    assert capsys.readouterr().out.startswith("title")
