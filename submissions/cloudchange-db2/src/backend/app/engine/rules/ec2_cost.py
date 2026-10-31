"""CC-EC2-COST-001: EC2 Instance Type Scaling Rule."""

from backend.app.engine.rules.base import BaseRule
from backend.app.engine.rules.helpers import compare_ec2_instance_types
from backend.app.models.change import CanonicalChange
from backend.app.models.evidence import EvidenceRequirement
from backend.app.models.impact import ImpactCategory, ImpactFinding, Severity
from backend.app.models.prediction import Prediction, VerificationApproach


class Ec2CostRule(BaseRule):
    """Detects changes to EC2 instance type and determines conservative sizing direction."""

    rule_id = "CC-EC2-COST-001"
    rule_version = "1.0.0"
    name = "EC2 Instance Type Scaling"
    resource_types = {"aws_instance"}
    category = ImpactCategory.COST
    severity = Severity.MEDIUM

    def trigger(self, change: CanonicalChange) -> bool:
        if not self.applies_to(change.resource_type):
            return False

        before_attrs = change.before or {}
        after_attrs = change.after or {}

        before_type = before_attrs.get("instance_type")
        after_type = after_attrs.get("instance_type")

        return bool(before_type and after_type and before_type != after_type)

    def generate_finding(self, change: CanonicalChange) -> ImpactFinding:
        before_attrs = change.before or {}
        after_attrs = change.after or {}
        before_type = before_attrs.get("instance_type", "unknown")
        after_type = after_attrs.get("instance_type", "unknown")

        direction = compare_ec2_instance_types(before_type, after_type)
        if direction == "SCALE_UP":
            explanation = f"EC2 instance type scaled up from {before_type} to {after_type}."
        elif direction == "SCALE_DOWN":
            explanation = f"EC2 instance type scaled down from {before_type} to {after_type}."
        else:
            explanation = f"EC2 instance type modified from {before_type} to {after_type}."

        return ImpactFinding(
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            resource_address=change.resource_address,
            category=self.category,
            severity=self.severity,
            title="EC2 instance type changed",
            explanation=explanation,
        )

    def generate_evidence_requirement(self, change: CanonicalChange) -> EvidenceRequirement:
        return EvidenceRequirement(
            provider="aws",
            service="ec2",
            resource_type="instance",
            field="instance_type",
        )

    def generate_prediction(self, change: CanonicalChange) -> Prediction:
        before_attrs = change.before or {}
        after_attrs = change.after or {}
        before_type = before_attrs.get("instance_type", "unknown")
        after_type = after_attrs.get("instance_type", "unknown")
        direction = compare_ec2_instance_types(before_type, after_type)

        pred_id = f"pred-{self.rule_id.lower()}-{change.resource_address.replace('.', '-')}"
        return Prediction(
            prediction_id=pred_id,
            resource_address=change.resource_address,
            metric="instance_type",
            expected_value=after_type,
            direction=direction,
            verification_approach=VerificationApproach.EXACT_MATCH,
            rationale=f"Instance type for {change.resource_address} is expected to be observed as {after_type} in AWS.",
            evidence_requirement=self.generate_evidence_requirement(change),
        )
