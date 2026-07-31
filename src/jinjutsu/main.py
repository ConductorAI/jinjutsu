"""
Command line entry point: jinjutsu template.jinja

Prints what is wrong with the template first, then the variable tree in the shape README.md documents
Exits 1 when a template has diagnostics, so the command works as a check in CI or a pre-commit hook
"""

import argparse
import json
import sys
from pathlib import Path

from .analyze import analyze_jinja_template
from .variable_tree import VariableNode

NAME_COLUMN = 20  # Wide enough for most names

def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    paths = [Path(template) for template in args.templates]

    if missing := [path for path in paths if not path.is_file()]:
        for path in missing:
            print(f"jinjutsu: cannot read {path}", file=sys.stderr)
        return 2

    results = [_analyze(path) for path in paths]

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for index, result in enumerate(results):
            if index:
                print()
            _print_text(result, show_filename=len(results) > 1)

    return 1 if any(result["diagnostics"] for result in results) else 0

if __name__ == "__main__":
    sys.exit(main())


def _render_tree(variables: dict[str, VariableNode]) -> list[str]:
    """The whole tree, one line per name, roots flush left and their fields indented beneath"""
    lines = []
    for name, node in variables.items():
        lines.append(f"{name.ljust(NAME_COLUMN)}{_type_label(node)}")
        if children := node.get("properties"):
            lines.extend(_render_children(children, ""))
    return lines


def _type_label(node: VariableNode) -> str:
    """The type as the README writes it, where a list also says what one element looks like"""
    if node["type"] == "list":
        item_format = node.get("item_format")
        return f"list of {item_format}s" if item_format else "list"
    return node["type"]


def _render_children(nodes: dict[str, VariableNode], prefix: str) -> list[str]:
    lines = []
    last_index = len(nodes) - 1
    for index, (name, node) in enumerate(nodes.items()):
        is_last = index == last_index
        label = f"{prefix}{'`-- ' if is_last else '|-- '}{name}"
        lines.append(f"{label.ljust(NAME_COLUMN)}{_type_label(node)}")
        if children := node.get("properties"):
            lines.extend(_render_children(children, prefix + ("    " if is_last else "|   ")))
    return lines


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jinjutsu",
        description="Report what data a Jinja template needs and what is wrong with it",
    )
    parser.add_argument("templates", nargs="+", metavar="TEMPLATE", help="template files to analyze")
    parser.add_argument("--json", action="store_true", help="emit machine readable output instead of text")
    return parser


def _analyze(path: Path) -> dict:
    # Word writes a BOM often enough that utf-8-sig is the safer read for the templates this targets
    report = analyze_jinja_template(path.read_text(encoding="utf-8-sig"))
    return {"file": str(path), "variables": report.variables, "diagnostics": report.diagnostics}


def _print_text(result: dict, *, show_filename: bool) -> None:
    if show_filename:
        print(f"== {result['file']}")
    for diagnostic in result["diagnostics"]:
        print(diagnostic)
    if result["variables"]:
        if result["diagnostics"]:
            print()
        print("\n".join(_render_tree(result["variables"])))
    elif not result["diagnostics"]:
        print("No variables and nothing wrong")
