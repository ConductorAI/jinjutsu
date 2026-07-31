"""
Command line entry point: jinjutsu template.jinja, or jinjutsu "{{ inline.text }}"

Prints what is wrong with the template first, then the variable tree in the shape README.md documents
Exits 1 when a template has diagnostics, so the command works as a check in CI or a pre-commit hook
"""

import argparse
import json
import sys
from pathlib import Path

from .analyze import analyze_jinja_template

NAME_COLUMN = 20  # Wide enough for most names
INLINE_LABEL = "<string>"  # Stands in for the filename when the template came from the command line
TEMPLATE_MARKERS = ("{{", "}}", "{%", "%}", "{#", "#}")

def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    sources = [(template, _read(template)) for template in args.templates]

    if missing := [template for template, source in sources if source is None]:
        for template in missing:
            print(f"jinjutsu: cannot read {template}", file=sys.stderr)
        return 2

    results = [_analyze(label, text) for _, (label, text) in sources]

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for index, result in enumerate(results):
            if index:
                print()
            _print_text(result, show_filename=len(results) > 1)

    return 1 if any(result["diagnostics"] for result in results) else 0


def _render_tree(properties: dict[str, dict]) -> list[str]:
    """The whole tree, one line per name, roots flush left and their fields indented beneath"""
    lines = []
    for name, node in properties.items():
        lines.append(f"{name.ljust(NAME_COLUMN)}{_type_label(node)}")
        if children := _child_properties(node):
            lines.extend(_render_children(children, ""))
    return lines


def _type_label(node: dict) -> str:
    """The type as the README writes it, where a list also says what one element looks like"""
    if node.get("type") != "array":
        return node.get("type", "unknown")
    items = node["items"]
    if items.get("type") == "array":
        return "list of lists"
    return f"list of {_type_label(items)}s"


def _child_properties(node: dict) -> dict[str, dict]:
    if node.get("type") == "object":
        return node["properties"]
    if node.get("type") == "array":
        return _child_properties(node["items"])
    return {}


def _render_children(nodes: dict[str, dict], prefix: str) -> list[str]:
    lines = []
    last_index = len(nodes) - 1
    for index, (name, node) in enumerate(nodes.items()):
        is_last = index == last_index
        label = f"{prefix}{'`-- ' if is_last else '|-- '}{name}"
        lines.append(f"{label.ljust(NAME_COLUMN)}{_type_label(node)}")
        if children := _child_properties(node):
            lines.extend(_render_children(children, prefix + ("    " if is_last else "|   ")))
    return lines


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jinjutsu",
        description="Report what data a Jinja template needs and what is wrong with it",
    )
    parser.add_argument(
        "templates",
        nargs="+",
        metavar="TEMPLATE",
        help="template files to analyze, or template text itself",
    )
    parser.add_argument("--json", action="store_true", help="emit machine readable output instead of text")
    return parser


def _read(template: str) -> tuple[str, str] | None:
    """Label and text for one argument, or None when it names neither a file nor anything template shaped"""
    path = Path(template)
    if path.is_file():  # Swallows the OSError a whole template passed as a path would otherwise raise
        # Word writes a BOM often enough that utf-8-sig is the safer read for the templates this targets
        return str(path), path.read_text(encoding="utf-8-sig")
    if any(marker in template for marker in TEMPLATE_MARKERS):
        return INLINE_LABEL, template
    return None


def _analyze(label: str, text: str) -> dict:
    report = analyze_jinja_template(text)
    return {"file": label, "schema": report.schema, "diagnostics": report.diagnostics}


def _print_text(result: dict, *, show_filename: bool) -> None:
    if show_filename:
        print(f"== {result['file']}")
    for diagnostic in result["diagnostics"]:
        print(diagnostic)
    if properties := result["schema"]["properties"]:
        if result["diagnostics"]:
            print()
        print("\n".join(_render_tree(properties)))
    elif not result["diagnostics"]:
        print("No variables and nothing wrong")


if __name__ == "__main__":
    sys.exit(main())
