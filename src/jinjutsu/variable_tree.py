"""
Build the variable tree from the jinja AST
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum, auto

from jinja2 import nodes
from jinja2.visitor import NodeVisitor

from .shapes import (
    SCALAR_NODES,
    BooleanNode,
    ListNode,
    NumberNode,
    ObjectNode,
    PrintedPath,
    StringNode,
    UnknownNode,
    VariableNode,
    WalkResult,
)
from .utils.ast_utils import NamePathSegment, jinja_local_variables, split_ast_object_path, strip_list_operations
from .utils.string_utils import read_source_line, warning_to_string

# Where a node lives: a name in a dict, or the element of a list
Slot = tuple[dict[str, VariableNode], str] | ListNode

# Operators a string cannot survive, so every operand is a number
# Multiplication is here because "a" * "b" raises: one side always counts, even when the other repeats
NUMERIC_OPERATORS = (nodes.Sub, nodes.Div, nodes.FloorDiv, nodes.Pow, nodes.Mul)
# Concat and printf read the same as addition and modulo, so a numeric literal has to say which
AMBIGUOUS_OPERATORS = (nodes.Add, nodes.Mod)
# Strings compare lexicographically, so these only say number against a numeric literal
ORDERED_COMPARISONS = ("lt", "lteq", "gt", "gteq")


class LeafUse(Enum):
    VALUE = auto()  # Read for its value, e.g. {{ x }} or {% if x == 'FINAL' %}
    GUARD = auto()  # Tested for truthiness, e.g. {% if x %}
    BOOLEAN = auto()  # Compared against a boolean literal, e.g. {% if x == true %}
    NUMBER = auto()  # Used in arithmetic, e.g. {{ x - 1 }} or {% if x > 5 %}


class VariableTreeVisitor(NodeVisitor):
    """
    Build the variable tree in `root` by walking the AST once. For example:

        {% for s in case.sections %}{{ s.name }}{% endfor %}

        root = {"case": ObjectNode(properties={
                    "sections": ListNode(items=ObjectNode(properties={"name": StringNode()}))})}

    `s` never lands in `root`, since the template invents it and nobody supplies a value for it
    While the loop body is walked, `s` is bound to the `case.sections` list, and its Slot means the
    element of that list, so `{{ s.name }}` writes `name` into `items` rather than into the list

    `self._scope` holds one dict per nesting level, mapping each invented name to the Slot it's bound to
    `visit_For` and the parameterized blocks push a dict on entry and pop it on exit
    `_lookup_frame` searches innermost first, so the inner `s` below shadows the outer one

        {% for s in outer %}{% for s in inner %}{{ s.x }}{% endfor %}{% endfor %}

        root = {"outer": ListNode(), "inner": ListNode(items=ObjectNode(properties={"x": StringNode()}))}

    `walk` returns the tree alongside the warnings and printed paths, because only this pass sees how
    each path is used. Every visit_* method sets `lineno`, otherwise a warning cites a stale line
    """

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self._root: dict[str, VariableNode] = {}
        self._scope: list[dict[str, Slot]] = [{}]
        self._warnings: list[str] = []
        self._conflict_paths: set[str] = set()
        # {{ case }} only looks wrong once {{ case.title }} somewhere else has made `case` an object
        # So record the bare print while we can still see it, and let
        # check_no_objects_printed_directly decide once the tree is finished
        self._printed_paths: list[PrintedPath] = []
        self._lineno = 0

    def walk(self, ast: nodes.Template) -> WalkResult:
        self.visit(ast)
        return WalkResult(self._root, self._warnings, self._conflict_paths, self._printed_paths)

    def visit_Output(self, node: nodes.Output) -> None:  # noqa: N802
        for child in node.nodes:
            self._lineno = child.lineno
            self._record_printed(child)
            self._record_load(child)

    def visit_If(self, node: nodes.If) -> None:  # noqa: N802
        self._lineno = node.test.lineno
        self._record_test(node.test)
        for child in node.body:
            self.visit(child)
        for child in node.elif_:
            self.visit(child)
        for child in node.else_:
            self.visit(child)

    def visit_For(self, node: nodes.For) -> None:  # noqa: N802
        self._lineno = node.iter.lineno
        frame: dict[str, Slot] = {}
        path = split_ast_object_path(strip_list_operations(node.iter))
        if not path:
            self._record_load(node.iter)
        # The target is bound to the list itself, so its slot means "one element of this list"
        list_node = self._ensure_list(*path) if path else ListNode()
        for target in jinja_local_variables(node.target):
            frame[target] = list_node
        self._scope.append(frame)
        if node.test:
            self._record_test(node.test)
        for child in node.body:
            self.visit(child)
        for child in node.else_:
            self.visit(child)
        self._scope.pop()

    def visit_With(self, node: nodes.With) -> None:  # noqa: N802
        self._lineno = node.lineno
        # Read the values before binding, so {% with a = a %} still records the outer name
        for value in node.values:
            self._record_load(value)
        self._visit_parameterized_block(node.targets, node.body)

    def visit_Macro(self, node: nodes.Macro) -> None:  # noqa: N802
        self._lineno = node.lineno
        self._visit_parameterized_block(node.args, node.body)

    def visit_CallBlock(self, node: nodes.CallBlock) -> None:  # noqa: N802
        self._lineno = node.lineno
        self._record_load(node.call)
        self._visit_parameterized_block(node.args, node.body)

    def visit_Assign(self, node: nodes.Assign) -> None:  # noqa: N802
        self._lineno = node.lineno
        for target in jinja_local_variables(node.target):
            self._scope[-1][target] = _discarded_slot(target)
        self._record_load(node.node)

    def visit_AssignBlock(self, node: nodes.AssignBlock) -> None:  # noqa: N802
        self._lineno = node.lineno
        for target in jinja_local_variables(node.target):
            self._scope[-1][target] = _discarded_slot(target)
        for child in node.body:
            self.visit(child)

    def _visit_parameterized_block(self, targets: Sequence[nodes.Node], body: list[nodes.Node]) -> None:
        """Walk a macro, call, or with block with its locals bound, so they stay out of the tree"""
        frame: dict[str, Slot] = {}
        for target in targets:
            for name in jinja_local_variables(target):
                frame[name] = _discarded_slot(name)
        self._scope.append(frame)
        for child in body:
            self.visit(child)
        self._scope.pop()

    def _record_printed(self, node: nodes.Node) -> None:
        path = split_ast_object_path(node)
        if not path:
            return
        root, segments = path
        if self._lookup_frame(root) or any(isinstance(segment, int) for segment in segments):
            return
        self._printed_paths.append(
            PrintedPath(self._lineno, root, [segment for segment in segments if isinstance(segment, str)])
        )

    def _record_load(self, node: nodes.Node) -> None:
        if isinstance(node, nodes.CondExpr):
            self._record_test(node.test)
            self._record_load(node.expr1)
            if node.expr2:
                self._record_load(node.expr2)
            return
        path = split_ast_object_path(node)
        if path:
            self._record_path(*path, use=LeafUse.VALUE)
            return
        if self._record_arithmetic(node):
            return
        for child in node.iter_child_nodes():
            self._record_load(child)

    def _record_arithmetic(self, node: nodes.Node) -> bool:
        """Type the operands of an arithmetic expression, which the generic walk below would flatten"""
        if isinstance(node, (nodes.Neg, nodes.Pos)):
            self._record_operand(node.node, numeric=True)
            return True
        if isinstance(node, NUMERIC_OPERATORS):
            operands = (node.left, node.right)
            numeric = True
        elif isinstance(node, AMBIGUOUS_OPERATORS):
            operands = (node.left, node.right)
            numeric = any(_is_numeric_const(operand) for operand in operands)
        else:
            return False
        for operand in operands:
            self._record_operand(operand, numeric=numeric)
        return True

    def _record_operand(self, node: nodes.Node, *, numeric: bool) -> None:
        path = split_ast_object_path(node)
        if path:
            self._record_path(*path, use=LeafUse.NUMBER if numeric else LeafUse.VALUE)
        else:
            self._record_load(node)

    def _record_test(self, node: nodes.Node) -> None:
        if isinstance(node, (nodes.And, nodes.Or)):
            self._record_test(node.left)
            self._record_test(node.right)
            return
        if isinstance(node, nodes.Not):
            self._record_test(node.node)
            return
        if self._record_boolean_comparison(node) or self._record_numeric_comparison(node):
            return
        path = split_ast_object_path(node)
        if path:
            self._record_path(*path, use=LeafUse.GUARD)
            return
        self._record_load(node)

    def _record_numeric_comparison(self, node: nodes.Node) -> bool:
        if not isinstance(node, nodes.Compare) or len(node.ops) != 1:
            return False
        if node.ops[0].op not in ORDERED_COMPARISONS:
            return False
        # Either side can hold the literal, so {% if 5 < count %} reads the same as {% if count > 5 %}
        for value, other in ((node.expr, node.ops[0].expr), (node.ops[0].expr, node.expr)):
            path = split_ast_object_path(value)
            if path and _is_numeric_const(other):
                self._record_path(*path, use=LeafUse.NUMBER)
                return True
        return False

    def _record_boolean_comparison(self, node: nodes.Node) -> bool:
        if not isinstance(node, nodes.Compare) or len(node.ops) != 1:
            return False
        operand = node.ops[0]
        if operand.op not in ("eq", "ne") or not isinstance(operand.expr, nodes.Const):
            return False
        if not isinstance(operand.expr.value, bool):
            return False
        path = split_ast_object_path(node.expr)
        if not path:
            return False
        self._record_path(*path, use=LeafUse.BOOLEAN)
        return True

    def _record_path(self, root: str, attrs: list[NamePathSegment], use: LeafUse) -> None:
        self._set_leaf(self._locate_leaf(root, attrs), use)

    def _ensure_list(self, root: str, attrs: list[NamePathSegment]) -> ListNode:
        return self._ensure_list_at(self._locate_leaf(root, attrs))

    def _locate_leaf(self, root: str, attrs: list[NamePathSegment]) -> Slot:
        frame = self._lookup_frame(root)
        # A local starts from the slot it's bound to, so its segments land on that node
        slot: Slot = frame[root] if frame else (self._root, root)
        path = [root]

        for segment in attrs:
            if isinstance(segment, int):
                slot = self._ensure_list_at(slot)
            else:
                slot = (self._ensure_object_at(slot, ".".join(path), segment).properties, segment)
                path.append(segment)
        return slot

    def _ensure_list_at(self, slot: Slot) -> ListNode:
        existing = _slot_get(slot)
        if isinstance(existing, ListNode):
            return existing
        # {% if xs %}{% for x in xs %} refined a guard, so the list inherits the guard's optionality
        node = ListNode(guard_only=_guard_only(existing))
        _slot_set(slot, node)
        return node

    def _ensure_object_at(self, slot: Slot, path: str, segment: str) -> ObjectNode:
        existing = _slot_get(slot)
        # A field read off a list belongs to its element, so descend rather than replace the list
        if isinstance(existing, ListNode):
            return self._ensure_object_at(existing, path, segment)
        if isinstance(existing, ObjectNode):
            return existing
        # An element has no name of its own to blame, so only a named slot can clash
        if not isinstance(slot, ListNode):
            self._record_container_conflict(existing, path, segment)
        node = ObjectNode(guard_only=_guard_only(existing))
        _slot_set(slot, node)
        return node

    def _record_container_conflict(self, existing: VariableNode | None, path: str, segment: str) -> None:
        """Record a warning when a path already used as a plain value is now being read as an object"""
        if _guard_only(existing):
            # {% if section %}{{ section.title }}{% endif %} guards an optional object and isn't considered a clash
            return
        if not isinstance(existing, SCALAR_NODES):
            return
        self._conflict_paths.add(path)
        self._warnings.append(
            warning_to_string(
                line_no=self._lineno,
                title=f"'{path}' is used as both a value and an object",
                found=f"{path}.{segment}",
                fix="Give the two uses different names",
                reason=(
                    f"The template also uses '{path}' as a single value, so it can't also "
                    f"carry {'an' if segment[:1].lower() in 'aeiou' else 'a'} '{segment}' field. "
                    f"One of the two renders empty."
                ),
                source_line=read_source_line(self._lines, self._lineno),
            )
        )

    def _set_leaf(self, slot: Slot, use: LeafUse) -> None:
        existing = _slot_get(slot)
        if existing is None or isinstance(existing, UnknownNode):
            _slot_set(slot, _new_leaf(use))
            return
        if use is not LeafUse.GUARD:
            # Any other use settles the type, and means the value has to be supplied after all
            existing.guard_only = False
        # Arithmetic is the most specific thing a scalar can be used for, so it wins over the others
        if use is LeafUse.NUMBER and isinstance(existing, SCALAR_NODES):
            _slot_set(slot, NumberNode())
        elif isinstance(existing, BooleanNode) and use is LeafUse.VALUE:
            _slot_set(slot, StringNode())

    def _lookup_frame(self, name: str) -> dict[str, Slot] | None:
        for frame in reversed(self._scope):
            if name in frame:
                return frame
        return None


def _slot_get(slot: Slot) -> VariableNode | None:
    if isinstance(slot, ListNode):
        return slot.items
    container, key = slot
    return container.get(key)


def _slot_set(slot: Slot, node: VariableNode) -> None:
    if isinstance(slot, ListNode):
        slot.items = node
    else:
        container, key = slot
        container[key] = node


def _new_leaf(use: LeafUse) -> VariableNode:
    if use is LeafUse.NUMBER:
        return NumberNode()
    if use is LeafUse.VALUE:
        return StringNode()
    return BooleanNode(guard_only=use is LeafUse.GUARD)


def _is_numeric_const(node: nodes.Node) -> bool:
    # bool is an int in python, but {% if x == true %} is already read as a boolean elsewhere
    return isinstance(node, nodes.Const) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool)


def _guard_only(node: VariableNode | None) -> bool:
    return node is not None and node.guard_only


def _discarded_slot(name: str) -> Slot:
    """A slot for a name the template invents, so writes to it never reach the tree"""
    return {name: ObjectNode()}, name
