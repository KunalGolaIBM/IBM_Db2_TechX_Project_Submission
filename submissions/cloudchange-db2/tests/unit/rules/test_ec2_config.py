"""Unit tests for CC-EC2-CONFIG-001 (Meaningful EC2 Operational Configuration Change)."""

import pytest
from backend.app.engine.rules.ec2_config import Ec2ConfigRule
from backend.app.models.change import ActionType, CanonicalChange
from backend.app.models.impact import ImpactCategory, Severity


@pytest.fixture
def rule():
    return Ec2ConfigRule()


def test_ec2_config_ebs_optimized_change_positive(rule):
    change = CanonicalChange(
        resource_address="aws_instance.app",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        requires_replacement=False,
        before={"ebs_optimized": False},
        after={"ebs_optimized": True},
    )
    assert rule.trigger(change) is True
    finding, pred = rule.evaluate(change)

    assert finding.rule_id == "CC-EC2-CONFIG-001"
    assert finding.category == ImpactCategory.PERFORMANCE
    assert finding.severity == Severity.LOW
    assert "ebs_optimized" in finding.explanation

    assert pred.metric == "operational_config"
    assert pred.expected_value == {"ebs_optimized": True}
    assert pred.direction == "MODIFIED"
    assert pred.verification_approach == "CONFIG_MATCH"
    assert pred.evidence_requirement is not None
    assert pred.evidence_requirement.service == "ec2"
    assert pred.evidence_requirement.field == "operational_config"


def test_ec2_config_multiple_attributes_positive(rule):
    change = CanonicalChange(
        resource_address="aws_instance.app",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        requires_replacement=False,
        before={"monitoring": False, "source_dest_check": True},
        after={"monitoring": True, "source_dest_check": False},
    )
    assert rule.trigger(change) is True
    finding, pred = rule.evaluate(change)

    assert "monitoring" in finding.explanation
    assert "source_dest_check" in finding.explanation
    assert pred.expected_value == {"monitoring": True, "source_dest_check": False}


def test_ec2_config_skipped_if_replacement_required_negative(rule):
    """If replacement is required, operational config change rule should not fire."""
    change = CanonicalChange(
        resource_address="aws_instance.app",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        requires_replacement=True,
        before={"monitoring": False},
        after={"monitoring": True},
    )
    assert rule.trigger(change) is False


def test_ec2_config_skipped_if_action_replace_negative(rule):
    change = CanonicalChange(
        resource_address="aws_instance.app",
        resource_type="aws_instance",
        action=ActionType.REPLACE,
        requires_replacement=False,
        before={"monitoring": False},
        after={"monitoring": True},
    )
    assert rule.trigger(change) is False


def test_ec2_config_skipped_if_delete_negative(rule):
    change = CanonicalChange(
        resource_address="aws_instance.app",
        resource_type="aws_instance",
        action=ActionType.DELETE,
        before={"monitoring": True},
        after=None,
    )
    assert rule.trigger(change) is False


def test_ec2_config_non_operational_change_negative(rule):
    """Only changing instance_type or tags should not trigger config rule."""
    change = CanonicalChange(
        resource_address="aws_instance.app",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        before={"instance_type": "t3.medium", "tags": {"Env": "dev"}},
        after={"instance_type": "t3.large", "tags": {"Env": "prod"}},
    )
    assert rule.trigger(change) is False
