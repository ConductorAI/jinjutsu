"""
Derive a template's variable schema from its Jinja AST.

The schema is a tree of SchemaField nodes, one tree per top-level variable. For example:

    {{ case.header.title }}
    {% for s in case.sections %}{{ s.name }}{% endfor %}
    {% if case.sealed %}SEALED{% endif %}

    case                object           -> {"header": ..., "sections": [...], "sealed": true}
    |-- header          object           -> {"title": "..."}
    |   `-- title       string
    |-- sections        list of objects  -> [{"name": "..."}, {"name": "..."}]
    |   `-- name        string              a field on each section, not on the list
    `-- sealed          boolean

Objects and lists are interior nodes while strings and booleans are leaves.

Two parts of the shape are easy to misread:
- properties means one thing per type. On an object it is that object's own fields. On a list it is
  the fields of one element, so sections.properties.name says every section has a name and never
  that the list itself has one. A loop is what puts it there: {% for s in sections %} binds s to
  the sections node, so {{ s.name }} writes name into that node's properties.
- item_format says what one element of a list looks like. _refine_list_formats derives it from
  whether the list ended up with properties, so it carries nothing the tree does not already say.
  It exists for the agent prompt. A list of lists has no representation, so a grid is flattened.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum, auto
from typing import Literal, NamedTuple, TypedDict

from jinja2 import TemplateSyntaxError, meta, nodes
from jinja2.visitor import NodeVisitor

from .jinja_utils import NamePathSegment, format_warning, name_path, parse_template, target_names, unwrap_filters

SchemaType = Literal["string", "boolean", "list", "object"]
ItemFormat = Literal["string", "object"]


class _SchemaFieldBase(TypedDict):
    type: SchemaType


class SchemaField(_SchemaFieldBase, total=False):
    item_format: ItemFormat
    properties: dict[str, SchemaField]


class LeafUse(Enum):
    # Read for its value, e.g. {{ x }} or {% if x == 'FINAL' %}
    VALUE = auto()
    # Tested for truthiness, e.g. {% if x %}
    GUARD = auto()
    # Compared against a boolean literal, e.g. {% if x == true %}
    BOOLEAN = auto()


class TemplateAnalysis(NamedTuple):
    """
    variables: the schema tree described in the module docstring, keyed by top-level name
    conflicts: warnings for variables used in two incompatible ways
    """

    variables: dict[str, SchemaField]
    conflicts: list[str]


def analyze_template(text: str) -> TemplateAnalysis:
    """Walk a template once to derive both its variable schema and conflict warnings."""
    try:
        ast = parse_template(text)
    except TemplateSyntaxError:
        return TemplateAnalysis({}, [])

    visitor = SchemaVisitor()
    visitor.visit(ast)

    # find_undeclared_variables already decides which names the template requires
    # the visitor only supplies the structure for those variables
    required = meta.find_undeclared_variables(ast)
    variables: dict[str, SchemaField] = {name: visitor.root.get(name, {"type": "string"}) for name in sorted(required)}
    _refine_list_formats(variables)

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
    return TemplateAnalysis(variables, list(dict.fromkeys(conflicts)))


def _lookup_path(schema: dict[str, SchemaField], root: str, attrs: list[str]) -> SchemaField | None:
    node = schema.get(root)
    for segment in attrs:
        if not node:
            return None
        node = node.get("properties", {}).get(segment)
    return node


def _refine_list_formats(schema: dict[str, SchemaField]) -> None:
    """Derive item_format for every list in the tree, now that its item's fields are known."""
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


