"""Unit tests for CC-EC2-REPLACE-001 (EC2 Forced Resource Replacement)."""

import pytest
from backend.app.engine.rules.ec2_replace import Ec2ReplaceRule
from backend.app.models.change import ActionType, CanonicalChange
from backend.app.models.impact import ImpactCategory, Severity


@pytest.fixture
def rule():
    return Ec2ReplaceRule()


def test_ec2_replace_requires_replacement_positive(rule):
    change = CanonicalChange(
        resource_address="aws_instance.web",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        requires_replacement=True,
        before={"id": "i-0011223344", "instance_type": "t3.medium", "ami": "ami-old"},
        after={"instance_type": "t3.medium", "ami": "ami-new"},
    )
    assert rule.trigger(change) is True
    finding, pred = rule.evaluate(change)

    assert finding.rule_id == "CC-EC2-REPLACE-001"
    assert finding.category == ImpactCategory.AVAILABILITY
    assert finding.severity == Severity.HIGH
    assert "downtime" in finding.explanation

    assert pred.metric == "resource_identity"
    assert pred.direction == "REPLACED"
    assert pred.verification_approach == "IDENTITY_REPLACED"
    assert pred.expected_value == {
        "transition": "REPLACED",
        "prior_physical_id": "i-0011223344",
    }
    assert "pre-apply physical instance ID" in pred.rationale
    assert "running state alone" in pred.rationale
    assert "NOT_OBSERVABLE" in pred.rationale

    assert pred.evidence_requirement is not None
    assert pred.evidence_requirement.service == "ec2"
    assert pred.evidence_requirement.field == "instance_id"


def test_ec2_replace_action_replace_positive(rule):
    change = CanonicalChange(
        resource_address="aws_instance.db_host",
        resource_type="aws_instance",
        action=ActionType.REPLACE,
        requires_replacement=False,  # action itself is REPLACE
        before={"id": "i-12345"},
        after={"instance_type": "t3.large"},
    )
    assert rule.trigger(change) is True
    _, pred = rule.evaluate(change)
    assert pred.verification_approach == "IDENTITY_REPLACED"
    assert pred.expected_value == {
        "transition": "REPLACED",
        "prior_physical_id": "i-12345",
    }


def test_ec2_replace_in_place_update_negative(rule):
    change = CanonicalChange(
        resource_address="aws_instance.web",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        requires_replacement=False,
        before={"monitoring": False},
        after={"monitoring": True},
    )
    assert rule.trigger(change) is False


def test_ec2_replace_wrong_resource_type_negative(rule):
    change = CanonicalChange(
        resource_address="aws_security_group.sg",
        resource_type="aws_security_group",
        action=ActionType.REPLACE,
        requires_replacement=True,
    )
    assert rule.trigger(change) is False


def test_ec2_replace_missing_prior_identity_does_not_fabricate_id(rule):
    """Regression test: When change lacks prior identity attributes, the rule does not fabricate one."""
    change = CanonicalChange(
        resource_address="aws_instance.no_id",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        requires_replacement=True,
        before={},  # No id present in prior state
        after={"instance_type": "t3.medium"},
    )
    assert rule.trigger(change) is True
    _, pred = rule.evaluate(change)
    # Ensure expected value is a structured descriptor with prior_physical_id as explicitly None (unresolved)
    assert isinstance(pred.expected_value, dict)
    assert pred.expected_value["transition"] == "REPLACED"
    assert pred.expected_value["prior_physical_id"] is None
    assert pred.verification_approach == "IDENTITY_REPLACED"
    assert "NOT_OBSERVABLE" in pred.rationale
