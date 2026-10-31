"""Unit tests for CC-EC2-COST-001 (EC2 Instance Type Scaling)."""

import pytest
from backend.app.engine.rules.ec2_cost import Ec2CostRule
from backend.app.models.change import ActionType, CanonicalChange
from backend.app.models.impact import ImpactCategory, Severity


@pytest.fixture
def rule():
    return Ec2CostRule()


def test_ec2_cost_scale_up_same_family(rule):
    change = CanonicalChange(
        resource_address="aws_instance.web",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        before={"instance_type": "t3.medium"},
        after={"instance_type": "t3.large"},
    )
    assert rule.trigger(change) is True
    finding, pred = rule.evaluate(change)

    assert finding.rule_id == "CC-EC2-COST-001"
    assert finding.category == ImpactCategory.COST
    assert finding.severity == Severity.MEDIUM
    assert "scaled up" in finding.explanation
    assert "t3.medium to t3.large" in finding.explanation

    assert pred.metric == "instance_type"
    assert pred.expected_value == "t3.large"
    assert pred.direction == "SCALE_UP"
    assert pred.verification_approach == "EXACT_MATCH"
    assert pred.evidence_requirement is not None
    assert pred.evidence_requirement.service == "ec2"
    assert pred.evidence_requirement.field == "instance_type"


def test_ec2_cost_scale_down_same_family(rule):
    change = CanonicalChange(
        resource_address="aws_instance.web",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        before={"instance_type": "t3.large"},
        after={"instance_type": "t3.micro"},
    )
    assert rule.trigger(change) is True
    finding, pred = rule.evaluate(change)

    assert finding.rule_id == "CC-EC2-COST-001"
    assert "scaled down" in finding.explanation
    assert pred.direction == "SCALE_DOWN"
    assert pred.expected_value == "t3.micro"
    assert pred.verification_approach == "EXACT_MATCH"


def test_ec2_cost_cross_family_modified(rule):
    """Cross-family sizing should conservatively return MODIFIED, not SCALE_UP or dollar guesses."""
    change = CanonicalChange(
        resource_address="aws_instance.web",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        before={"instance_type": "t3.large"},
        after={"instance_type": "m5.large"},
    )
    assert rule.trigger(change) is True
    finding, pred = rule.evaluate(change)

    assert "modified" in finding.explanation
    assert pred.direction == "MODIFIED"
    assert pred.expected_value == "m5.large"
    assert "$" not in finding.explanation


def test_ec2_cost_unknown_generation_modified(rule):
    """Unknown or uncomparable sizes should fall back to MODIFIED."""
    change = CanonicalChange(
        resource_address="aws_instance.web",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        before={"instance_type": "t3.custom"},
        after={"instance_type": "t3.medium"},
    )
    assert rule.trigger(change) is True
    _, pred = rule.evaluate(change)
    assert pred.direction == "MODIFIED"


def test_ec2_cost_no_change_negative(rule):
    change = CanonicalChange(
        resource_address="aws_instance.web",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        before={"instance_type": "t3.medium"},
        after={"instance_type": "t3.medium"},
    )
    assert rule.trigger(change) is False


def test_ec2_cost_unsupported_resource_negative(rule):
    change = CanonicalChange(
        resource_address="aws_security_group.allow_all",
        resource_type="aws_security_group",
        action=ActionType.UPDATE,
        before={"instance_type": "t3.medium"},
        after={"instance_type": "t3.large"},
    )
    assert rule.trigger(change) is False


def test_ec2_cost_missing_before_after_negative(rule):
    change = CanonicalChange(
        resource_address="aws_instance.web",
        resource_type="aws_instance",
        action=ActionType.CREATE,
        before=None,
        after={"instance_type": "t3.medium"},
    )
    # Creation is not scaling an existing instance
    assert rule.trigger(change) is False
