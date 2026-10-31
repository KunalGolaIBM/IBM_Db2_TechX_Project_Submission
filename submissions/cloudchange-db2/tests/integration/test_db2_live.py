"""Live IBM Db2 Integration Tests.

These tests execute against a LIVE IBM Db2 database instance (e.g. running in
Docker or IBM Cloud). They are explicitly distinguished from mocked unit tests
and are marked with @pytest.mark.live_db2.

To run these tests:
1. Start an IBM Db2 instance (e.g. `docker run -d -p 50000:50000 -e DB2INST1_PASSWORD=secret ibmcom/db2`).
2. Export DB2_HOST, DB2_PORT, DB2_DATABASE, DB2_USER, DB2_PASSWORD.
3. Run: pytest -m live_db2
"""

import os
import pytest

from backend.app.db2.adapter import Db2PersistenceAdapter
from backend.app.db2.config import Db2Config
from backend.app.db2.connection import Db2ConnectionManager
from backend.app.models.change import ActionType, CanonicalChange
from backend.app.models.impact import ImpactCategory, ImpactFinding, Severity
from backend.app.models.run import Run, RunStatus, build_run_summary


@pytest.fixture(scope="module")
def live_db2_adapter():
    """Fixture providing a live Db2PersistenceAdapter if configured and reachable."""
    config = Db2Config.from_env()

    # Skip cleanly if credentials are not configured or live testing is not requested
    if not config.is_configured():
        pytest.skip("Skipping live Db2 tests: DB2 credentials (DB2_PASSWORD, etc.) are not configured in environment.")

    cm = Db2ConnectionManager(config)
    if not cm.check_connection():
        pytest.skip(f"Skipping live Db2 tests: Unable to connect to IBM Db2 at {config.host}:{config.port}.")

    adapter = Db2PersistenceAdapter(config=config, connection_manager=cm)
    # Initialize schema on live database
    adapter.init_schema()
    return adapter


@pytest.mark.live_db2
def test_live_db2_schema_and_roundtrip(live_db2_adapter):
    """Verify schema initialization and full round-trip persistence against a live IBM Db2 instance."""
    adapter = live_db2_adapter

    # Create test run
    change = CanonicalChange(
        resource_address="aws_instance.live_test",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        requires_replacement=False,
        before={"instance_type": "t3.micro"},
        after={"instance_type": "t3.large"},
    )
    finding = ImpactFinding(
        rule_id="CC-EC2-COST-001",
        rule_version="1.0.0",
        resource_address="aws_instance.live_test",
        category=ImpactCategory.COST,
        severity=Severity.LOW,
        title="Live Test Instance Resize",
        explanation="Testing live IBM Db2 insert and retrieve.",
    )
    summary = build_run_summary([change], [finding], [], [], [])

    run = Run(
        run_id="live-test-run-001",
        created_at="2026-10-31T12:00:00Z",
        status=RunStatus.PREDICTED,
        summary=summary,
        changes=[change],
        findings=[finding],
        predictions=[],
        unsupported_resources=[],
        ignored_noops=[],
        ignored_reads=[],
        verification_results=[],
    )

    try:
        # Save run to live Db2
        saved = adapter.save_run(run)
        assert saved.run_id == "live-test-run-001"

        # Retrieve run from live Db2
        fetched = adapter.get_run("live-test-run-001")
        assert fetched is not None
        assert fetched.run_id == "live-test-run-001"
        assert len(fetched.changes) == 1
        assert len(fetched.findings) == 1

        # Check audit trail in live Db2
        audit = adapter.get_audit_history("live-test-run-001")
        assert len(audit) >= 1
        assert audit[0]["run_id"] == "live-test-run-001"

        # Check governance query
        findings = adapter.get_findings_by_severity("LOW")
        assert any(f["resource_address"] == "aws_instance.live_test" for f in findings)
    finally:
        # Clean up test row
        adapter.delete_run("live-test-run-001")
