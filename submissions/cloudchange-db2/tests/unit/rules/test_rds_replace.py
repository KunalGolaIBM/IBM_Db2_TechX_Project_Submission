"""Unit tests for CC-RDS-REPLACE-001 (RDS DB Instance Replacement)."""

import pytest
from backend.app.engine.rules.rds_replace import RdsReplaceRule
from backend.app.models.change import ActionType, CanonicalChange
from backend.app.models.impact import ImpactCategory, Severity


@pytest.fixture
def rule():
    return RdsReplaceRule()


def test_rds_replace_requires_replacement_positive(rule):
    change = CanonicalChange(
        resource_address="aws_db_instance.postgres",
        resource_type="aws_db_instance",
        action=ActionType.UPDATE,
        requires_replacement=True,
        before={"id": "db-abc123", "identifier": "db-old", "engine_version": "14.1"},
        after={"identifier": "db-new", "engine_version": "14.1"},
    )
    assert rule.trigger(change) is True
    finding, pred = rule.evaluate(change)

    assert finding.rule_id == "CC-RDS-REPLACE-001"
    assert finding.category == ImpactCategory.AVAILABILITY
    assert finding.severity == Severity.HIGH
    assert "downtime" in finding.explanation

    assert pred.metric == "resource_identity"
    assert pred.direction == "REPLACED"
    assert pred.verification_approach == "IDENTITY_REPLACED"
    assert pred.expected_value == {
        "transition": "REPLACED",
        "prior_physical_id": "db-abc123",
    }
    assert "dbi_resource_id" in pred.rationale
    assert "available state alone" in pred.rationale
    assert "NOT_OBSERVABLE" in pred.rationale

    assert pred.evidence_requirement is not None
    assert pred.evidence_requirement.service == "rds"
    assert pred.evidence_requirement.resource_type == "db_instance"
    assert pred.evidence_requirement.field == "dbi_resource_id"


def test_rds_replace_action_replace_positive(rule):
    change = CanonicalChange(
        resource_address="aws_db_instance.postgres",
        resource_type="aws_db_instance",
        action=ActionType.REPLACE,
        before={"dbi_resource_id": "dbi-12345678"},
        after={"identifier": "db-main"},
    )
    assert rule.trigger(change) is True
    _, pred = rule.evaluate(change)
    assert pred.verification_approach == "IDENTITY_REPLACED"
    assert pred.expected_value == {
        "transition": "REPLACED",
        "prior_physical_id": "dbi-12345678",
    }


def test_rds_replace_missing_prior_identity_leaves_unresolved(rule):
    """Regression test: Missing prior identity must remain explicitly unresolved (None), never fabricated."""
    change = CanonicalChange(
        resource_address="aws_db_instance.postgres",
        resource_type="aws_db_instance",
        action=ActionType.UPDATE,
        requires_replacement=True,
        before={},  # Missing prior identity
        after={"identifier": "db-main"},
    )
    assert rule.trigger(change) is True
    _, pred = rule.evaluate(change)
    assert isinstance(pred.expected_value, dict)
    assert pred.expected_value["transition"] == "REPLACED"
    assert pred.expected_value["prior_physical_id"] is None


def test_rds_replace_in_place_update_negative(rule):
    change = CanonicalChange(
        resource_address="aws_db_instance.postgres",
        resource_type="aws_db_instance",
        action=ActionType.UPDATE,
        requires_replacement=False,
        before={"allocated_storage": 20},
        after={"allocated_storage": 50},
    )
    assert rule.trigger(change) is False


def test_rds_replace_wrong_resource_type_negative(rule):
    change = CanonicalChange(
        resource_address="aws_instance.db_server",
        resource_type="aws_instance",
        action=ActionType.REPLACE,
        requires_replacement=True,
    )
    assert rule.trigger(change) is False
