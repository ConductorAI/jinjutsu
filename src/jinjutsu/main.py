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
from .types import TemplateReport

INLINE_LABEL = "<string>"  # Stands in for the filename when the template came from the command line
TEMPLATE_MARKERS = ("{{", "}}", "{%", "%}", "{#", "#}")
SECTIONS = ("warnings", "tree", "schema")
DEFAULT_SECTIONS = ("warnings", "tree")
DIVIDER_WIDTH = 64


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    sources = [_read(template) for template in args.templates]

    if unreadable := [source for source in sources if isinstance(source, str)]:
        for error in unreadable:
            print(error, file=sys.stderr)
        return 2

    reports = [(label, analyze_jinja_template(text)) for label, text in sources]
    sections = SECTIONS if args.all else tuple(s for s in SECTIONS if getattr(args, s)) or DEFAULT_SECTIONS

    for index, (label, report) in enumerate(reports):
        if index:
            print()
        _print_text(label, report, sections, show_filename=len(reports) > 1)

    return 1 if any(report.diagnostics for _, report in reports) else 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jinjutsu", description="Report what data a Jinja template needs and what is wrong with it"
    )
    parser.add_argument("templates", nargs="+", metavar="TEMPLATE", help="template files, or template text itself")
    parser.add_argument("--warnings", action="store_true", help="print what is wrong with the template")
    parser.add_argument("--tree", action="store_true", help="print the data it needs as an indented tree")
    parser.add_argument("--schema", action="store_true", help="print the data it needs as a JSON Schema")
    parser.add_argument("--all", action="store_true", help="print all three sections")
    return parser


def _read(template: str) -> tuple[str, str] | str:
    """Label and text for one argument, or a formatted error when it yields neither"""
    path = Path(template)
    if path.is_file():  # Swallows the OSError a whole template passed as a path would otherwise raise
        try:
            # Word writes a BOM often enough that utf-8-sig is the safer read for the templates this targets
            return str(path), path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            if path.suffix.lower() == ".docx":
                return _error_to_string(
                    template,
                    problem="Document is a .docx file, not a text file",
                    fix="Extract text into a .txt file and try again",
                    reason="We can't directly read docx files",
                )
            return _error_to_string(
                template,
                problem="Not UTF-8 text",
                fix="Re-save the file as UTF-8, or pass the template text itself",
                reason="A byte in it does not decode, so it is either binary or a legacy encoding",
            )
        except OSError as error:
            return _error_to_string(template, problem=error.strerror or "Not readable", fix="Check its permissions")
    if any(marker in template for marker in TEMPLATE_MARKERS):
        return INLINE_LABEL, template
    if path.is_dir():
        return _error_to_string(template, problem="Is a directory", fix="Pass the template files inside it")
    return _error_to_string(template, problem="No such file", fix="Check the path, or quote the template text itself")


def _error_to_string(template: str, *, problem: str, fix: str, reason: str | None = None) -> str:
    """An unreadable argument, laid out the way warning_to_string lays out a warning"""
    parts = [f"Error: {template}", f"  Problem: {problem}", f"  Fix:     {fix}"]
    if reason:
        parts.append(f"  Reason:  {reason}")
    return "\n".join(parts)


def _print_text(label: str, report: TemplateReport, sections: tuple[str, ...], *, show_filename: bool) -> None:
    if show_filename:
        print(f"== {label}")

    properties = report.schema["properties"]
    blocks = []
    if "warnings" in sections and report.diagnostics:
        blocks.append(("warnings", "\n".join(report.diagnostics)))
    if "tree" in sections and properties:
        blocks.append(("tree", "\n".join(render_tree(properties))))
    if "schema" in sections:
        blocks.append(("schema", json.dumps(report.schema, indent=2)))

    # Only label once there is more than one block, so a lone --schema still redirects to a valid file
    if len(blocks) > 1:
        print("\n\n".join(f"{f'===== {name} '.ljust(DIVIDER_WIDTH, '=')}\n{body}" for name, body in blocks))
    elif blocks:
        print(blocks[0][1])
    elif "tree" not in sections:
        print("Template parsed successfully with no warnings")
    elif "warnings" in sections:
        print("Template parsed successfully but no variables found")
    else:
        # A lone --tree hid the warnings, so print them here rather than exiting 1 in silence
        empty = "No variables parsed from template. Warnings:"
        print("\n".join([empty, "", *report.diagnostics]) if report.diagnostics else empty)


if __name__ == "__main__":
    sys.exit(main())
