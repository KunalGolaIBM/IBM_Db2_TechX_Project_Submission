"""Unit tests for Verification Lifecycle Orchestrator (Phase F4)."""

from unittest.mock import MagicMock
from backend.app.aws.clients import AWSClientFactory
from backend.app.aws.collectors.registry import EvidenceCollectorRegistry
from backend.app.aws.errors import (
    AWSAuthorizationError,
    AWSServiceError,
    ResourceNotFoundError,
)
from backend.app.engine.orchestrator import VerificationOrchestrator
from backend.app.models.change import ActionType, CanonicalChange
from backend.app.models.evidence import Evidence, EvidenceRequirement
from backend.app.models.prediction import Prediction, VerificationApproach
from backend.app.models.run import Run, RunStatus, build_run_summary
from backend.app.models.verification import VerificationStatus


def _build_test_run(
    predictions: list[Prediction],
    changes: list[CanonicalChange] = None,
) -> Run:
    changes = changes or []
    summary = build_run_summary(changes, [], [], [], [])
    return Run(
        run_id="test-run-1",
        created_at="2026-09-27T12:00:00Z",
        status=RunStatus.PREDICTED,
        summary=summary,
        changes=changes,
        findings=[],
        predictions=predictions,
        verification_results=[],
    )


def test_orchestrator_successful_verification_ec2_scale():
    """Verify end-to-end orchestration when AWS evidence matches prediction."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client
    mock_client.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-1234567890abcdef0",
                        "InstanceType": "t3.large",
                        "State": {"Name": "running"},
                    }
                ]
            }
        ]
    }

    pred = Prediction(
        prediction_id="pred-ec2-cost-1",
        resource_address="aws_instance.web",
        metric="instance_type",
        expected_value="t3.large",
        verification_approach=VerificationApproach.EXACT_MATCH,
        rationale="EC2 instance type scaled up",
        evidence_requirement=EvidenceRequirement(
            provider="aws",
            service="ec2",
            resource_type="instance",
            field="instance_type",
        ),
    )
    change = CanonicalChange(
        resource_address="aws_instance.web",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        before={"instance_type": "t3.small"},
        after={"instance_type": "t3.large"},
    )
    run = _build_test_run(predictions=[pred], changes=[change])

    state_artifact = {
        "format_version": "1.0",
        "resources": [
            {
                "mode": "managed",
                "type": "aws_instance",
                "name": "web",
                "instances": [
                    {"attributes": {"id": "i-1234567890abcdef0"}}
                ],
            }
        ],
    }

    factory = AWSClientFactory(session=mock_session)
    orchestrator = VerificationOrchestrator(client_factory=factory)
    updated_run = orchestrator.verify_run(run=run, state_artifact=state_artifact)

    assert updated_run.status == RunStatus.VERIFIED
    assert len(updated_run.verification_results) == 1
    res = updated_run.verification_results[0]
    assert res.prediction_id == "pred-ec2-cost-1"
    assert res.status == VerificationStatus.VERIFIED
    assert res.observed_value == "t3.large"


def test_orchestrator_mismatch_verification():
    """Verify that contradictory AWS evidence transitions run to VERIFICATION_FAILED."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client
    mock_client.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-1234567890abcdef0",
                        "InstanceType": "t3.small",  # differs from expected t3.large
                        "State": {"Name": "running"},
                    }
                ]
            }
        ]
    }

    pred = Prediction(
        prediction_id="pred-ec2-cost-2",
        resource_address="aws_instance.web",
        metric="instance_type",
        expected_value="t3.large",
        verification_approach=VerificationApproach.EXACT_MATCH,
        rationale="Expected t3.large",
        evidence_requirement=EvidenceRequirement(
            provider="aws",
            service="ec2",
            resource_type="instance",
            field="instance_type",
        ),
    )
    run = _build_test_run(predictions=[pred])

    state_artifact = {
        "resources": [
            {
                "mode": "managed",
                "type": "aws_instance",
                "name": "web",
                "instances": [{"attributes": {"id": "i-1234567890abcdef0"}}],
            }
        ]
    }

    factory = AWSClientFactory(session=mock_session)
    orchestrator = VerificationOrchestrator(client_factory=factory)
    updated_run = orchestrator.verify_run(run=run, state_artifact=state_artifact)

    assert updated_run.status == RunStatus.VERIFICATION_FAILED
    assert len(updated_run.verification_results) == 1
    assert updated_run.verification_results[0].status == VerificationStatus.MISMATCH


def test_orchestrator_unresolved_identity_not_observable():
    """Verify that when state artifact lacks physical ID, prediction becomes NOT_OBSERVABLE and run becomes PARTIALLY_VERIFIED."""
    pred = Prediction(
        prediction_id="pred-missing-id",
        resource_address="aws_instance.unknown_host",
        metric="instance_type",
        expected_value="t3.large",
        verification_approach=VerificationApproach.EXACT_MATCH,
        rationale="Target",
        evidence_requirement=EvidenceRequirement(
            provider="aws",
            service="ec2",
            resource_type="instance",
            field="instance_type",
        ),
    )
    run = _build_test_run(predictions=[pred])

    # State does not contain aws_instance.unknown_host
    state_artifact = {"resources": []}

    orchestrator = VerificationOrchestrator()
    updated_run = orchestrator.verify_run(run=run, state_artifact=state_artifact)

    assert updated_run.status == RunStatus.PARTIALLY_VERIFIED
    assert len(updated_run.verification_results) == 1
    res = updated_run.verification_results[0]
    assert res.status == VerificationStatus.NOT_OBSERVABLE
    assert "could not be resolved" in res.explanation


