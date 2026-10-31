"""CC-SG-WIDEN-001: Security Group Ingress Widened to Public Rule."""

from backend.app.engine.rules.base import BaseRule
from backend.app.engine.rules.helpers import SemanticIngressRule, extract_new_public_ingress_rules
from backend.app.models.change import CanonicalChange
from backend.app.models.evidence import EvidenceRequirement
from backend.app.models.impact import ImpactCategory, ImpactFinding, Severity
from backend.app.models.prediction import Prediction, VerificationApproach


class SgWidenRule(BaseRule):
    """Detects newly introduced or widened ingress permissions granting public access (0.0.0.0/0 or ::/0)."""

    rule_id = "CC-SG-WIDEN-001"
    rule_version = "1.0.0"
    name = "Security Group Ingress Widened to Public"
    resource_types = {"aws_security_group"}
    category = ImpactCategory.SECURITY
    severity = Severity.HIGH

    def _format_rule(self, rule: SemanticIngressRule) -> str:
        if rule.protocol == "-1":
            return f"ALL traffic from {rule.cidr}"
        if rule.from_port == rule.to_port:
            return f"{rule.protocol.upper()} port {rule.from_port} from {rule.cidr}"
        return f"{rule.protocol.upper()} ports {rule.from_port}-{rule.to_port} from {rule.cidr}"

    def trigger(self, change: CanonicalChange) -> bool:
        if not self.applies_to(change.resource_type):
            return False

        new_rules = extract_new_public_ingress_rules(change.before, change.after)
        return len(new_rules) > 0

    def generate_finding(self, change: CanonicalChange) -> ImpactFinding:
        new_rules = extract_new_public_ingress_rules(change.before, change.after)
        formatted_rules = [self._format_rule(r) for r in new_rules]
        explanation = (
            f"Newly introduced public ingress allows unrestricted access: {'; '.join(formatted_rules)}."
        )

        return ImpactFinding(
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            resource_address=change.resource_address,
            category=self.category,
            severity=self.severity,
            title="Security group ingress widened to public access",
            explanation=explanation,
        )

    def generate_evidence_requirement(self, change: CanonicalChange) -> EvidenceRequirement:
        return EvidenceRequirement(
            provider="aws",
            service="ec2",
            resource_type="security_group",
            field="ip_permissions",
        )

    def generate_prediction(self, change: CanonicalChange) -> Prediction:
        new_rules = extract_new_public_ingress_rules(change.before, change.after)
        expected = [
            {
                "protocol": r.protocol,
                "from_port": r.from_port,
                "to_port": r.to_port,
                "cidr": r.cidr,
            }
            for r in new_rules
        ]

        pred_id = f"pred-{self.rule_id.lower()}-{change.resource_address.replace('.', '-')}"
        return Prediction(
            prediction_id=pred_id,
            resource_address=change.resource_address,
            metric="ingress_cidr_blocks",
            expected_value=expected,
            direction="OPEN",
            verification_approach=VerificationApproach.SET_CONTAINS,
            rationale=(
                "Verification requires confirming that AWS security group permissions "
                "contain the specified newly opened public ingress CIDRs."
            ),
            evidence_requirement=self.generate_evidence_requirement(change),
        )
