"""CC-SG-SENSITIVE-PORT-001: Sensitive Administrative Port Exposed to Public Rule."""

from backend.app.engine.rules.base import BaseRule
from backend.app.engine.rules.helpers import SENSITIVE_PORTS, SemanticIngressRule, extract_new_public_ingress_rules
from backend.app.models.change import CanonicalChange
from backend.app.models.evidence import EvidenceRequirement
from backend.app.models.impact import ImpactCategory, ImpactFinding, Severity
from backend.app.models.prediction import Prediction, VerificationApproach


class SgSensitivePortRule(BaseRule):
    """Detects newly introduced public exposure (0.0.0.0/0 or ::/0) of sensitive administrative ports (22, 3389)."""

    rule_id = "CC-SG-SENSITIVE-PORT-001"
    rule_version = "1.0.0"
    name = "Sensitive Administrative Port Exposed to Public"
    resource_types = {"aws_security_group"}
    category = ImpactCategory.SECURITY
    severity = Severity.HIGH

    def _get_sensitive_rules(self, change: CanonicalChange) -> list[SemanticIngressRule]:
        new_rules = extract_new_public_ingress_rules(change.before, change.after)
        return [
            r for r in new_rules
            if any(r.encompasses_port(p) for p in sorted(SENSITIVE_PORTS))
        ]

    def trigger(self, change: CanonicalChange) -> bool:
        if not self.applies_to(change.resource_type):
            return False

        return len(self._get_sensitive_rules(change)) > 0

    def generate_finding(self, change: CanonicalChange) -> ImpactFinding:
        sensitive_rules = self._get_sensitive_rules(change)
        exposures = []
        for r in sensitive_rules:
            for p in sorted(SENSITIVE_PORTS):
                if r.encompasses_port(p):
                    label = "SSH" if p == 22 else "RDP"
                    exposures.append(f"port {p} ({label}) via {r.protocol.upper()} from {r.cidr}")

        explanation = (
            f"Public ingress allows unrestricted access to sensitive administrative ports: "
            f"{'; '.join(exposures)}."
        )

        return ImpactFinding(
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            resource_address=change.resource_address,
            category=self.category,
            severity=self.severity,
            title="Sensitive administrative port exposed to public internet",
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
        sensitive_rules = self._get_sensitive_rules(change)
        expected = []
        for r in sensitive_rules:
            for p in sorted(SENSITIVE_PORTS):
                if r.encompasses_port(p):
                    expected.append({
                        "port": p,
                        "protocol": r.protocol,
                        "cidr": r.cidr,
                    })

        pred_id = f"pred-{self.rule_id.lower()}-{change.resource_address.replace('.', '-')}"
        return Prediction(
            prediction_id=pred_id,
            resource_address=change.resource_address,
            metric="sensitive_port_exposure",
            expected_value=expected,
            direction="OPEN",
            verification_approach=VerificationApproach.SET_CONTAINS,
            rationale=(
                "Verification requires confirming in AWS whether ingress rules permit "
                "unrestricted public access to administrative ports 22/3389."
            ),
            evidence_requirement=self.generate_evidence_requirement(change),
        )
