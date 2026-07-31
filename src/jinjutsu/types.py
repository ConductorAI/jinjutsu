from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, NamedTuple


@dataclass
class UnknownNode:
    kind: Literal["unknown"] = "unknown"


@dataclass
class StringNode:
    kind: Literal["string"] = "string"


@dataclass
class BooleanNode:
    kind: Literal["boolean"] = "boolean"


@dataclass
class NumberNode:
    kind: Literal["number"] = "number"


@dataclass
class ObjectNode:
    kind: Literal["object"] = "object"
    properties: dict[str, VariableNode] = field(default_factory=dict)


@dataclass
class ListNode:
    kind: Literal["list"] = "list"
    items: VariableNode = field(default_factory=UnknownNode)


VariableNode = UnknownNode | StringNode | BooleanNode | NumberNode | ObjectNode | ListNode

SCALAR_NODES = (StringNode, BooleanNode, NumberNode)


def child_properties(node: VariableNode) -> dict[str, VariableNode]:
    """The fields readable off a node. On a list those belong to one element, not to the list"""
    if isinstance(node, ObjectNode):
        return node.properties
    if isinstance(node, ListNode):
        return child_properties(node.items)
    return {}


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
