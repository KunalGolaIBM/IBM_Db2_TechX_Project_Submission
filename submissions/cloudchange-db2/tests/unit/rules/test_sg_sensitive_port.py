"""Unit tests for CC-SG-SENSITIVE-PORT-001 (Sensitive Administrative Port Exposed to Public)."""

import pytest
from backend.app.engine.rules.sg_sensitive_port import SgSensitivePortRule
from backend.app.models.change import ActionType, CanonicalChange
from backend.app.models.impact import ImpactCategory, Severity


@pytest.fixture
def rule():
    return SgSensitivePortRule()


def test_sg_sensitive_port_22_ssh_positive(rule):
    change = CanonicalChange(
        resource_address="aws_security_group.ssh_open",
        resource_type="aws_security_group",
        action=ActionType.UPDATE,
        before={"ingress": []},
        after={
            "ingress": [
                {
                    "protocol": "tcp",
                    "from_port": 22,
                    "to_port": 22,
                    "cidr_blocks": ["0.0.0.0/0"],
                }
            ]
        },
    )
    assert rule.trigger(change) is True
    finding, pred = rule.evaluate(change)

    assert finding.rule_id == "CC-SG-SENSITIVE-PORT-001"
    assert finding.category == ImpactCategory.SECURITY
    assert finding.severity == Severity.HIGH
    assert "port 22 (SSH)" in finding.explanation
    assert "0.0.0.0/0" in finding.explanation

    assert pred.metric == "sensitive_port_exposure"
    assert pred.direction == "OPEN"
    assert pred.verification_approach == "SET_CONTAINS"
    assert pred.expected_value == [{"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0"}]
    assert pred.evidence_requirement is not None
    assert pred.evidence_requirement.resource_type == "security_group"
    assert pred.evidence_requirement.field == "ip_permissions"


def test_sg_sensitive_port_3389_rdp_ipv6_positive(rule):
    """Positive test for RDP over IPv6 preserving ::/0 CIDR."""
    change = CanonicalChange(
        resource_address="aws_security_group.windows_rdp",
        resource_type="aws_security_group",
        action=ActionType.UPDATE,
        before={"ingress": []},
        after={
            "ingress": [
                {
                    "protocol": "tcp",
                    "from_port": 3389,
                    "to_port": 3389,
                    "ipv6_cidr_blocks": ["::/0"],
                }
            ]
        },
    )
    assert rule.trigger(change) is True
    finding, pred = rule.evaluate(change)

    assert "port 3389 (RDP)" in finding.explanation
    assert "::/0" in finding.explanation
    assert pred.expected_value == [{"port": 3389, "protocol": "tcp", "cidr": "::/0"}]


def test_sg_sensitive_port_protocol_all_encompasses_both_ports(rule):
    """Protocol -1 encompasses all ports including sensitive ports 22 and 3389."""
    change = CanonicalChange(
        resource_address="aws_security_group.open_all",
        resource_type="aws_security_group",
        action=ActionType.UPDATE,
        before={"ingress": []},
        after={
            "ingress": [
                {
                    "protocol": "-1",
                    "from_port": None,
                    "to_port": None,
                    "cidr_blocks": ["0.0.0.0/0"],
                }
            ]
        },
    )
    assert rule.trigger(change) is True
    finding, pred = rule.evaluate(change)

    assert "port 22" in finding.explanation
    assert "port 3389" in finding.explanation
    ports_in_pred = [e["port"] for e in pred.expected_value]
    assert 22 in ports_in_pred
    assert 3389 in ports_in_pred


def test_sg_sensitive_port_range_encompassing_22(rule):
    change = CanonicalChange(
        resource_address="aws_security_group.range",
        resource_type="aws_security_group",
        action=ActionType.UPDATE,
        before={"ingress": []},
        after={
            "ingress": [
                {
                    "protocol": "tcp",
                    "from_port": 20,
                    "to_port": 25,
                    "cidr_blocks": ["0.0.0.0/0"],
                }
            ]
        },
    )
    assert rule.trigger(change) is True
    _, pred = rule.evaluate(change)
    assert any(e["port"] == 22 for e in pred.expected_value)


def test_sg_sensitive_port_preexisting_public_regression_negative(rule):
    """Regression test: Pre-existing public SSH must not re-trigger if unchanged."""
    change = CanonicalChange(
        resource_address="aws_security_group.existing_ssh",
        resource_type="aws_security_group",
        action=ActionType.UPDATE,
        before={
            "description": "Old description",
            "ingress": [
                {
                    "protocol": "tcp",
                    "from_port": 22,
                    "to_port": 22,
                    "cidr_blocks": ["0.0.0.0/0"],
                }
            ],
        },
        after={
            "description": "Updated description",
            "ingress": [
                {
                    "protocol": "tcp",
                    "from_port": 22,
                    "to_port": 22,
                    "cidr_blocks": ["0.0.0.0/0"],
                }
            ],
        },
    )
    assert rule.trigger(change) is False


def test_sg_sensitive_port_non_sensitive_port_negative(rule):
    """Port 80/443 exposure is NOT an administrative port exposure."""
    change = CanonicalChange(
        resource_address="aws_security_group.web",
        resource_type="aws_security_group",
        action=ActionType.UPDATE,
        before={"ingress": []},
        after={
            "ingress": [
                {
                    "protocol": "tcp",
                    "from_port": 80,
                    "to_port": 80,
                    "cidr_blocks": ["0.0.0.0/0"],
                }
            ]
        },
    )
    assert rule.trigger(change) is False


def test_sg_sensitive_port_private_cidr_negative(rule):
    """SSH to private 10.0.0.0/8 should not trigger public sensitive port rule."""
    change = CanonicalChange(
        resource_address="aws_security_group.internal_ssh",
        resource_type="aws_security_group",
        action=ActionType.UPDATE,
        before={"ingress": []},
        after={
            "ingress": [
                {
                    "protocol": "tcp",
                    "from_port": 22,
                    "to_port": 22,
                    "cidr_blocks": ["10.0.0.0/8"],
                }
            ]
        },
    )
    assert rule.trigger(change) is False
