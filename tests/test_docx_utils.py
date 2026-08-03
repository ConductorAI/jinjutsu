import zipfile
from pathlib import Path

import pytest

from jinjutsu import extract_docx_text

from .helpers import DOCX_XMLNS, docx_bytes, paragraph

CURRENT_DIR = Path(__file__).parent


def extract(tmp_path, content: bytes) -> str:
    path = tmp_path / "document.docx"
    path.write_bytes(content)
    return extract_docx_text(path)


def test_each_paragraph_is_one_line_in_document_order(tmp_path):
    text = extract(tmp_path, docx_bytes(paragraph("Invoice {{ invoice.number }}") + paragraph("{%p if paid %}")))

    assert text == "Invoice {{ invoice.number }}\n{%p if paid %}"


def test_a_tag_word_split_across_runs_is_rejoined(tmp_path):
    body = "<w:p><w:r><w:t>{{ ti</w:t></w:r><w:r><w:t>tle }}</w:t></w:r></w:p>"

    assert extract(tmp_path, docx_bytes(body)) == "{{ title }}"


def test_a_table_row_is_one_line_with_cells_tab_separated(tmp_path):
    cells = f"<w:tc>{paragraph('{{ line.desc }}')}</w:tc><w:tc>{paragraph('{{ line.amount }}')}</w:tc>"

    assert extract(tmp_path, docx_bytes(f"<w:tbl><w:tr>{cells}</w:tr></w:tbl>")) == "{{ line.desc }}\t{{ line.amount }}"


def test_a_trailing_empty_cell_leaves_no_tab(tmp_path):
    body = f"<w:tbl><w:tr><w:tc>{paragraph('{%tr endfor %}')}</w:tc><w:tc>{paragraph('')}</w:tc></w:tr></w:tbl>"

    assert extract(tmp_path, docx_bytes(body)) == "{%tr endfor %}"


def test_a_typed_tab_becomes_a_tab_character(tmp_path):
    body = "<w:p><w:r><w:t>a</w:t></w:r><w:r><w:tab/></w:r><w:r><w:t>b</w:t></w:r></w:p>"

    assert extract(tmp_path, docx_bytes(body)) == "a\tb"


def test_headers_and_footers_are_included_after_the_body(tmp_path):
    parts = {
        "word/header1.xml": f"<w:hdr {DOCX_XMLNS}>{paragraph('{{ letterhead }}')}</w:hdr>",
        "word/footer1.xml": f"<w:ftr {DOCX_XMLNS}>{paragraph('{{ page_note }}')}</w:ftr>",
    }

    text = extract(tmp_path, docx_bytes(paragraph("body"), parts))

    assert text == "body\n{{ page_note }}\n{{ letterhead }}"


def test_a_textbox_is_emitted_as_its_own_lines(tmp_path):
    box = f"<w:pict><w:txbxContent>{paragraph('{{ boxed }}')}</w:txbxContent></w:pict>"
    body = f"<w:p><w:r><w:t>outer</w:t>{box}</w:r></w:p>"

    assert extract(tmp_path, docx_bytes(body)) == "outer\n{{ boxed }}"


def test_a_file_that_is_not_a_zip_is_rejected(tmp_path):
    with pytest.raises(zipfile.BadZipFile):
        extract(tmp_path, b"PK\x03\x04\x80\x81\x82")


def test_a_zip_without_a_document_body_is_rejected(tmp_path):
    buffer_path = tmp_path / "document.docx"
    with zipfile.ZipFile(buffer_path, "w") as archive:
        archive.writestr("word/styles.xml", f"<w:styles {DOCX_XMLNS}/>")

    with pytest.raises(KeyError):
        extract_docx_text(buffer_path)


def test_the_sample_invoice_extracts_its_docxtpl_tags():
    text = extract_docx_text(CURRENT_DIR.parent / "examples" / "docx" / "samples" / "invoice.docx")

    assert "{%tr for line in invoice.lines %}" in text
    assert "{{r line.desc }}\t{{ line.amount }}" in text
