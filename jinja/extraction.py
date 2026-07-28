from __future__ import annotations

from enum import Enum, auto
from typing import Literal, TypedDict

from jinja2 import TemplateSyntaxError, meta, nodes
from jinja2.visitor import NodeVisitor

from .jinja_utils import (
    NamePathSegment,
    PathSegment,
    format_warning,
    name_path,
    parse_template,
    target_names,
    unwrap_filters,
)

SchemaType = Literal["string", "boolean", "list", "object"]
ItemFormat = Literal["string", "object"]


class _SchemaFieldBase(TypedDict):
    type: SchemaType


class SchemaField(_SchemaFieldBase, total=False):
    item_format: ItemFormat
    properties: dict[str, SchemaField]


class _LeafUse(Enum):
    """How a path was used, which decides both its type and whether a later field read conflicts."""

    # Read for its value, e.g. {{ x }} or {% if x == 'FINAL' %}
    VALUE = auto()
    # Tested for truthiness, e.g. {% if x %}
    GUARD = auto()
    # Compared against a boolean literal, e.g. {% if x == true %}
    BOOLEAN = auto()


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


def find_schema_conflicts(text: str) -> list[str]:
    """
    Report places where a template uses one path in two incompatible ways.

    Nothing else catches these: the schema can only describe a path one way, and Jinja renders the
    result without error, so the document silently gets an empty field or a Python repr.
    """
    try:
        ast = parse_template(text)
    except TemplateSyntaxError:
        return []

    visitor = _SchemaVisitor()
    visitor.visit(ast)

    conflicts = list(visitor.conflicts)
    for lineno, root, attrs in visitor.printed:
        node = _lookup_path(visitor.root, root, attrs)
        node_type = node.get("type") if node else None
        path = ".".join([root, *attrs])
        # A path already reported above has the same root cause, so one warning is enough.
        if node_type not in ("object", "list") or path in visitor.conflict_paths:
            continue
        if node_type == "object":
            article, rendered = "an object", "{'field': ...}"
            fix = "print a single field, e.g. {{ " + path + ".field }}"
        else:
            article, rendered = "a list", "['item', ...]"
            fix = "loop over it with {% for item in " + path + " %}"
        conflicts.append(
            format_warning(
                line_no=lineno,
                title=f"'{path}' is printed as a whole {node_type}",
                found="{{ " + path + " }}",
                fix=fix,
                reason=(
                    f"the template also reads fields from '{path}', so it receives {article}. "
                    f"Printing it renders {rendered} into the document."
                ),
            )
        )
    # The same mistake repeated on one line produces the same message twice, and the UI keys
    # warnings by their text.
    return list(dict.fromkeys(conflicts))


def _lookup_path(schema: dict[str, SchemaField], root: str, attrs: list[str]) -> SchemaField | None:
    """Read a dotted path out of an already-built schema without creating anything."""
    node = schema.get(root)
    for segment in attrs:
        if not node:
            return None
        node = node.get("properties", {}).get(segment)
    return node


def _refine_list_formats(schema: dict[str, SchemaField]) -> None:
    """Recursively refine list item_format based on whether objects have properties."""
    for var_info in schema.values():
        if var_info.get("type") == "list":
            if "properties" in var_info and var_info["properties"]:
                var_info["item_format"] = "object"
                _refine_list_formats(var_info["properties"])
            else:
                var_info["item_format"] = "string"
                var_info.pop("properties", None)
        elif var_info.get("type") == "object":
            _refine_list_formats(var_info.get("properties", {}))


