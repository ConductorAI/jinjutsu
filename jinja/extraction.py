from __future__ import annotations

from typing import Literal, TypedDict

from jinja2 import TemplateSyntaxError, meta, nodes
from jinja2.visitor import NodeVisitor

from .jinja_utils import name_path, parse_template, target_names

SchemaType = Literal["string", "boolean", "list", "object"]
ItemFormat = Literal["string", "object"]


class _SchemaFieldBase(TypedDict):
    type: SchemaType


class SchemaField(_SchemaFieldBase, total=False):
    item_format: ItemFormat
    properties: dict[str, SchemaField]


def extract_template_variables(text: str) -> dict[str, SchemaField]:
    """
    Extract all Jinja2 variables from text with nested structure support.

    Returns:
        Dictionary mapping top-level variable names to their schema:
        {
            "RELEASE_COUNTRIES": {
                "type": "list",
                "item_format": "string"
            },
            "SECTIONS": {
                "type": "list",
                "item_format": "object",
                "properties": {
                    "TITLE": {"type": "string"},
                    "AUTHORIZED": {
                        "type": "list",
                        "item_format": "object",
                        "properties": {
                            "TITLE": {"type": "string"},
                            "CONTENTS": {"type": "list", "item_format": "string"}
                        }
                    }
                }
            }
        }
    """
    try:
        ast = parse_template(text)
    except TemplateSyntaxError:
        # A template that fails to parse cannot be rendered; validate_template_jinja surfaces
        # the syntax errors to the user, so there is no schema to produce here.
        return {}

    required = meta.find_undeclared_variables(ast)

    visitor = _SchemaVisitor()
    visitor.visit(ast)

    # find_undeclared_variables is the source of truth for which top-level names the
    # template requires; the visitor only supplies structure for those names.
    schema: dict[str, SchemaField] = {name: visitor.root.get(name, {"type": "string"}) for name in sorted(required)}
    _refine_list_formats(schema)
    return schema


def _refine_list_formats(schema: dict[str, SchemaField]) -> None:
    """Recursively refine list item_format based on whether objects have properties."""
    for var_info in schema.values():
        if var_info.get("type") == "list":
            if "properties" in var_info and var_info["properties"]:
                var_info["item_format"] = "object"
                _refine_list_formats(var_info["properties"])
            else:
                var_info["item_format"] = "string"
        elif var_info.get("type") == "object":
            _refine_list_formats(var_info.get("properties", {}))


