import re

from jinja2 import Environment, TemplateSyntaxError, meta, nodes
from jinja2.visitor import NodeVisitor

from conduit.server.core.logging import get_logger

log = get_logger(__name__)

_JINJA_ENV = Environment()


# docxtpl adds row/cell/paragraph/run prefixes to Jinja tags, e.g. {%tr for ... %} or {{r ... }}
_DOCXTPL_TAG_PREFIX = r"(?:tr|tc|p|r)"


def validate_template_jinja(full_text: str) -> list[str]:
    """
    Validate Jinja2 syntax in a docx template.

    Returns:
        List of warning messages describing any malformed Jinja2 syntax.
        Empty list if template is valid.
    """
    lines = full_text.split("\n")

    warnings = []
    warnings.extend(_check_malformed_tags(lines))
    warnings.extend(_check_mismatched_tags(full_text))

    if not warnings:
        # Only use jinja checker only if the checker we wrote didn't pick up any issues
        # If we use both checkers there will be duplicate errors
        # The jinja checker error messages are not as easy to read as the ones we emit from our custom checks
        warnings.extend(_check_jinja_syntax(full_text))
    return warnings


def extract_template_variables(text: str) -> dict[str, dict]:
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
    normalized = _normalize_docxtpl_prefixes(text)

    try:
        ast = _JINJA_ENV.parse(normalized)
    except TemplateSyntaxError:
        # Malformed template: fall back to best-effort regex extraction so the upload
        # still produces a schema (validate_template_jinja surfaces the syntax errors).
        return _extract_via_tokens(text)

    required = meta.find_undeclared_variables(ast)

    visitor = _SchemaVisitor()
    visitor.visit(ast)

    # find_undeclared_variables is the source of truth for which top-level names the
    # template requires; the visitor only supplies structure for those names.
    schema = {name: visitor.root.get(name, {"type": "string"}) for name in sorted(required)}
    _refine_list_formats(schema)
    return schema


def _extract_via_tokens(text: str) -> dict[str, dict]:
    tokens = _tokenize_template(text)

    # Build nested structure
    root_vars: dict[str, dict] = {}
    context_stack: list[tuple[str, dict]] = []  # Stack of (loop_item_name, parent_schema)

    for token in tokens:
        if token["type"] == "for":
            loop_var = token["loop_var"]
            loop_item = token["loop_item"]

            # Check if this is a nested property access (e.g., SECTION.AUTHORIZED)
            if "." in loop_var:
                parts = loop_var.split(".", 1)
                parent_item = parts[0]
                property_name = parts[1]

                # Find parent in context stack
                for item_name, parent_schema in reversed(context_stack):
                    if item_name == parent_item:
                        if "properties" not in parent_schema:
                            parent_schema["properties"] = {}

                        # Create nested list property
                        parent_schema["properties"][property_name] = {
                            "type": "list",
                            "item_format": "object",  # Will be refined based on usage
                        }
                        context_stack.append((loop_item, parent_schema["properties"][property_name]))
                        break
            else:
                # Top-level loop variable
                if loop_var not in root_vars:
                    root_vars[loop_var] = {
                        "type": "list",
                        "item_format": "object",  # Will be refined based on usage
                    }
                context_stack.append((loop_item, root_vars[loop_var]))

        elif token["type"] == "endfor":
            if context_stack:
                context_stack.pop()

        elif token["type"] == "variable":
            var_name = token["var_name"]

            # Check if it's a property access (e.g., SECTION.TITLE)
            if "." in var_name:
                parts = var_name.split(".", 1)
                parent_item = parts[0]
                property_name = parts[1]

                # Find parent in context stack
                for item_name, parent_schema in reversed(context_stack):
                    if item_name == parent_item:
                        if "properties" not in parent_schema:
                            parent_schema["properties"] = {}

                        parent_schema["properties"][property_name] = {"type": "string"}
                        break
            elif not context_stack and var_name not in root_vars:
                root_vars[var_name] = {"type": "string"}

    _refine_list_formats(root_vars)
    return root_vars


