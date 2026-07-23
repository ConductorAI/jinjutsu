import re

from jinja2 import Environment, nodes

JINJA_ENV = Environment()

# docxtpl adds row/cell/paragraph/run prefixes to Jinja tags, e.g. {%tr for ... %} or {{r ... }}
DOCXTPL_TAG_PREFIX = r"(?:tr|tc|p|r)"


def normalize_docxtpl_prefixes(text: str) -> str:
    """Strip docxtpl row/cell/paragraph/run prefixes so vanilla Jinja can parse the tags."""
    return re.sub(rf"(\{{[%{{]){DOCXTPL_TAG_PREFIX}?\s+", r"\1 ", text)


def parse_template(text: str) -> nodes.Template:
    """Normalize docxtpl prefixes and parse the template into a Jinja AST.

    Raises TemplateSyntaxError if the template is malformed. Only prefixes are stripped, so
    line numbers still map back to the original text.
    """
    return JINJA_ENV.parse(normalize_docxtpl_prefixes(text))


def name_path(node: nodes.Node) -> tuple[str, list[str]] | None:
    """Resolve a Name / Getattr chain to (root_name, attribute_path), else None."""
    attrs: list[str] = []
    current = node
    while isinstance(current, nodes.Getattr):
        attrs.append(current.attr)
        current = current.node
    if isinstance(current, nodes.Name):
        return current.name, list(reversed(attrs))
    return None


def target_names(target: nodes.Node) -> list[str]:
    """Names bound by a for-loop target or set assignment (handles tuple unpacking)."""
    if isinstance(target, nodes.Name):
        return [target.name]
    if isinstance(target, nodes.Tuple):
        return [item.name for item in target.items if isinstance(item, nodes.Name)]
    return []
