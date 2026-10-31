"""Unit tests for CC-RDS-DATA-001 (RDS Data Persistence and Lifecycle Risk)."""

import pytest
from backend.app.engine.rules.rds_data import RdsDataRule
from backend.app.models.change import ActionType, CanonicalChange
from backend.app.models.impact import ImpactCategory, Severity


@pytest.fixture
def rule():
    return RdsDataRule()


def test_rds_data_deletion_with_after_none_positive(rule):
    """Guardrail: Deletion with after=None must trigger CC-RDS-DATA-001 and declare verification approach RESOURCE_DELETED."""
    change = CanonicalChange(
        resource_address="aws_db_instance.db_to_delete",
        resource_type="aws_db_instance",
        action=ActionType.DELETE,
        before={"identifier": "db-production", "allocated_storage": 100},
        after=None,
    )
    assert rule.trigger(change) is True
    finding, pred = rule.evaluate(change)

    assert finding.rule_id == "CC-RDS-DATA-001"
    assert finding.category == ImpactCategory.DATA
    assert finding.severity == Severity.HIGH
    # Required exact wording
    assert finding.explanation == "This change may affect lifecycle or persistence characteristics."

    assert pred.metric == "instance_deletion"
    assert pred.expected_value == "DELETED"
    assert pred.direction == "DELETED"
    assert pred.verification_approach == "RESOURCE_DELETED"
    assert "DBInstanceNotFound rather than treating API errors" in pred.rationale

    assert pred.evidence_requirement is not None
    assert pred.evidence_requirement.service == "rds"
    assert pred.evidence_requirement.resource_type == "db_instance"
    assert pred.evidence_requirement.field == "DBInstanceNotFound"


def test_rds_data_replacement_with_storage_changes_positive(rule):
    """Replacement accompanied by storage alterations triggers CC-RDS-DATA-001 with CONFIG_MATCH."""
    change = CanonicalChange(
        resource_address="aws_db_instance.db_store",
        resource_type="aws_db_instance",
        action=ActionType.UPDATE,
        requires_replacement=True,
        before={
            "identifier": "db-store",
            "allocated_storage": 20,
            "storage_type": "gp2",
            "storage_encrypted": False,
        },
        after={
            "identifier": "db-store",
            "allocated_storage": 100,
            "storage_type": "gp3",
            "storage_encrypted": True,
        },
    )
    assert rule.trigger(change) is True
    finding, pred = rule.evaluate(change)

    assert finding.rule_id == "CC-RDS-DATA-001"
    assert finding.explanation == "This change may affect lifecycle or persistence characteristics."
    assert pred.metric == "storage_and_encryption_config"
    assert pred.verification_approach == "CONFIG_MATCH"
    assert pred.direction == "MODIFIED"
    assert pred.expected_value["allocated_storage"] == 100
    assert pred.expected_value["storage_type"] == "gp3"
    assert pred.expected_value["storage_encrypted"] is True

    assert pred.evidence_requirement is not None
    assert pred.evidence_requirement.field == "StorageConfig"


def test_rds_data_replacement_without_storage_changes_regression_negative(rule):
    """Regression test: Replacement without storage/persistence alterations MUST NOT trigger CC-RDS-DATA-001."""
    change = CanonicalChange(
        resource_address="aws_db_instance.db_engine_upgrade",
        resource_type="aws_db_instance",
        action=ActionType.UPDATE,
        requires_replacement=True,
        before={
            "identifier": "db-main",
            "engine_version": "13.4",
            "allocated_storage": 50,
            "storage_type": "gp2",
            "storage_encrypted": True,
        },
        after={
            "identifier": "db-main",
            "engine_version": "14.1",  # Engine version triggers replacement, but storage is unchanged
            "allocated_storage": 50,
            "storage_type": "gp2",
            "storage_encrypted": True,
        },
    )
    # Storage did not change; therefore CC-RDS-DATA-001 must NOT trigger
    assert rule.trigger(change) is False


def test_rds_data_in_place_storage_update_without_replacement_negative(rule):
    """In-place storage scaling without replacement does not trigger CC-RDS-DATA-001."""
    change = CanonicalChange(
        resource_address="aws_db_instance.db_scale",
        resource_type="aws_db_instance",
        action=ActionType.UPDATE,
        requires_replacement=False,
        before={"allocated_storage": 20},
        after={"allocated_storage": 50},
    )
    assert rule.trigger(change) is False


def test_rds_data_wrong_resource_type_negative(rule):
    change = CanonicalChange(
        resource_address="aws_instance.server",
        resource_type="aws_instance",
        action=ActionType.DELETE,
        before={"instance_type": "t3.medium"},
        after=None,
    )
    assert rule.trigger(change) is False
