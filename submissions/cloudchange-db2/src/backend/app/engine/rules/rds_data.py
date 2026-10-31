"""CC-RDS-DATA-001: RDS Data Persistence and Lifecycle Risk Rule."""

from backend.app.engine.rules.base import BaseRule
from backend.app.models.change import ActionType, CanonicalChange
from backend.app.models.evidence import EvidenceRequirement
from backend.app.models.impact import ImpactCategory, ImpactFinding, Severity
from backend.app.models.prediction import Prediction, VerificationApproach

STORAGE_PERSISTENCE_ATTRIBUTES = {
    "allocated_storage",
    "storage_type",
    "kms_key_id",
    "storage_encrypted",
    "snapshot_identifier",
    "skip_final_snapshot",
    "final_snapshot_identifier",
}


class RdsDataRule(BaseRule):
    """Detects RDS lifecycle or persistence changes (instance deletion or replacement with storage alterations)."""

    rule_id = "CC-RDS-DATA-001"
    rule_version = "1.0.0"
    name = "RDS Data Persistence and Lifecycle Risk"
    resource_types = {"aws_db_instance"}
    category = ImpactCategory.DATA
    severity = Severity.HIGH

    def _get_changed_storage_attrs(self, change: CanonicalChange) -> list[str]:
        before_attrs = change.before or {}
        after_attrs = change.after or {}
        changed = []
        for attr in sorted(STORAGE_PERSISTENCE_ATTRIBUTES):
            if attr in before_attrs or attr in after_attrs:
                if before_attrs.get(attr) != after_attrs.get(attr):
                    changed.append(attr)
        return changed

    def trigger(self, change: CanonicalChange) -> bool:
        if not self.applies_to(change.resource_type):
            return False

        # Branch 1: Resource Deletion (where after is None)
        if change.action == ActionType.DELETE:
            return True

        # Branch 2: Resource Replacement WITH storage/persistence configuration modifications
        is_replacement = change.requires_replacement or change.action == ActionType.REPLACE
        if is_replacement:
            changed_storage = self._get_changed_storage_attrs(change)
            return len(changed_storage) > 0

        return False

    def generate_finding(self, change: CanonicalChange) -> ImpactFinding:
        return ImpactFinding(
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            resource_address=change.resource_address,
            category=self.category,
            severity=self.severity,
            title="RDS data lifecycle or persistence characteristics affected",
            explanation="This change may affect lifecycle or persistence characteristics.",
        )

    def generate_evidence_requirement(self, change: CanonicalChange) -> EvidenceRequirement:
        if change.action == ActionType.DELETE:
            return EvidenceRequirement(
                provider="aws",
                service="rds",
                resource_type="db_instance",
                field="DBInstanceNotFound",
            )

        return EvidenceRequirement(
            provider="aws",
            service="rds",
            resource_type="db_instance",
            field="StorageConfig",
        )

    def generate_prediction(self, change: CanonicalChange) -> Prediction:
        pred_id = f"pred-{self.rule_id.lower()}-{change.resource_address.replace('.', '-')}"

        if change.action == ActionType.DELETE:
            return Prediction(
                prediction_id=pred_id,
                resource_address=change.resource_address,
                metric="instance_deletion",
                expected_value="DELETED",
                direction="DELETED",
                verification_approach=VerificationApproach.RESOURCE_DELETED,
                rationale=(
                    "RDS instance is scheduled for deletion; verifier must confirm "
                    "DBInstanceNotFound rather than treating API errors as absence."
                ),
                evidence_requirement=self.generate_evidence_requirement(change),
            )

        changed_attrs = self._get_changed_storage_attrs(change)
        after_attrs = change.after or {}
        expected = {attr: after_attrs.get(attr) for attr in changed_attrs}

        return Prediction(
            prediction_id=pred_id,
            resource_address=change.resource_address,
            metric="storage_and_encryption_config",
            expected_value=expected,
            direction="MODIFIED",
            verification_approach=VerificationApproach.CONFIG_MATCH,
            rationale=(
                "RDS replacement alters storage or persistence configuration; verifier must confirm "
                "post-apply storage characteristics without claiming premature data loss."
            ),
            evidence_requirement=self.generate_evidence_requirement(change),
        )