class SchemaVisitor(NodeVisitor):
    """
    Build the schema tree in `root` by walking the AST once.

    Terms used here and in the methods below:

    node
        One entry in the schema tree, a SchemaField. An object or a list holds other nodes under
        `properties`. A string or a boolean is a leaf.
    path
        A chain of names read from the template, such as `case.header.title`, split into a root
        name and its following segments.
    printed path
        A path that is the whole of a `{{ }}` expression, so its value lands in the document.
        `{{ case.title }}` counts. `{{ items | length }}` does not, because that prints a count
        rather than the list.
    local
        A name the template invents rather than one the user supplies: a loop target, a set
        target, or a macro, call or with block parameter.
    frame
        One dict mapping the locals of a single nesting level to the tree node each is bound to.
    scope
        The stack of frames. `visit_For` and the parameterized blocks push a frame on entry and
        pop it on exit, and `_lookup_frame` searches the stack innermost first.

    A frame holds a pointer into the tree rather than a copy, so a loop target binds to the very
    list node it iterates and `{{ s.name }}` writes `name` into that list's properties. That is how
    a list comes to describe its item.

    A local must never be reported as a variable, since nobody supplies one. `_locate_leaf` looks a
    leading name up in `scope` first and continues from the node it is bound to, so `s` finds
    `sections` and is then discarded instead of becoming a key in `root`.

    `conflicts` and `printed` are gathered here because only this pass sees how each path is used.
    Every visit_* method must set `lineno`, or a warning will cite a stale line.
    """

    def __init__(self) -> None:
        self.root: dict[str, SchemaField] = {}
        self.scope: list[dict[str, SchemaField]] = [{}]
        self.conflicts: list[str] = []
        self.conflict_paths: set[str] = set()
        # Leaves seen only as a truthiness guard, which says nothing about their shape
        self.guarded: list[SchemaField] = []
        # Paths printed on their own, as {{ a.b }} rather than inside a larger expression
        self.printed: list[tuple[int, str, list[str]]] = []
        self.lineno = 0

    def visit_Output(self, node: nodes.Output) -> None:  # noqa: N802
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
        # {% for x in items | sort %} still iterates items
        # Filter arguments are picked up by find_undeclared_variables.
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

    def visit_With(self, node: nodes.With) -> None:  # noqa: N802
        self.lineno = node.lineno
        # Read the values before binding, so {% with a = a %} still records the outer name.
        for value in node.values:
            self._record_load(value)
        self._visit_parameterized_block(node.targets, node.body)

    def visit_Macro(self, node: nodes.Macro) -> None:  # noqa: N802
        self._visit_parameterized_block(node.args, node.body)

    def visit_CallBlock(self, node: nodes.CallBlock) -> None:  # noqa: N802
        self._record_load(node.call)
        self._visit_parameterized_block(node.args, node.body)

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

    def _visit_parameterized_block(self, targets: Sequence[nodes.Node], body: list[nodes.Node]) -> None:
        """Walk a macro, call, or with block with its locals bound, so they stay out of the schema."""
        frame: dict[str, SchemaField] = {}
        for target in targets:
            for name in target_names(target):
                frame[name] = {"type": "object", "properties": {}}
        self.scope.append(frame)
        for child in body:
            self.visit(child)
        self.scope.pop()

    def _record_printed(self, node: nodes.Node) -> None:
        name = name_path(node)
        if not name:
            return
        root, segments = name
        if self._lookup_frame(root) or any(isinstance(segment, int) for segment in segments):
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
            self._record_path(*name, use=LeafUse.VALUE)
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
            self._record_path(*name, use=LeafUse.GUARD)
            return
        self._record_load(node)

    def _record_boolean_comparison(self, node: nodes.Node) -> bool:
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
        self._record_path(*name, use=LeafUse.BOOLEAN)
        return True

    def _record_path(self, root: str, attrs: list[NamePathSegment], use: LeafUse) -> None:
        location = self._locate_leaf(root, attrs)
        if not location:
            return
        container, key = location
        self._set_leaf(container, key, use)

    def _ensure_list(self, root: str, attrs: list[NamePathSegment]) -> SchemaField:
        location = self._locate_leaf(root, attrs)
        if not location:
            return {"type": "list"}
        container, key = location
        existing = container.get(key)
        if existing and existing.get("type") == "list":
            return existing
        node: SchemaField = {"type": "list"}
        container[key] = node
        return node

    def _locate_leaf(self, root: str, attrs: list[NamePathSegment]) -> tuple[dict[str, SchemaField], str] | None:
        frame = self._lookup_frame(root)
        if not attrs:
            return frame or self.root, root

        # A local starts from the node it is bound to, so its segments land on that node.
        container = frame[root].setdefault("properties", {}) if frame else self.root
        key: str | None = None if frame else root
        path = [root]

        for segment in attrs:
            if isinstance(segment, int):
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
        """Note a object field access from a path the template has already established as a single value."""
        existing = container.get(key)
        if any(leaf is existing for leaf in self.guarded):
            # {% if section %}{{ section.title }}{% endif %} guards an optional object, not a clash
            return
        if not existing or existing.get("type") not in ("string", "boolean"):
            return
        self.conflict_paths.add(path)
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

    def _set_leaf(self, container: dict[str, SchemaField], key: str, use: LeafUse) -> None:
        existing = container.get(key)
        if not existing:
            leaf: SchemaField = {"type": "string"} if use is LeafUse.VALUE else {"type": "boolean"}
            container[key] = leaf
            if use is LeafUse.GUARD:
                self.guarded.append(leaf)
            return
        if use is not LeafUse.GUARD:
            # Any other use pins the shape, so the leaf stops being refinable
            self.guarded = [leaf for leaf in self.guarded if leaf is not existing]
        if existing.get("type") == "boolean" and use is LeafUse.VALUE:
            existing["type"] = "string"

    def _lookup_frame(self, name: str) -> dict[str, SchemaField] | None:
        for frame in reversed(self.scope):
            if name in frame:
                return frame
        return None
