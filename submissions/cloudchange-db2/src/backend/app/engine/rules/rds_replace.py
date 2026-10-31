"""CC-RDS-REPLACE-001: RDS DB Instance Replacement Rule."""

from backend.app.engine.rules.base import BaseRule
from backend.app.models.change import ActionType, CanonicalChange
from backend.app.models.evidence import EvidenceRequirement
from backend.app.models.impact import ImpactCategory, ImpactFinding, Severity
from backend.app.models.prediction import Prediction, VerificationApproach


class RdsReplaceRule(BaseRule):
    """Detects planned replacement (destroy and recreate) of an RDS DB instance."""

    rule_id = "CC-RDS-REPLACE-001"
    rule_version = "1.0.0"
    name = "RDS DB Instance Replacement"
    resource_types = {"aws_db_instance"}
    category = ImpactCategory.AVAILABILITY
    severity = Severity.HIGH

    def trigger(self, change: CanonicalChange) -> bool:
        if not self.applies_to(change.resource_type):
            return False

        return bool(change.requires_replacement or change.action == ActionType.REPLACE)

    def generate_finding(self, change: CanonicalChange) -> ImpactFinding:
        return ImpactFinding(
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            resource_address=change.resource_address,
            category=self.category,
            severity=self.severity,
            title="RDS DB instance will be replaced",
            explanation=(
                "The planned change forces destruction and recreation of the RDS DB instance, "
                "causing physical resource ID replacement and database downtime."
            ),
        )

    def generate_evidence_requirement(self, change: CanonicalChange) -> EvidenceRequirement:
        return EvidenceRequirement(
            provider="aws",
            service="rds",
            resource_type="db_instance",
            field="dbi_resource_id",
        )

    def generate_prediction(self, change: CanonicalChange) -> Prediction:
        pred_id = f"pred-{self.rule_id.lower()}-{change.resource_address.replace('.', '-')}"
        prior_id = (
            (change.before or {}).get("id")
            or (change.before or {}).get("dbi_resource_id")
            or (change.before or {}).get("identifier")
        )

        return Prediction(
            prediction_id=pred_id,
            resource_address=change.resource_address,
            metric="resource_identity",
            expected_value={
                "transition": "REPLACED",
                "prior_physical_id": prior_id,  # Explicitly None (unresolved) if prior state lacks an ID
            },
            direction="REPLACED",
            verification_approach=VerificationApproach.IDENTITY_REPLACED,
            rationale=(
                "Verification requires comparing the pre-apply physical RDS resource ID "
                "(dbi_resource_id) with the post-apply physical resource ID. "
                "An available state alone does not prove replacement. "
                "If prior identity is missing or unresolved, verification must return NOT_OBSERVABLE."
            ),
            evidence_requirement=self.generate_evidence_requirement(change),
        )