def _check_malformed_tags(lines: list[str]) -> list[str]:
    """Check for malformed Jinja2 tags with extra spaces or missing braces."""
    warnings = []
    for line_num, line in enumerate(lines, start=1):
        # Check for { % instead of {%
        if re.search(r"\{\s+%", line):
            match = re.search(r"\{\s+%.*?%\s*\}", line)
            if match:
                malformed_tag = match.group(0)
                fixed_tag = malformed_tag.replace("{ ", "{").replace(" }", "}")
                warnings.append(
                    f"Line {line_num}: Extra space after '{{' in tag\n"
                    f"  Found: {malformed_tag}\n"
                    f"  Fix:   {fixed_tag}\n"
                    f"  {line}"
                )
        # Check for % } instead of %}
        elif re.search(r"%\s+\}", line) and not re.search(r"\{\s+%", line):
            match = re.search(r"\{%.*?%\s+\}", line)
            if match:
                malformed_tag = match.group(0)
                fixed_tag = malformed_tag.replace("{ ", "{").replace(" }", "}")
                warnings.append(
                    f"Line {line_num}: Extra space before '}}' in tag\n"
                    f"  Found: {malformed_tag}\n"
                    f"  Fix:   {fixed_tag}\n"
                    f"  {line}"
                )

        # Check for incomplete variable tags ({{ without }} or with only one })
        if re.search(r"\{\{[^}]*\}(?!\})", line):
            match = re.search(r"\{\{[^}]*\}(?!\})", line)
            if match:
                incomplete_tag = match.group(0)
                fixed_tag = incomplete_tag + "}"
                warnings.append(
                    f"Line {line_num}: Missing closing '}}}}' in variable tag\n"
                    f"  Found: {incomplete_tag}\n"
                    f"  Fix:   {fixed_tag}\n"
                    f"  {line}"
                )

        # Check for incomplete statement tags ({% without %} or with only one %)
        if re.search(r"\{%[^}]*(?<!%)(?<!%\s)\}(?!\})", line) and not re.search(r"\{%[^}]*%\}", line):
            match = re.search(r"\{%[^}]*\}", line)
            if match:
                incomplete_tag = match.group(0)
                fixed_tag = incomplete_tag[:-1] + "%}"
                warnings.append(
                    f"Line {line_num}: Missing closing '%}}}}' in statement tag\n"
                    f"  Found: {incomplete_tag}\n"
                    f"  Fix:   {fixed_tag}\n"
                    f"  {line}"
                )

    warnings.extend(_check_hyphenated_variables(lines))

    return warnings


def _check_hyphenated_variables(lines: list[str]) -> list[str]:
    """Check for variables containing hyphens, which Jinja2 interprets as subtraction."""
    warnings = []
    for line_num, line in enumerate(lines, start=1):
        for match in re.finditer(r"\{\{\s*([\w.\-]+)\s*\}\}", line):
            var_name = match.group(1)
            if "-" in var_name:
                suggested_name = var_name.replace("-", "_")
                warnings.append(
                    f"Line {line_num}: Variable name contains hyphen(s)\n"
                    f"  Found: {{{{{var_name}}}}}\n"
                    f"  Fix:   {{{{{suggested_name}}}}}\n"
                    f"  Reason: Jinja2 interprets hyphens as subtraction operators. "
                    f"Use underscores instead.\n"
                    f"  {line}"
                )
    return warnings


def _check_mismatched_tags(full_text: str) -> list[str]:
    """Check for mismatched loop and conditional tags."""
    warnings = []

    for_count = len(re.findall(rf"\{{%{_DOCXTPL_TAG_PREFIX}?\s*for\s+", full_text))
    endfor_count = len(re.findall(rf"\{{%{_DOCXTPL_TAG_PREFIX}?\s*endfor\s*%\}}", full_text))
    if for_count != endfor_count:
        warnings.append(
            f"Mismatched loop tags\n"
            f"  Found: {for_count} {{% for %}} tag(s) but {endfor_count} {{% endfor %}} tag(s)\n"
            f"  Fix: Each {{% for %}} must have a corresponding {{% endfor %}}"
        )

    if_count = len(re.findall(rf"\{{%{_DOCXTPL_TAG_PREFIX}?\s*if\s+", full_text))
    endif_count = len(re.findall(rf"\{{%{_DOCXTPL_TAG_PREFIX}?\s*endif\s*%\}}", full_text))
    if if_count != endif_count:
        warnings.append(
            f"Mismatched conditional tags\n"
            f"  Found: {if_count} {{% if %}} tag(s) but {endif_count} {{% endif %}} tag(s)\n"
            f"  Fix: Each {{% if %}} must have a corresponding {{% endif %}}"
        )

    return warnings


