"""Unit tests for IBM Db2 Persistence Adapter."""

import json
from unittest import mock
import pytest

from backend.app.db2.adapter import Db2PersistenceAdapter
from backend.app.db2.connection import Db2ConnectionManager, Db2ExecutionError
from backend.app.models.change import ActionType, AttributeDiff, CanonicalChange
from backend.app.models.evidence import EvidenceRequirement
from backend.app.models.impact import ImpactCategory, ImpactFinding, Severity
from backend.app.models.prediction import Prediction, VerificationApproach
from backend.app.models.run import Run, RunStatus, build_run_summary
from backend.app.models.verification import VerificationResult, VerificationStatus


@pytest.fixture
def sample_run() -> Run:
    """Create a realistic CloudChange Run domain model instance."""
    changes = [
        CanonicalChange(
            resource_address="aws_instance.api_server",
            resource_type="aws_instance",
            action=ActionType.UPDATE,
            diffs=[
                AttributeDiff(path="instance_type", before="t3.medium", after="t3.xlarge")
            ],
            requires_replacement=False,
            before={"instance_type": "t3.medium"},
            after={"instance_type": "t3.xlarge"},
        ),
        CanonicalChange(
            resource_address="aws_db_instance.primary",
            resource_type="aws_db_instance",
            action=ActionType.REPLACE,
            diffs=[
                AttributeDiff(path="allocated_storage", before=50, after=200)
            ],
            requires_replacement=True,
            before={"allocated_storage": 50},
            after={"allocated_storage": 200},
        ),
    ]

    findings = [
        ImpactFinding(
            rule_id="CC-EC2-COST-001",
            rule_version="1.0.0",
            resource_address="aws_instance.api_server",
            category=ImpactCategory.COST,
            severity=Severity.MEDIUM,
            title="EC2 Instance Type Scale Up",
            explanation="Scaling from t3.medium to t3.xlarge increases hourly compute cost by ~300%.",
        ),
        ImpactFinding(
            rule_id="CC-RDS-REPLACE-001",
            rule_version="1.0.0",
            resource_address="aws_db_instance.primary",
            category=ImpactCategory.AVAILABILITY,
            severity=Severity.HIGH,
            title="Destructive Database Re-creation",
            explanation="Storage change forces replacement of primary database instance with potential downtime.",
        ),
    ]

    predictions = [
        Prediction(
            prediction_id="pred-ec2-type",
            resource_address="aws_instance.api_server",
            metric="instance_type",
            expected_value="t3.xlarge",
            direction="SCALE_UP",
            verification_approach=VerificationApproach.EXACT_MATCH,
            rationale="Plan specifies target instance_type t3.xlarge.",
            evidence_requirement=EvidenceRequirement(
                provider="aws",
                service="ec2",
                resource_type="instance",
                field="InstanceType",
            ),
        )
    ]

    summary = build_run_summary(
        changes=changes,
        findings=findings,
        unsupported_resources=[],
        ignored_noops=[],
        ignored_reads=[],
    )

    return Run(
        run_id="run-uuid-12345",
        created_at="2026-10-31T12:00:00Z",
        status=RunStatus.PREDICTED,
        summary=summary,
        changes=changes,
        findings=findings,
        predictions=predictions,
        unsupported_resources=[],
        ignored_noops=[],
        ignored_reads=[],
        verification_results=[],
    )


def test_db2_adapter_save_run_insert_new(sample_run):
    """Verify saving a new run inserts into cc_runs, child tables, and cc_audit_events."""
    mock_cm = mock.MagicMock(spec=Db2ConnectionManager)
    mock_conn = mock.MagicMock()

    # contextmanager transaction yields mock_conn
    mock_cm.transaction.return_value.__enter__.return_value = mock_conn

    # Check query returns None (not existing yet)
    mock_cm.fetch_one_assoc.return_value = None

    adapter = Db2PersistenceAdapter(connection_manager=mock_cm)
    saved = adapter.save_run(sample_run)

    assert saved.run_id == sample_run.run_id
    mock_cm.transaction.assert_called_once()

    # Check statements executed
    calls = mock_cm.execute_statement.call_args_list
    assert len(calls) >= 6  # check, insert run, 2 changes, 2 findings, 1 prediction, 1 audit event

    # Verify parameterized check
    assert "SELECT run_id FROM cc_runs WHERE run_id = ?" in calls[0][0][1]
    assert calls[0][0][2] == (sample_run.run_id,)

    # Verify INSERT INTO cc_runs
    assert "INSERT INTO cc_runs" in calls[1][0][1]


def test_db2_adapter_save_run_update_existing(sample_run):
    """Verify updating an existing run updates cc_runs and refreshes child entities."""
    mock_cm = mock.MagicMock(spec=Db2ConnectionManager)
    mock_conn = mock.MagicMock()
    mock_cm.transaction.return_value.__enter__.return_value = mock_conn

    # Check query returns existing run row
    mock_cm.fetch_one_assoc.return_value = {"run_id": sample_run.run_id}

    adapter = Db2PersistenceAdapter(connection_manager=mock_cm)
    saved = adapter.save_run(sample_run)

    assert saved.run_id == sample_run.run_id
    calls = mock_cm.execute_statement.call_args_list
    sql_statements = [call[0][1] for call in calls]

    # Verify UPDATE cc_runs was executed
    assert any("UPDATE cc_runs" in s for s in sql_statements)
    # Verify child tables were cleaned for refresh
    assert any("DELETE FROM cc_canonical_changes" in s for s in sql_statements)
    assert any("DELETE FROM cc_impact_findings" in s for s in sql_statements)