class _SchemaVisitor(NodeVisitor):
    """
    Walk a parsed Jinja AST to infer variable type and structure (list / object / string / boolean).

    find_undeclared_variables only decides which top-level names are referenced. This visitor
    supplies the fields on those names so the full data shape can be generated. Loop targets and
    set assignments are tracked as local scope so their names never leak into the schema.

    The walk also collects `conflicts` and `printed` for find_schema_conflicts, since only this
    pass sees how each path is used. Every visit_* method must set `lineno`, or those warnings
    will cite a stale line.
    """

    def __init__(self) -> None:
        self.root: dict[str, SchemaField] = {}
        self.scope: list[dict[str, SchemaField]] = [{}]
        self.conflicts: list[str] = []
        self.conflict_paths: set[str] = set()
        # Leaves seen only as a truthiness guard. That test says nothing about the shape of the
        # value, so a later field read refines the leaf into an object instead of conflicting.
        self.guarded: list[SchemaField] = []
        # Paths printed on their own, as {{ a.b }} rather than inside a larger expression
        self.printed: list[tuple[int, str, list[str]]] = []
        self.lineno = 0

    def visit_Output(self, node: nodes.Output) -> None:  # noqa: N802
        # Jinja merges a run of adjacent text and expressions into one Output node, so each child
        # carries the only accurate line number.
        for child in node.nodes:
            self.lineno = child.lineno
            self._record_printed(child)
            self._record_load(child)

    def visit_If(self, node: nodes.If) -> None:  # noqa: N802
        self.lineno = node.test.lineno
        self._record_test(node.test)
        for child in node.body:
            self.visit(child)
        for child in node.elif_:
            self.visit(child)
        for child in node.else_:
            self.visit(child)

    def visit_For(self, node: nodes.For) -> None:  # noqa: N802
        self.lineno = node.iter.lineno
        frame: dict[str, SchemaField] = {}
        # A filtered iterable is still the same list, e.g. {% for x in items | sort %}
        # Any names in the filter arguments are covered by find_undeclared_variables.
        name = name_path(unwrap_filters(node.iter))
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
        self.lineno = node.lineno
        for target in target_names(node.target):
            self.scope[-1][target] = {"type": "object", "properties": {}}
        self._record_load(node.node)

    def visit_AssignBlock(self, node: nodes.AssignBlock) -> None:  # noqa: N802
        self.lineno = node.lineno
        for target in target_names(node.target):
            self.scope[-1][target] = {"type": "object", "properties": {}}
        for child in node.body:
            self.visit(child)

    def _record_printed(self, node: nodes.Node) -> None:
        """
        Note a path printed on its own, so find_schema_conflicts can catch a whole container
        reaching the document. Only a bare path counts, so a legitimate {{ items | length }} is
        ignored: that is a Filter, not a print of items itself.
        """
        name = name_path(node)
        if not name:
            return
        root, segments = name
        if self._lookup_frame(root) or any(segment is PathSegment.LIST_INDEX for segment in segments):
            return
        self.printed.append((self.lineno, root, [segment for segment in segments if isinstance(segment, str)]))

    def _record_load(self, node: nodes.Node) -> None:
        if isinstance(node, nodes.CondExpr):
            self._record_test(node.test)
            self._record_load(node.expr1)
            if node.expr2:
                self._record_load(node.expr2)
            return
        name = name_path(node)
        if name:
            self._record_path(*name, use=_LeafUse.VALUE)
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
            self._record_path(*name, use=_LeafUse.GUARD)
            return
        self._record_load(node)

    def _record_boolean_comparison(self, node: nodes.Node) -> bool:
        """
        Record a name compared against the literal true or false as a boolean.

        Only the boolean literals qualify, since no string can satisfy `x == true`. A quoted
        `x == 'true'` is a string Const and falls through to the string path.
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
        self._record_path(*name, use=_LeafUse.BOOLEAN)
        return True

    def _record_path(self, root: str, attrs: list[NamePathSegment], use: _LeafUse) -> None:
        resolved = self._resolve(root, attrs)
        if not resolved:
            return
        container, key = resolved
        self._set_leaf(container, key, use)

    def _ensure_list(self, root: str, attrs: list[NamePathSegment]) -> SchemaField:
        # item_format is assigned later by _refine_list_formats once the item's shape is known.
        resolved = self._resolve(root, attrs)
        if not resolved:
            return {"type": "list"}
        container, key = resolved
        existing = container.get(key)
        if existing and existing.get("type") == "list":
            return existing
        node: SchemaField = {"type": "list"}
        container[key] = node
        return node

    def _resolve(self, root: str, attrs: list[NamePathSegment]) -> tuple[dict[str, SchemaField], str] | None:
        """
        Resolve a name path to the container holding its leaf and that leaf's key, creating
        intermediate objects and lists along the way.

        Returns None when there is no leaf to record: the path ends in a subscript (items[0], which
        only tells us items is a list), or nests one subscript in another (matrix[0][1], a shape
        this schema cannot express).
        """
        frame = self._lookup_frame(root)
        if not attrs:
            return frame or self.root, root

        # A loop or set target resolves into its scope frame, so writes against it never reach the
        # schema. Its remaining segments continue from the bound node's own item shape.
        container = frame[root].setdefault("properties", {}) if frame else self.root
        key: str | None = None if frame else root
        path = [root]

        for segment in attrs:
            if segment is PathSegment.LIST_INDEX:
                if not key:
                    return None
                container = self._ensure_container(container, key, as_list=True)
                key = None
            elif not key:
                key = segment
                path.append(segment)
            else:
                self._record_container_conflict(container, key, ".".join(path), segment)
                container = self._ensure_container(container, key, as_list=False)
                key = segment
                path.append(segment)
        return (container, key) if key else None

    def _record_container_conflict(self, container: dict[str, SchemaField], key: str, path: str, segment: str) -> None:
        """Note a field read from a path the template has already established as a list or a value."""
        existing = container.get(key)
        if any(leaf is existing for leaf in self.guarded):
            # {% if section %}{{ section.title }}{% endif %} is a common way to guard an optional object, not a clash
            return
        existing_type = existing.get("type") if existing else None
        if existing_type in ("list", "string", "boolean"):
            self.conflict_paths.add(path)
        if existing_type == "list":
            self.conflicts.append(
                format_warning(
                    line_no=self.lineno,
                    title=f"'{path}' is used as both a list and an object",
                    found=f"{path}.{segment}",
                    fix=(
                        f"loop over '{path}' and read '{segment}' from the loop item, or give the "
                        f"two uses different names"
                    ),
                    reason=(
                        f"the template also loops over '{path}'. A list has no named fields, so "
                        f"'{path}.{segment}' renders empty."
                    ),
                )
            )
        elif existing_type in ("string", "boolean"):
            self.conflicts.append(
                format_warning(
                    line_no=self.lineno,
                    title=f"'{path}' is used as both a value and an object",
                    found=f"{path}.{segment}",
                    fix="give the two uses different names",
                    reason=(
                        f"the template also uses '{path}' as a single value, so it cannot also "
                        f"carry a '{segment}' field. One of the two renders empty."
                    ),
                )
            )

    def _ensure_container(self, container: dict[str, SchemaField], key: str, as_list: bool) -> dict[str, SchemaField]:
        existing = container.get(key)
        if existing and existing.get("type") in ("object", "list"):
            return existing.setdefault("properties", {})
        properties: dict[str, SchemaField] = {}
        container[key] = {"type": "list" if as_list else "object", "properties": properties}
        return properties

    def _set_leaf(self, container: dict[str, SchemaField], key: str, use: _LeafUse) -> None:
        existing = container.get(key)
        if not existing:
            leaf: SchemaField = {"type": "string"} if use is _LeafUse.VALUE else {"type": "boolean"}
            container[key] = leaf
            if use is _LeafUse.GUARD:
                self.guarded.append(leaf)
            return
        if use is not _LeafUse.GUARD:
            # Any other use pins the leaf's shape, so it is no longer refinable.
            self.guarded = [leaf for leaf in self.guarded if leaf is not existing]
        if existing.get("type") == "boolean" and use is _LeafUse.VALUE:
            existing["type"] = "string"

    def _lookup_frame(self, name: str) -> dict[str, SchemaField] | None:
        for frame in reversed(self.scope):
            if name in frame:
                return frame
        return None