class _SchemaVisitor(NodeVisitor):
    """
    Walk a parsed Jinja AST to infer variable type and structure (list / object / string / boolean).

    find_undeclared_variables only decides which top-level names are referenced. This visitor
    supplies the fields on those names so the full data shape can be generated. Loop targets and
    set assignments are tracked as local scope so their names never leak into the schema.
    """

    def __init__(self) -> None:
        self.root: dict[str, SchemaField] = {}
        self.scope: list[dict[str, SchemaField]] = [{}]

    def visit_Output(self, node: nodes.Output) -> None:  # noqa: N802
        for child in node.nodes:
            self._record_load(child)

    def visit_If(self, node: nodes.If) -> None:  # noqa: N802
        self._record_test(node.test)
        for child in node.body:
            self.visit(child)
        for child in node.elif_:
            self.visit(child)
        for child in node.else_:
            self.visit(child)

    def visit_For(self, node: nodes.For) -> None:  # noqa: N802
        frame: dict[str, SchemaField] = {}
        name = name_path(node.iter)
        if not name:
            self._record_load(node.iter)
        list_node: SchemaField = self._ensure_list(*name) if name else {"type": "list"}
        for target in target_names(node.target):
            frame[target] = list_node
        self.scope.append(frame)
        if node.test:
            self._record_test(node.test)
        for child in node.body:
            self.visit(child)
        for child in node.else_:
            self.visit(child)
        self.scope.pop()

    def visit_Assign(self, node: nodes.Assign) -> None:  # noqa: N802
        for target in target_names(node.target):
            self.scope[-1][target] = {"type": "object", "properties": {}}
        self._record_load(node.node)

    def visit_AssignBlock(self, node: nodes.AssignBlock) -> None:  # noqa: N802
        for target in target_names(node.target):
            self.scope[-1][target] = {"type": "object", "properties": {}}
        for child in node.body:
            self.visit(child)

    def _record_load(self, node: nodes.Node) -> None:
        if isinstance(node, nodes.CondExpr):
            self._record_test(node.test)
            self._record_load(node.expr1)
            if node.expr2:
                self._record_load(node.expr2)
            return
        name = name_path(node)
        if name:
            self._record_path(*name, leaf_bool=False)
            return
        for child in node.iter_child_nodes():
            self._record_load(child)

    def _record_test(self, node: nodes.Node) -> None:
        if isinstance(node, (nodes.And, nodes.Or)):
            self._record_test(node.left)
            self._record_test(node.right)
            return
        if isinstance(node, nodes.Not):
            self._record_test(node.node)
            return
        if self._record_boolean_comparison(node):
            return
        name = name_path(node)
        if name:
            self._record_path(*name, leaf_bool=True)
            return
        self._record_load(node)

    def _record_boolean_comparison(self, node: nodes.Node) -> bool:
        """
        Record a name compared against the literal true or false as a boolean.

        Only the boolean literals qualify: no string can satisfy `x == true`, so the variable must
        be supplied as a real boolean. A quoted comparison like `x == 'true'` is a string Const and
        falls through to the string path.
        """
        if not isinstance(node, nodes.Compare) or len(node.ops) != 1:
            return False
        operand = node.ops[0]
        if operand.op not in ("eq", "ne") or not isinstance(operand.expr, nodes.Const):
            return False
        if not isinstance(operand.expr.value, bool):
            return False
        name = name_path(node.expr)
        if not name:
            return False
        self._record_path(*name, leaf_bool=True)
        return True

    def _record_path(self, root: str, attrs: list[str], leaf_bool: bool) -> None:
        container, key = self._resolve(root, attrs)
        self._set_leaf(container, key, leaf_bool)

    def _ensure_list(self, root: str, attrs: list[str]) -> SchemaField:
        container, key = self._resolve(root, attrs)
        existing = container.get(key)
        if existing and existing.get("type") == "list":
            return existing
        # item_format is assigned later by _refine_list_formats once the item's shape is known.
        node: SchemaField = {"type": "list"}
        container[key] = node
        return node

    def _resolve(self, root: str, attrs: list[str]) -> tuple[dict[str, SchemaField], str]:
        """
        Resolve a dotted name to the container holding its leaf and that leaf's key, creating
        intermediate objects along the way. Names bound by a loop or set resolve into their scope
        frame, so writes against them never reach the schema.
        """
        frame = self._lookup_frame(root)
        if not attrs:
            return frame or self.root, root
        container = frame[root].setdefault("properties", {}) if frame else self._ensure_object(self.root, root)
        for segment in attrs[:-1]:
            container = self._ensure_object(container, segment)
        return container, attrs[-1]

    def _ensure_object(self, container: dict[str, SchemaField], key: str) -> dict[str, SchemaField]:
        existing = container.get(key)
        if existing and existing.get("type") in ("object", "list"):
            return existing.setdefault("properties", {})
        properties: dict[str, SchemaField] = {}
        container[key] = {"type": "object", "properties": properties}
        return properties

    def _set_leaf(self, container: dict[str, SchemaField], key: str, leaf_bool: bool) -> None:
        existing = container.get(key)
        if not existing:
            container[key] = {"type": "boolean"} if leaf_bool else {"type": "string"}
        elif existing.get("type") == "boolean" and not leaf_bool:
            existing["type"] = "string"

    def _lookup_frame(self, name: str) -> dict[str, SchemaField] | None:
        for frame in reversed(self.scope):
            if name in frame:
                return frame
        return None
