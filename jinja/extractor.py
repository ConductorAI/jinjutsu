import re

from jinja2 import Environment, TemplateSyntaxError

from conduit.server.core.logging import get_logger

log = get_logger(__name__)


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

    for_count = len(re.findall(r"\{%\s*for\s+", full_text))
    endfor_count = len(re.findall(r"\{%\s*endfor\s*%\}", full_text))
    if for_count != endfor_count:
        warnings.append(
            f"Mismatched loop tags\n"
            f"  Found: {for_count} {{% for %}} tag(s) but {endfor_count} {{% endfor %}} tag(s)\n"
            f"  Fix: Each {{% for %}} must have a corresponding {{% endfor %}}"
        )

    if_count = len(re.findall(r"\{%\s*if\s+", full_text))
    endif_count = len(re.findall(r"\{%\s*endif\s*%\}", full_text))
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

    try:
        env.parse(full_text)
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
    for match in re.finditer(r"\{%\s*for\s+(\w+)\s+in\s+([\w.]+)\s*%\}", text):
        loop_item = match.group(1)
        loop_var = match.group(2)
        tokens.append({"type": "for", "loop_item": loop_item, "loop_var": loop_var, "pos": match.start()})

    # Find all endfor
    for match in re.finditer(r"\{%\s*endfor\s*%\}", text):
        tokens.append({"type": "endfor", "pos": match.start()})

    # Find all variables
    # Include hyphens in variable names to detect them (even though Jinja2 interprets hyphens as subtraction)
    for match in re.finditer(r"\{\{\s*([\w.\-]+)(?:\s*\|[^}]*)?\s*\}\}", text):
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
