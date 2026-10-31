"""Attribute Difference Engine.

Computes structured attribute differences between before and after resource states.
Supports nested paths such as 'instance_type' and 'ingress[0].cidr_blocks'.
"""

from typing import Any, Optional
from backend.app.models.change import AttributeDiff


def compute_attribute_diffs(
    before: Optional[dict[str, Any]],
    after: Optional[dict[str, Any]],
    parent_path: str = ""
) -> list[AttributeDiff]:
    """Compute structured attribute differences between before and after states.
    
    Args:
        before: Resource attributes before change (or None on create).
        after: Resource attributes after change (or None on delete).
        parent_path: Prefix path for nested recursion.

    Returns:
        A list of AttributeDiff objects representing changed paths.
    """
    diffs: list[AttributeDiff] = []

    # Case 1: Resource Creation (before is None)
    if before is None and after is not None:
        for key in sorted(after.keys()):
            path = f"{parent_path}.{key}" if parent_path else key
            diffs.append(AttributeDiff(path=path, before=None, after=after[key]))
        return diffs

    # Case 2: Resource Deletion (after is None)
    if before is not None and after is None:
        for key in sorted(before.keys()):
            path = f"{parent_path}.{key}" if parent_path else key
            diffs.append(AttributeDiff(path=path, before=before[key], after=None))
        return diffs

    # Case 3: Both None
    if before is None and after is None:
        return []

    # Case 4: Both are dictionaries (Update / In-Place / Replace)
    all_keys = sorted(set(before.keys()) | set(after.keys()))
    for key in all_keys:
        path = f"{parent_path}.{key}" if parent_path else key

        if key not in before:
            # Attribute added
            diffs.append(AttributeDiff(path=path, before=None, after=after[key]))
        elif key not in after:
            # Attribute removed
            diffs.append(AttributeDiff(path=path, before=before[key], after=None))
        else:
            val_before = before[key]
            val_after = after[key]

            if val_before == val_after:
                continue

            # Nested dict comparison
            if isinstance(val_before, dict) and isinstance(val_after, dict):
                nested_diffs = compute_attribute_diffs(val_before, val_after, parent_path=path)
                diffs.extend(nested_diffs)

            # Nested list comparison
            elif isinstance(val_before, list) and isinstance(val_after, list):
                diffs.extend(_diff_lists(val_before, val_after, path))

            # Primitive or type-mismatched value change
            else:
                diffs.append(AttributeDiff(path=path, before=val_before, after=val_after))

    return diffs


def _diff_lists(list_before: list[Any], list_after: list[Any], path: str) -> list[AttributeDiff]:
    """Helper to compare two lists.
    
    If elements are dictionaries, recurses index by index to form paths like 'ingress[0].cidr_blocks'.
    If elements are primitives, records a list-level diff.
    """
    diffs: list[AttributeDiff] = []

    # Check if elements are dictionaries
    both_dict_lists = (
        all(isinstance(item, dict) for item in list_before) and
        all(isinstance(item, dict) for item in list_after)
    )

    if both_dict_lists and (list_before or list_after):
        max_len = max(len(list_before), len(list_after))
        for idx in range(max_len):
            idx_path = f"{path}[{idx}]"
            if idx >= len(list_before):
                diffs.append(AttributeDiff(path=idx_path, before=None, after=list_after[idx]))
            elif idx >= len(list_after):
                diffs.append(AttributeDiff(path=idx_path, before=list_before[idx], after=None))
            else:
                item_before = list_before[idx]
                item_after = list_after[idx]
                if item_before != item_after:
                    nested = compute_attribute_diffs(item_before, item_after, parent_path=idx_path)
                    diffs.extend(nested)
    else:
        # List of primitives or mixed items
        diffs.append(AttributeDiff(path=path, before=list_before, after=list_after))

    return diffs