def _check_jinja_syntax(full_text: str) -> list[str]:
    """Check Jinja2 syntax by attempting to parse the template."""
    warnings = []
    env = Environment()

    # Strip docxtpl prefixes (tr/tc/p/r) from block and variable tags so the vanilla
    # environment doesn't reject valid docxtpl directives like {%p if ... %} or {{r ... }}.
    # Only the prefix is removed, so line numbers still map to full_text.
    normalized = _normalize_docxtpl_prefixes(full_text)

    try:
        env.parse(normalized)
    except TemplateSyntaxError as e:
        error_msg = str(e)
        line_preview = ""

        if e.lineno:
            lines = full_text.split("\n")
            if 0 < e.lineno <= len(lines):
                line_preview = f"  {lines[e.lineno - 1]}"

        if "expected token 'end of statement block'" in error_msg.lower():
            guidance = "Extra spaces in tag? Use '{{% for %}}' not '{{%  for %}}'"
        elif "unexpected end of template" in error_msg.lower():
            guidance = "Missing closing tag like '{{% endfor %}}' or '{{% endif %}}'"
        elif "expected name or number" in error_msg.lower():
            guidance = "Invalid variable name in '{{{{ }}}}' or '{{% %}}' tag"
        else:
            guidance = "Check for typos or formatting issues"

        if e.lineno and line_preview:
            warning = f"Line {e.lineno}: {guidance}\n{line_preview}\n  Error: {error_msg}"
        else:
            warning = f"Jinja2 syntax error: {guidance}\n  Error: {error_msg}"
        warnings.append(warning)

    return warnings


def _tokenize_template(text: str) -> list[dict]:
    """Tokenize Jinja2 template into for-loops, variables, etc."""
    tokens = []

    # Find all for loops
    for match in re.finditer(rf"\{{%{_DOCXTPL_TAG_PREFIX}?\s*for\s+(\w+)\s+in\s+([\w.]+)\s*%\}}", text):
        loop_item = match.group(1)
        loop_var = match.group(2)
        tokens.append({"type": "for", "loop_item": loop_item, "loop_var": loop_var, "pos": match.start()})

    # Find all endfor
    for match in re.finditer(rf"\{{%{_DOCXTPL_TAG_PREFIX}?\s*endfor\s*%\}}", text):
        tokens.append({"type": "endfor", "pos": match.start()})

    # Find all variables
    # Include hyphens in variable names to detect them (even though Jinja2 interprets hyphens as subtraction)
    for match in re.finditer(rf"\{{\{{(?:{_DOCXTPL_TAG_PREFIX}\s+)?\s*([\w.\-]+)(?:\s*\|[^}}]*)?\s*\}}\}}", text):
        var_name = match.group(1)
        tokens.append({"type": "variable", "var_name": var_name, "pos": match.start()})

    # Sort by position to maintain order
    tokens.sort(key=lambda t: t["pos"])

    return tokens


def _refine_list_formats(schema: dict) -> None:
    """Recursively refine list item_format based on whether objects have properties."""
    for _, var_info in schema.items():
        if var_info.get("type") == "list":
            # If it has properties, it's an object
            if "properties" in var_info and var_info["properties"]:
                var_info["item_format"] = "object"
                # Recursively refine nested lists
                _refine_list_formats(var_info["properties"])
            else:
                # No properties means it's a simple list
                var_info["item_format"] = "string"
        elif var_info.get("type") == "object":
            _refine_list_formats(var_info.get("properties", {}))


def _normalize_docxtpl_prefixes(text: str) -> str:
    """Strip docxtpl row/cell/paragraph/run prefixes so vanilla Jinja can parse the tags."""
    return re.sub(rf"(\{{[%{{]){_DOCXTPL_TAG_PREFIX}?\s+", r"\1 ", text)