def test_orchestrator_aws_authorization_failure_handled():
    """Verify AWS authorization failure maps to NOT_OBSERVABLE without crashing."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client
    mock_client.describe_instances.side_effect = AWSAuthorizationError("AccessDenied to describe instances")

    pred = Prediction(
        prediction_id="pred-auth-err",
        resource_address="aws_instance.api",
        metric="instance_type",
        expected_value="t3.large",
        verification_approach=VerificationApproach.EXACT_MATCH,
        rationale="Target",
        evidence_requirement=EvidenceRequirement(
            provider="aws",
            service="ec2",
            resource_type="instance",
            field="instance_type",
        ),
    )
    run = _build_test_run(predictions=[pred])
    state_artifact = {
        "resources": [
            {
                "mode": "managed",
                "type": "aws_instance",
                "name": "api",
                "instances": [{"attributes": {"id": "i-api-123"}}],
            }
        ]
    }

    factory = AWSClientFactory(session=mock_session)
    orchestrator = VerificationOrchestrator(client_factory=factory)
    updated_run = orchestrator.verify_run(run=run, state_artifact=state_artifact)

    assert updated_run.status == RunStatus.PARTIALLY_VERIFIED
    assert updated_run.verification_results[0].status == VerificationStatus.NOT_OBSERVABLE


def test_orchestrator_resource_deletion_verified():
    """Verify RESOURCE_DELETED strategy confirms deletion when AWS returns ResourceNotFoundError."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client
    mock_client.describe_db_instances.side_effect = ResourceNotFoundError(
        resource_id="db-temp-1",
        resource_type="RDS DB instance",
    )

    pred = Prediction(
        prediction_id="pred-rds-del-1",
        resource_address="aws_db_instance.db_temp",
        metric="instance_deletion",
        expected_value="DELETED",
        verification_approach=VerificationApproach.RESOURCE_DELETED,
        rationale="RDS instance scheduled for deletion",
        evidence_requirement=EvidenceRequirement(
            provider="aws",
            service="rds",
            resource_type="db_instance",
            field="StorageConfig",
        ),
    )
    change = CanonicalChange(
        resource_address="aws_db_instance.db_temp",
        resource_type="aws_db_instance",
        action=ActionType.DELETE,
        before={"identifier": "db-temp-1"},
        after=None,
    )
    run = _build_test_run(predictions=[pred], changes=[change])

    # Destroyed DB instance is absent from post-apply state
    state_artifact = {"resources": []}

    factory = AWSClientFactory(session=mock_session)
    orchestrator = VerificationOrchestrator(client_factory=factory)
    updated_run = orchestrator.verify_run(run=run, state_artifact=state_artifact)

    assert updated_run.status == RunStatus.VERIFIED
    assert len(updated_run.verification_results) == 1
    assert updated_run.verification_results[0].status == VerificationStatus.VERIFIED


def test_orchestrator_multiple_predictions_mixed_outcomes():
    """Verify multiple predictions with mixed results aggregate correctly."""
    mock_session = MagicMock()
    mock_client_ec2 = MagicMock()
    mock_client_rds = MagicMock()

    mock_session.client.side_effect = lambda svc, region_name: mock_client_ec2 if svc == "ec2" else mock_client_rds

    # EC2 instance matches
    mock_client_ec2.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"InstanceId": "i-web-1", "InstanceType": "t3.large"}]}]
    }
    # RDS instance mismatches (allocated storage differs)
    mock_client_rds.describe_db_instances.return_value = {
        "DBInstances": [{"DBInstanceIdentifier": "db-prod", "AllocatedStorage": 50, "StorageType": "gp2", "StorageEncrypted": False}]
    }

    pred_ec2 = Prediction(
        prediction_id="pred-1",
        resource_address="aws_instance.web",
        metric="instance_type",
        expected_value="t3.large",
        verification_approach=VerificationApproach.EXACT_MATCH,
        rationale="EC2 cost scale",
        evidence_requirement=EvidenceRequirement(
            provider="aws",
            service="ec2",
            resource_type="instance",
            field="instance_type",
        ),
    )
    pred_rds = Prediction(
        prediction_id="pred-2",
        resource_address="aws_db_instance.db",
        metric="storage_and_encryption_config",
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
    run = _build_test_run(predictions=[pred_ec2, pred_rds])

    state_artifact = {
        "resources": [
            {"mode": "managed", "type": "aws_instance", "name": "web", "instances": [{"attributes": {"id": "i-web-1"}}]},
            {"mode": "managed", "type": "aws_db_instance", "name": "db", "instances": [{"attributes": {"identifier": "db-prod"}}]},
        ]
    }

    factory = AWSClientFactory(session=mock_session)
    orchestrator = VerificationOrchestrator(client_factory=factory)
    updated_run = orchestrator.verify_run(run=run, state_artifact=state_artifact)

    # Since 1 passed and 1 failed, overall status is VERIFICATION_FAILED
    assert updated_run.status == RunStatus.VERIFICATION_FAILED
    assert len(updated_run.verification_results) == 2
    assert updated_run.verification_results[0].status == VerificationStatus.VERIFIED
    assert updated_run.verification_results[1].status == VerificationStatus.MISMATCH


def test_orchestrator_empty_predictions_run_verified():
    """Verify run with 0 predictions transitions to VERIFIED cleanly."""
    run = _build_test_run(predictions=[])
    orchestrator = VerificationOrchestrator()
    updated_run = orchestrator.verify_run(run=run, state_artifact={})

    assert updated_run.status == RunStatus.VERIFIED
    assert updated_run.verification_results == []
