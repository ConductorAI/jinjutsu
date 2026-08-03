"""
Extract a .docx's template text: everything docxtpl will render, in document order

A .docx is a zip of XML, so this reads it with the standard library alone — no python-docx needed.
A table becomes one line per row with the cells tab-separated, which keeps a reported line number
pointing at the row the author is looking at. Whitespace inside a Jinja tag is insignificant, so the
tabs cost nothing.

Textboxes, headers and footers are included because docxtpl renders tags in all three. Leaving them out
would under-report the context: the template would need a name nothing told you about, and it would
render blank with no error.
"""

import sys
import zipfile
from xml.etree import ElementTree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
BODY = "word/document.xml"


def extract_text(path: str) -> str:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        parts = [BODY] + sorted(n for n in names if n.startswith(("word/header", "word/footer")))
        lines = []
        for part in parts:
            if part in names:
                lines.extend(_lines(ElementTree.fromstring(archive.read(part))))
    return "\n".join(lines)


def _lines(element: ElementTree.Element) -> list[str]:
    """One line per paragraph and per table row, plus any textbox's own contents, in document order"""
    lines = []
    for child in element:
        if child.tag == f"{W}p":
            lines.append(_text_of(child))
        elif child.tag == f"{W}tbl":
            lines.extend(_row_line(row) for row in child.findall(f"{W}tr"))
        else:
            lines.extend(_lines(child))
            continue
        lines.extend(_textbox_lines(child))
    return lines


def _row_line(row: ElementTree.Element) -> str:
    """A row as one line. A trailing empty cell would leave a tab the author never typed, so drop it"""
    return "\t".join(_text_of(cell) for cell in row.findall(f"{W}tc")).rstrip("\t")


def _textbox_lines(element: ElementTree.Element) -> list[str]:
    lines = []
    for box in element.iter(f"{W}txbxContent"):
        lines.extend(_lines(box))
    return lines


def _text_of(element: ElementTree.Element) -> str:
    """The element's own text. A textbox is skipped here, since it is emitted as its own lines"""
    parts = []
    for child in element:
        if child.tag == f"{W}txbxContent":
            continue
        if child.tag == f"{W}t":
            parts.append(child.text or "")
        elif child.tag == f"{W}tab":
            parts.append("\t")
        else:
            parts.append(_text_of(child))
    return "".join(parts)


if __name__ == "__main__":
    print(extract_text(sys.argv[1]))
