from __future__ import annotations

from typing import Literal, NamedTuple, TypedDict


class VariableNodeBase(TypedDict):
    type: Literal["string", "boolean", "list", "object"]


class VariableNode(VariableNodeBase, total=False):
    item_format: Literal["string", "object"]
    properties: dict[str, VariableNode]


class TemplateReport(NamedTuple):
    variables: dict[str, VariableNode]  # the variable tree described in README.md, empty when the template won't parse
    diagnostics: list[str]  # every problem found, in the order a reader should see them


class PrintedPath(NamedTuple):
    """
    A variable printed with {{ }}, split into its root name and the fields read off it

    {{ case.header.title }} on line 4  ->  PrintedPath(4, "case", ["header", "title"])
    {{ amount }} on line 1             ->  PrintedPath(1, "amount", [])
    """

    line_no: int
    root: str
    attrs: list[str]


class WalkResult(NamedTuple):
    root: dict[str, VariableNode]  # the variable tree
    warnings: list[str]  # a name the template uses as both a value and an object
    conflict_paths: set[str]  # the paths behind those warnings, so a later check doesn't double up
    printed: list[PrintedPath]  # bare {{ x }} prints, judged once the tree is finished
