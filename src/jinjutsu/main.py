"""
Command line entry point: jinjutsu template.jinja, or jinjutsu "{{ inline.text }}"

Prints what is wrong with the template first, then the schema as the tree README.md documents
Exits 1 when a template has diagnostics, so the command works as a check in CI or a pre-commit hook
"""

import argparse
import json
import sys
from pathlib import Path

from .analyze import analyze_jinja_template
from .schema import render_tree

INLINE_LABEL = "<string>"  # Stands in for the filename when the template came from the command line
TEMPLATE_MARKERS = ("{{", "}}", "{%", "%}", "{#", "#}")
SECTIONS = ("warnings", "tree", "schema")
DEFAULT_SECTIONS = ("warnings", "tree")
# What to say when the requested sections all came back empty. A schema always prints, so it is absent
NOTHING_TO_SAY = {
    ("warnings", "tree"): "No variables and nothing wrong",
    ("warnings",): "Nothing wrong",
    ("tree",): "No variables",
}


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    sources = [_read(template) for template in args.templates]

    if missing := [t for t, source in zip(args.templates, sources, strict=True) if source is None]:
        for template in missing:
            print(f"jinjutsu: cannot read {template}", file=sys.stderr)
        return 2

    results = [_analyze(label, text) for label, text in sources]

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        sections = SECTIONS if args.all else tuple(s for s in SECTIONS if getattr(args, s)) or DEFAULT_SECTIONS
        for index, result in enumerate(results):
            if index:
                print()
            _print_text(result, sections, show_filename=len(results) > 1)

    return 1 if any(result["diagnostics"] for result in results) else 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jinjutsu", description="Report what data a Jinja template needs and what is wrong with it"
    )
    parser.add_argument("templates", nargs="+", metavar="TEMPLATE", help="template files, or template text itself")
    parser.add_argument("--warnings", action="store_true", help="print what is wrong with the template")
    parser.add_argument("--tree", action="store_true", help="print the data it needs as an indented tree")
    parser.add_argument("--schema", action="store_true", help="print the data it needs as a JSON Schema")
    parser.add_argument("--all", action="store_true", help="print all three sections")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit one machine readable record per template, ignoring the section flags",
    )
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


def _print_text(result: dict, sections: tuple[str, ...], *, show_filename: bool) -> None:
    if show_filename:
        print(f"== {result['file']}")

    properties = result["schema"]["properties"]
    blocks = []
    if "warnings" in sections and result["diagnostics"]:
        blocks.append("\n".join(result["diagnostics"]))
    if "tree" in sections and properties:
        blocks.append("\n".join(render_tree(properties)))
    if "schema" in sections:
        blocks.append(json.dumps(result["schema"], indent=2))

    if blocks:
        print("\n\n".join(blocks))
    elif not result["diagnostics"]:
        print(NOTHING_TO_SAY[sections])


if __name__ == "__main__":
    sys.exit(main())
