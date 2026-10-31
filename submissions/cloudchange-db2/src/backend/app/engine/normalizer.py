"""Change Normalizer.

Transforms raw Terraform action arrays and diff structures into internal
CanonicalChange domain models.
"""

from typing import Any
from backend.app.engine.diff import compute_attribute_diffs
from backend.app.engine.exceptions import InvalidActionError
from backend.app.engine.parser import PlanParser
from backend.app.models.change import (
    ActionType,
    CanonicalChange,
    PlanNormalizationResult,
)


class ChangeNormalizer:
    """Normalizes Terraform raw plan changes to domain CanonicalChange instances."""

    @staticmethod
    def normalize_action(actions: list[str], resource_address: str = "") -> ActionType:
        """Map raw Terraform action arrays to a deterministic ActionType enum.
        
        Supported mappings:
            ["create"] -> ActionType.CREATE
            ["update"] -> ActionType.UPDATE
            ["delete"] -> ActionType.DELETE
            ["delete", "create"] -> ActionType.REPLACE
            ["create", "delete"] -> ActionType.REPLACE
            
        Raises:
            InvalidActionError: For unsupported, empty, or unmappable action lists (e.g. no-op, read).
        """
        if not actions or not isinstance(actions, list):
            raise InvalidActionError(actions=actions or [], resource_address=resource_address)

        # Exact match or set equality for replacement orders
        action_tuple = tuple(actions)
        action_set = set(actions)

        if action_tuple == ("create",):
            return ActionType.CREATE
        elif action_tuple == ("update",):
            return ActionType.UPDATE
        elif action_tuple == ("delete",):
            return ActionType.DELETE
        elif action_set == {"delete", "create"} and len(actions) == 2:
            return ActionType.REPLACE
        else:
            raise InvalidActionError(actions=actions, resource_address=resource_address)

    def normalize_resource_change(self, raw_change: dict[str, Any]) -> CanonicalChange:
        """Transform a raw resource change item into a CanonicalChange."""
        address = raw_change.get("address", "")
        resource_type = raw_change.get("type", "")
        change_info = raw_change.get("change", {})

        raw_actions = change_info.get("actions", [])
        action = self.normalize_action(raw_actions, resource_address=address)

        raw_before = change_info.get("before")
        raw_after = change_info.get("after")

        before = raw_before if isinstance(raw_before, dict) else None
        after = raw_after if isinstance(raw_after, dict) else None

        # Determine replacement triggers
        replace_paths = change_info.get("replace_paths")
        action_reason = change_info.get("action_reason")
        requires_replacement = (
            action == ActionType.REPLACE or
            bool(replace_paths) or
            action_reason == "replace_because_cannot_update"
        )

        # Compute structured attribute-level diffs
        diffs = compute_attribute_diffs(before, after)

        return CanonicalChange(
            resource_address=address,
            resource_type=resource_type,
            action=action,
            before=before,
            after=after,
            requires_replacement=requires_replacement,
            diffs=diffs,
        )

    def normalize(self, raw_changes: list[dict[str, Any]]) -> list[CanonicalChange]:
        """Normalize a list of raw resource changes into CanonicalChange objects."""
        return [self.normalize_resource_change(item) for item in raw_changes]


def parse_and_normalize(
    plan_json: Any,
    strict_supported_only: bool = False,
    strict: bool | None = None,
) -> PlanNormalizationResult:
    """Complete Phase B pipeline: plan.json -> validation -> parsing -> normalization -> PlanNormalizationResult.
    
    Args:
        plan_json: Machine-readable plan JSON artifact.
        strict_supported_only: When True, raises UnsupportedResourceError if any
            unsupported resource type is encountered. When False (default), unsupported
            resources are preserved as structured warnings, allowing actionable changes
            to supported resources to be analyzed.
        
    Returns:
        PlanNormalizationResult containing actionable CanonicalChange objects,
        unsupported resource warnings, and ignored no-op/read entries.
    """
    if strict is not None:
        strict_supported_only = strict

    parser = PlanParser()
    normalizer = ChangeNormalizer()

    parsed_plan = parser.parse(plan_json, strict_supported_only=strict_supported_only)
    actionable_changes = normalizer.normalize(parsed_plan.actionable_changes)

    return PlanNormalizationResult(
        changes=actionable_changes,
        unsupported_resources=parsed_plan.unsupported_resources,
        ignored_noops=parsed_plan.ignored_noops,
        ignored_reads=parsed_plan.ignored_reads,
    )
