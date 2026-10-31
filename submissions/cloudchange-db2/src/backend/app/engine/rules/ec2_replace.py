"""CC-EC2-REPLACE-001: EC2 Forced Resource Replacement Rule."""

from backend.app.engine.rules.base import BaseRule
from backend.app.models.change import ActionType, CanonicalChange
from backend.app.models.evidence import EvidenceRequirement
from backend.app.models.impact import ImpactCategory, ImpactFinding, Severity
from backend.app.models.prediction import Prediction, VerificationApproach


class Ec2ReplaceRule(BaseRule):
    """Detects planned replacement (destroy and recreate) of an EC2 instance."""

    rule_id = "CC-EC2-REPLACE-001"
    rule_version = "1.0.0"
    name = "EC2 Forced Resource Replacement"
    resource_types = {"aws_instance"}
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
            title="EC2 resource will be replaced",
            explanation=(
                "The planned change forces destruction and recreation of the EC2 instance, "
                "causing physical resource ID replacement and transient downtime."
            ),
        )

    def generate_evidence_requirement(self, change: CanonicalChange) -> EvidenceRequirement:
        return EvidenceRequirement(
            provider="aws",
            service="ec2",
            resource_type="instance",
            field="instance_id",
        )

    def generate_prediction(self, change: CanonicalChange) -> Prediction:
        pred_id = f"pred-{self.rule_id.lower()}-{change.resource_address.replace('.', '-')}"
        prior_id = (change.before or {}).get("id")

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
                "Verification requires comparing the pre-apply physical instance ID with the "
                "post-apply physical instance ID. A running state alone does not confirm replacement. "
                "If prior identity is missing or unresolved, verification cannot proceed and must return NOT_OBSERVABLE."
            ),
            evidence_requirement=self.generate_evidence_requirement(change),
        )
