"""CC-EC2-CONFIG-001: Meaningful EC2 Operational Configuration Change Rule."""

from backend.app.engine.rules.base import BaseRule
from backend.app.models.change import ActionType, CanonicalChange
from backend.app.models.evidence import EvidenceRequirement
from backend.app.models.impact import ImpactCategory, ImpactFinding, Severity
from backend.app.models.prediction import Prediction, VerificationApproach

OPERATIONAL_ATTRIBUTES = {
    "ebs_optimized",
    "monitoring",
    "source_dest_check",
    "credit_specification",
    "tenancy",
    "disable_api_termination",
}


class Ec2ConfigRule(BaseRule):
    """Detects meaningful EC2 operational configuration changes that do not trigger replacement."""

    rule_id = "CC-EC2-CONFIG-001"
    rule_version = "1.0.0"
    name = "Meaningful EC2 Operational Configuration Change"
    resource_types = {"aws_instance"}
    category = ImpactCategory.PERFORMANCE
    severity = Severity.LOW

    def _get_changed_attrs(self, change: CanonicalChange) -> list[str]:
        before_attrs = change.before or {}
        after_attrs = change.after or {}
        changed = []
        for attr in sorted(OPERATIONAL_ATTRIBUTES):
            if attr in before_attrs or attr in after_attrs:
                if before_attrs.get(attr) != after_attrs.get(attr):
                    changed.append(attr)
        return changed

    def trigger(self, change: CanonicalChange) -> bool:
        if not self.applies_to(change.resource_type):
            return False

        # Must not be a replacement
        if change.requires_replacement or change.action == ActionType.REPLACE:
            return False

        # Must not be deletion
        if change.action == ActionType.DELETE:
            return False

        return len(self._get_changed_attrs(change)) > 0

    def generate_finding(self, change: CanonicalChange) -> ImpactFinding:
        changed_attrs = self._get_changed_attrs(change)
        attrs_str = ", ".join(changed_attrs)
        return ImpactFinding(
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            resource_address=change.resource_address,
            category=self.category,
            severity=self.severity,
            title="EC2 operational configuration modified",
            explanation=f"EC2 operational configuration modified without replacement: {attrs_str}.",
        )

    def generate_evidence_requirement(self, change: CanonicalChange) -> EvidenceRequirement:
        return EvidenceRequirement(
            provider="aws",
            service="ec2",
            resource_type="instance",
            field="operational_config",
        )

    def generate_prediction(self, change: CanonicalChange) -> Prediction:
        changed_attrs = self._get_changed_attrs(change)
        after_attrs = change.after or {}
        expected = {attr: after_attrs.get(attr) for attr in changed_attrs}

        pred_id = f"pred-{self.rule_id.lower()}-{change.resource_address.replace('.', '-')}"
        return Prediction(
            prediction_id=pred_id,
            resource_address=change.resource_address,
            metric="operational_config",
            expected_value=expected,
            direction="MODIFIED",
            verification_approach=VerificationApproach.CONFIG_MATCH,
            rationale=(
                f"Observed EC2 configuration attributes in AWS must match post-apply configuration for: "
                f"{', '.join(changed_attrs)}."
            ),
            evidence_requirement=self.generate_evidence_requirement(change),
        )
