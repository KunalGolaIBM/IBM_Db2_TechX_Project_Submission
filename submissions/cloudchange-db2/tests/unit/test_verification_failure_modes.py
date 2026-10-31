"""Unit tests for AWS verification failure modes, timeouts, and unobservable conditions."""

from unittest.mock import MagicMock
from backend.app.aws.clients import AWSClientFactory
from backend.app.aws.errors import (
    AWSAuthorizationError,
    AWSServiceError,
    ResourceNotFoundError,
    UnsupportedFieldError,
)
from backend.app.engine.orchestrator import VerificationOrchestrator
from backend.app.engine.verifier import Verifier
from backend.app.models.change import ActionType, CanonicalChange
from backend.app.models.evidence import EvidenceRequirement
from backend.app.models.prediction import Prediction, VerificationApproach
from backend.app.models.run import Run, RunStatus, build_run_summary
from backend.app.models.verification import VerificationStatus


def _make_run(predictions, changes=None):
    changes = changes or []
    summary = build_run_summary(changes, [], [], [], [])
    return Run(
        run_id="run-fail-test",
        created_at="2026-09-27T12:00:00Z",
        status=RunStatus.PREDICTED,
        summary=summary,
        changes=changes,
        findings=[],
        predictions=predictions,
        verification_results=[],
    )


def test_throttling_failure_mapped_to_not_observable():
    """Verify AWS request throttling is mapped to NOT_OBSERVABLE."""
    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    mock_session.client.return_value = mock_ec2
    mock_ec2.describe_instances.side_effect = AWSServiceError("RequestLimitExceeded: Rate exceeded")

    pred = Prediction(
        prediction_id="pred-throttle",
        resource_address="aws_instance.app",
        metric="instance_type",
        expected_value="t3.large",
        verification_approach=VerificationApproach.EXACT_MATCH,
        rationale="EC2 scaling",
        evidence_requirement=EvidenceRequirement(
            provider="aws",
            service="ec2",
            resource_type="instance",
            field="instance_type",
        ),
    )
    run = _make_run([pred])
    state = {
        "resources": [
            {"mode": "managed", "type": "aws_instance", "name": "app", "instances": [{"attributes": {"id": "i-app-1"}}]}
        ]
    }

    factory = AWSClientFactory(session=mock_session)
    orchestrator = VerificationOrchestrator(client_factory=factory)
    updated_run = orchestrator.verify_run(run, state)

    assert updated_run.status == RunStatus.PARTIALLY_VERIFIED
    assert len(updated_run.verification_results) == 1
    assert updated_run.verification_results[0].status == VerificationStatus.NOT_OBSERVABLE
    assert "AWS observation failed" in updated_run.verification_results[0].explanation


def test_access_denied_mapped_to_not_observable():
    """Verify AWS IAM permission failure maps to NOT_OBSERVABLE without failing the run with MISMATCH."""
    mock_session = MagicMock()
    mock_rds = MagicMock()
    mock_session.client.return_value = mock_rds
    mock_rds.describe_db_instances.side_effect = AWSAuthorizationError("User is not authorized to perform: rds:DescribeDBInstances")

    pred = Prediction(
        prediction_id="pred-auth",
        resource_address="aws_db_instance.db",
        metric="StorageConfig",
        expected_value={"allocated_storage": 100},
        verification_approach=VerificationApproach.CONFIG_MATCH,
        rationale="RDS storage",
        evidence_requirement=EvidenceRequirement(
            provider="aws",
            service="rds",
            resource_type="db_instance",
            field="StorageConfig",
        ),
    )
    run = _make_run([pred])
    state = {
        "resources": [
            {"mode": "managed", "type": "aws_db_instance", "name": "db", "instances": [{"attributes": {"identifier": "db-prod"}}]}
        ]
    }

    factory = AWSClientFactory(session=mock_session)
    orchestrator = VerificationOrchestrator(client_factory=factory)
    updated_run = orchestrator.verify_run(run, state)

    assert updated_run.status == RunStatus.PARTIALLY_VERIFIED
    assert updated_run.verification_results[0].status == VerificationStatus.NOT_OBSERVABLE


def test_unsupported_field_gracefully_handled():
    """Verify requesting an unsupported field raises UnsupportedFieldError and maps to NOT_OBSERVABLE."""
    pred = Prediction(
        prediction_id="pred-bad-field",
        resource_address="aws_instance.app",
        metric="nonexistent_quantum_metric",
        expected_value="enabled",
        verification_approach=VerificationApproach.EXACT_MATCH,
        rationale="Bad field test",
        evidence_requirement=EvidenceRequirement(
            provider="aws",
            service="ec2",
            resource_type="instance",
            field="nonexistent_quantum_metric",
        ),
    )
    run = _make_run([pred])

    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    mock_session.client.return_value = mock_ec2
    mock_ec2.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"InstanceId": "i-app-1", "InstanceType": "t3.large"}]}]
    }

    factory = AWSClientFactory(session=mock_session)
    orchestrator = VerificationOrchestrator(client_factory=factory)
    state = {
        "resources": [
            {"mode": "managed", "type": "aws_instance", "name": "app", "instances": [{"attributes": {"id": "i-app-1"}}]}
        ]
    }
    updated_run = orchestrator.verify_run(run, state)

    assert updated_run.status == RunStatus.PARTIALLY_VERIFIED
    assert updated_run.verification_results[0].status == VerificationStatus.NOT_OBSERVABLE