def _name_path(node: nodes.Node) -> tuple[str, list[str]] | None:
    """Resolve a Name / Getattr chain to (root_name, attribute_path), else None."""
    attrs: list[str] = []
    current = node
    while isinstance(current, nodes.Getattr):
        attrs.append(current.attr)
        current = current.node
    if isinstance(current, nodes.Name):
        return current.name, list(reversed(attrs))
    return None


def _target_names(target: nodes.Node) -> list[str]:
    """Names bound by a for-loop target or set assignment (handles tuple unpacking)."""
    if isinstance(target, nodes.Name):
        return [target.name]
    if isinstance(target, nodes.Tuple):
        return [item.name for item in target.items if isinstance(item, nodes.Name)]
    return []


class _SchemaVisitor(NodeVisitor):
    """
    Walk a parsed Jinja AST to infer variable structure (list / object / string / boolean).

    find_undeclared_variables decides which top-level names are required; this visitor only
    supplies their shape. Loop targets and set assignments are tracked as local scope so their
    names never leak into the schema.
    """

    def __init__(self) -> None:
        self.root: dict[str, dict] = {}
        self.scope: list[dict[str, dict]] = [{}]

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
        frame: dict[str, dict] = {}
        name_path = _name_path(node.iter)
        if name_path:
            list_node = self._ensure_list(*name_path)
        else:
            self._record_load(node.iter)
            list_node = {"type": "list", "item_format": "object"}
        for target in _target_names(node.target):
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
        for target in _target_names(node.target):
            self.scope[-1][target] = {"type": "object", "properties": {}}
        self._record_load(node.node)

    def visit_AssignBlock(self, node: nodes.AssignBlock) -> None:  # noqa: N802
        for target in _target_names(node.target):
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
        name_path = _name_path(node)
        if name_path:
            self._record_path(*name_path, leaf_bool=False)
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
        name_path = _name_path(node)
        if name_path:
            self._record_path(*name_path, leaf_bool=True)
            return
        self._record_load(node)

    def _record_path(self, root: str, attrs: list[str], leaf_bool: bool) -> None:
        local = self._lookup_local(root)
        if local is not None:
            if not attrs:
                return
            self._descend_and_set(local.setdefault("properties", {}), attrs, leaf_bool)
        elif not attrs:
            self._set_leaf(self.root, root, leaf_bool)
        else:
            obj = self._ensure_object(self.root, root)
            self._descend_and_set(obj["properties"], attrs, leaf_bool)

    def _ensure_list(self, root: str, attrs: list[str]) -> dict:
        local = self._lookup_local(root)
        if local is not None:
            if not attrs:
                return local
            return self._make_list(local.setdefault("properties", {}), attrs)
        if not attrs:
            return self._make_list(self.root, [root])
        obj = self._ensure_object(self.root, root)
        return self._make_list(obj["properties"], attrs)

    def _descend_and_set(self, container: dict, attrs: list[str], leaf_bool: bool) -> None:
        for segment in attrs[:-1]:
            container = self._ensure_object(container, segment)["properties"]
        self._set_leaf(container, attrs[-1], leaf_bool)

    def _make_list(self, container: dict, attrs: list[str]) -> dict:
        for segment in attrs[:-1]:
            container = self._ensure_object(container, segment)["properties"]
        key = attrs[-1]
        existing = container.get(key)
        if existing and existing.get("type") == "list":
            return existing
        node = {"type": "list", "item_format": "object"}
        container[key] = node
        return node

    def _ensure_object(self, container: dict, key: str) -> dict:
        existing = container.get(key)
        if existing and existing.get("type") in ("object", "list"):
            existing.setdefault("properties", {})
            return existing
        node = {"type": "object", "properties": {}}
        container[key] = node
        return node

    def _set_leaf(self, container: dict, key: str, wants_bool: bool) -> None:
        existing = container.get(key)
        if existing is None:
            container[key] = {"type": "boolean" if wants_bool else "string"}
        elif existing.get("type") == "boolean" and not wants_bool:
            existing["type"] = "string"

    def _lookup_local(self, name: str) -> dict | None:
        for frame in reversed(self.scope):
            if name in frame:
                return frame[name]
        return None
