"""Unit tests for CC-SG-WIDEN-001 (Security Group Ingress Widened to Public)."""

import pytest
from backend.app.engine.rules.sg_widen import SgWidenRule
from backend.app.models.change import ActionType, CanonicalChange
from backend.app.models.impact import ImpactCategory, Severity


@pytest.fixture
def rule():
    return SgWidenRule()


def test_sg_widen_ipv4_newly_added_positive(rule):
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
    assert rule.trigger(change) is True
    finding, pred = rule.evaluate(change)

    assert finding.rule_id == "CC-SG-WIDEN-001"
    assert finding.category == ImpactCategory.SECURITY
    assert finding.severity == Severity.HIGH
    assert "0.0.0.0/0" in finding.explanation
    assert "TCP port 80" in finding.explanation

    assert pred.metric == "ingress_cidr_blocks"
    assert pred.direction == "OPEN"
    assert pred.verification_approach == "SET_CONTAINS"
    assert pred.expected_value == [
        {"protocol": "tcp", "from_port": 80, "to_port": 80, "cidr": "0.0.0.0/0"}
    ]
    assert pred.evidence_requirement is not None
    assert pred.evidence_requirement.resource_type == "security_group"
    assert pred.evidence_requirement.field == "ip_permissions"


def test_sg_widen_ipv6_exposure_preserves_actual_cidr(rule):
    """Guardrail: Preserve actual CIDR for IPv6 (::/0) findings without hardcoding IPv4."""
    change = CanonicalChange(
        resource_address="aws_security_group.web",
        resource_type="aws_security_group",
        action=ActionType.UPDATE,
        before={"ingress": []},
        after={
            "ingress": [
                {
                    "protocol": "tcp",
                    "from_port": 443,
                    "to_port": 443,
                    "ipv6_cidr_blocks": ["::/0"],
                }
            ]
        },
    )
    assert rule.trigger(change) is True
    finding, pred = rule.evaluate(change)

    assert "::/0" in finding.explanation
    assert pred.expected_value[0]["cidr"] == "::/0"
    assert pred.expected_value[0]["cidr"] != "0.0.0.0/0"


def test_sg_widen_protocol_all_and_null_ports(rule):
    """Guardrail: Protocol -1 with null/missing port fields should normalize cleanly."""
    change = CanonicalChange(
        resource_address="aws_security_group.all",
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

    assert "ALL traffic from 0.0.0.0/0" in finding.explanation
    assert pred.expected_value == [
        {"protocol": "-1", "from_port": 0, "to_port": 0, "cidr": "0.0.0.0/0"}
    ]


def test_sg_widen_port_range(rule):
    change = CanonicalChange(
        resource_address="aws_security_group.range",
        resource_type="aws_security_group",
        action=ActionType.UPDATE,
        before={"ingress": []},
        after={
            "ingress": [
                {
                    "protocol": "tcp",
                    "from_port": 8000,
                    "to_port": 8080,
                    "cidr_blocks": ["0.0.0.0/0"],
                }
            ]
        },
    )
    assert rule.trigger(change) is True
    finding, pred = rule.evaluate(change)
    assert "TCP ports 8000-8080 from 0.0.0.0/0" in finding.explanation
    assert pred.expected_value[0]["from_port"] == 8000
    assert pred.expected_value[0]["to_port"] == 8080


def test_sg_widen_preexisting_public_ingress_regression_negative(rule):
    """Regression test: Pre-existing public access must NOT trigger if only unrelated attributes change."""
    change = CanonicalChange(
        resource_address="aws_security_group.web",
        resource_type="aws_security_group",
        action=ActionType.UPDATE,
        before={
            "description": "Old description",
            "ingress": [
                {
                    "protocol": "tcp",
                    "from_port": 80,
                    "to_port": 80,
                    "cidr_blocks": ["0.0.0.0/0"],
                }
            ],
        },
        after={
            "description": "New description",
            "ingress": [
                {
                    "protocol": "tcp",
                    "from_port": 80,
                    "to_port": 80,
                    "cidr_blocks": ["0.0.0.0/0"],
                }
            ],
        },
    )
    # The rule already existed in before; it was not newly introduced or widened
    assert rule.trigger(change) is False


def test_sg_widen_private_cidr_negative(rule):
    """Widening to an internal CIDR should not trigger public widen rule."""
    change = CanonicalChange(
        resource_address="aws_security_group.internal",
        resource_type="aws_security_group",
        action=ActionType.UPDATE,
        before={"ingress": []},
        after={
            "ingress": [
                {
                    "protocol": "tcp",
                    "from_port": 80,
                    "to_port": 80,
                    "cidr_blocks": ["10.0.0.0/8"],
                }
            ]
        },
    )
    assert rule.trigger(change) is False


def test_sg_widen_deduplicates_equivalent_ingress(rule):
    """Equivalent duplicate ingress definitions in after state should not create duplicate prediction entries."""
    change = CanonicalChange(
        resource_address="aws_security_group.web",
        resource_type="aws_security_group",
        action=ActionType.UPDATE,
        before={"ingress": []},
        after={
            "ingress": [
                {"protocol": "tcp", "from_port": 80, "to_port": 80, "cidr_blocks": ["0.0.0.0/0"]},
                {"protocol": "tcp", "from_port": 80, "to_port": 80, "cidr_blocks": ["0.0.0.0/0"]},
            ]
        },
    )
    assert rule.trigger(change) is True
    _, pred = rule.evaluate(change)
    assert len(pred.expected_value) == 1
