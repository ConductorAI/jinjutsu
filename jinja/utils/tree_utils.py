from ..variable_tree import VariableNode


def refine_list_formats(tree: dict[str, VariableNode]) -> None:
    """Derive item_format for every list in the tree, now that its item's fields are known."""
    for var_info in tree.values():
        if var_info.get("type") == "list":
            if "properties" in var_info and var_info["properties"]:
                var_info["item_format"] = "object"
                refine_list_formats(var_info["properties"])
            else:
                var_info["item_format"] = "string"
                var_info.pop("properties", None)
        elif var_info.get("type") == "object":
            refine_list_formats(var_info.get("properties", {}))


def lookup_path(tree: dict[str, VariableNode], root: str, attrs: list[str]) -> VariableNode | None:
    node = tree.get(root)
    for segment in attrs:
        if not node:
            return None
        node = node.get("properties", {}).get(segment)
    return node
