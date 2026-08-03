import io
import zipfile

from jinja2 import Environment, TemplateSyntaxError

from jinjutsu import analyze_jinja_template
from jinjutsu.analyze import _build_variable_tree
from jinjutsu.utils.docxtpl_utils import normalize_docxtpl_prefixes

DOCX_XMLNS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def warnings_for(text: str) -> list[str]:
    return analyze_jinja_template(text).diagnostics


def docx_bytes(body_xml: str, parts: dict[str, str] | None = None) -> bytes:
    "A minimal .docx: word/document.xml wrapping body_xml, plus any extra parts given as complete XML"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", f"<w:document {DOCX_XMLNS}><w:body>{body_xml}</w:body></w:document>")
        for name, xml in (parts or {}).items():
            archive.writestr(name, xml)
    return buffer.getvalue()


def paragraph(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def schema_for(text: str) -> dict:
    return analyze_jinja_template(text).schema


def variables_for(text: str):
    "The internal tree, which the public report no longer carries"
    return _build_variable_tree(_ast_for(text))[0]


def conflicts_for(text: str) -> list[str]:
    "Just what the walk noticed, without the text checks analyze_jinja_template() merges in alongside"
    return _build_variable_tree(_ast_for(text))[1]


def _ast_for(text: str):
    try:
        return Environment().parse(normalize_docxtpl_prefixes(text))
    except TemplateSyntaxError:
        return None
