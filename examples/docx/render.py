import sys
from pathlib import Path

from docxtpl import DocxTemplate, RichText

context = {
    "invoice": {
        "number": "INV-0042",
        "lines": [
            {"desc": RichText("Design", bold=True), "amount": "$1,200.00"},
            {"desc": RichText("Development"), "amount": "$3,400.00"},
        ],
        "paid": True,
    }
}

template_path = Path(sys.argv[1])
rendered_path = template_path.with_name(f"{template_path.stem}_rendered.docx")

template = DocxTemplate(template_path)
template.render(context)
template.save(str(rendered_path))
print(f"wrote {rendered_path}")
