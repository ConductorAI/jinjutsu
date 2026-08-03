import sys

from docx import Document
from docx.table import Table


def extract_text(path: str) -> str:
    document = Document(path)
    lines = []
    for item in document.iter_inner_content():
        if isinstance(item, Table):
            lines.extend("\t".join(cell.text for cell in row.cells).rstrip("\t") for row in item.rows)
        else:
            lines.append(item.text)
    return "\n".join(lines)


if __name__ == "__main__":
    print(extract_text(sys.argv[1]))