def test_db2_adapter_save_run_rollback_on_error(sample_run):
    """Verify transaction boundary rolls back if an execution error occurs during save."""
    mock_cm = mock.MagicMock(spec=Db2ConnectionManager)
    mock_conn = mock.MagicMock()

    def raise_on_insert(*args, **kwargs):
        if "INSERT INTO cc_runs" in args[1]:
            raise Db2ExecutionError("Disk full or constraint violation")
        return mock.MagicMock()

    mock_cm.execute_statement.side_effect = raise_on_insert
    mock_cm.fetch_one_assoc.return_value = None

    # Context manager simulates actual transaction rollback behavior
    class FakeTransaction:
        def __enter__(self):
            return mock_conn
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                mock_conn.rollback()
            return False

    mock_cm.transaction.return_value = FakeTransaction()

    adapter = Db2PersistenceAdapter(connection_manager=mock_cm)
    with pytest.raises(Db2ExecutionError, match="Disk full"):
        adapter.save_run(sample_run)

    mock_conn.rollback.assert_called_once()


def test_db2_adapter_get_run_found(sample_run):
    """Verify get_run retrieves and deserializes the full Run model."""
    mock_cm = mock.MagicMock(spec=Db2ConnectionManager)
    mock_conn = mock.MagicMock()
    mock_cm.connect.return_value = mock_conn

    raw_json = sample_run.model_dump_json()
    mock_cm.fetch_one_assoc.return_value = {"raw_run_json": raw_json}

    adapter = Db2PersistenceAdapter(connection_manager=mock_cm)
    result = adapter.get_run(sample_run.run_id)

    assert result is not None
    assert result.run_id == sample_run.run_id
    assert len(result.changes) == 2
    assert len(result.findings) == 2
    mock_cm.close.assert_called_once_with(mock_conn)


def test_db2_adapter_get_run_not_found():
    """Verify get_run returns None when run_id does not exist."""
    mock_cm = mock.MagicMock(spec=Db2ConnectionManager)
    mock_conn = mock.MagicMock()
    mock_cm.connect.return_value = mock_conn
    mock_cm.fetch_one_assoc.return_value = None

    adapter = Db2PersistenceAdapter(connection_manager=mock_cm)
    result = adapter.get_run("non-existent-id")

    assert result is None
    mock_cm.close.assert_called_once_with(mock_conn)


def test_db2_adapter_list_runs(sample_run):
    """Verify list_runs queries with ordering and limit."""
    mock_cm = mock.MagicMock(spec=Db2ConnectionManager)
    mock_conn = mock.MagicMock()
    mock_cm.connect.return_value = mock_conn

    raw_json = sample_run.model_dump_json()
    mock_cm.fetch_all_assoc.return_value = [{"raw_run_json": raw_json}]

    adapter = Db2PersistenceAdapter(connection_manager=mock_cm)
    runs = adapter.list_runs(limit=10)

    assert len(runs) == 1
    assert runs[0].run_id == sample_run.run_id
    mock_cm.close.assert_called_once_with(mock_conn)


def test_db2_adapter_count_and_delete(sample_run):
    """Verify count_runs and delete_run queries."""
    mock_cm = mock.MagicMock(spec=Db2ConnectionManager)
    mock_conn = mock.MagicMock()
    mock_cm.connect.return_value = mock_conn
    mock_cm.fetch_one_assoc.return_value = {"total_count": 42}
    mock_cm.transaction.return_value.__enter__.return_value = mock_conn

    adapter = Db2PersistenceAdapter(connection_manager=mock_cm)
    cnt = adapter.count_runs()
    assert cnt == 42

    res = adapter.delete_run("run-123")
    assert res is True


def test_db2_adapter_analytics_queries():
    """Verify governance analytics helper queries."""
    mock_cm = mock.MagicMock(spec=Db2ConnectionManager)
    mock_conn = mock.MagicMock()
    mock_cm.connect.return_value = mock_conn

    mock_cm.fetch_all_assoc.side_effect = [
        # audit history
        [{"event_id": "e1", "event_type": "RUN_CREATED", "payload_json": '{"status":"PREDICTED"}'}],
        # findings by severity
        [{"finding_id": "f1", "severity": "HIGH", "title": "Destructive DB"}],
        # high risk changes
        [{"change_id": "c1", "requires_replacement": 1, "resource_address": "aws_db_instance.primary"}],
        # verification summary
        [{"status": "VERIFIED", "status_count": 10}, {"status": "MISMATCH", "status_count": 2}],
    ]

    adapter = Db2PersistenceAdapter(connection_manager=mock_cm)

    # 1. Audit history
    audit = adapter.get_audit_history("run-123")
    assert len(audit) == 1
    assert audit[0]["payload"] == {"status": "PREDICTED"}

    # 2. Findings by severity
    findings = adapter.get_findings_by_severity("HIGH")
    assert len(findings) == 1

    # 3. High risk changes
    changes = adapter.get_high_risk_changes()
    assert len(changes) == 1

    # 4. Verification metrics
    metrics = adapter.get_verification_metrics()
    assert metrics["total"] == 12
    assert metrics["by_status"]["VERIFIED"] == 10
    assert metrics["by_status"]["MISMATCH"] == 2
