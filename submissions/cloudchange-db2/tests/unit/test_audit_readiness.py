"""F6 Architecture Audit & Real-AWS Readiness Regression Tests.

Validates:
1. Region resolution hierarchy (A: us-east-1, B: inferred other region, C: explicit override, D: missing fallback)
2. RDS deletion semantics (expected deletion + resource still exists -> MISMATCH)
3. Replacement semantics (same ID, different ID, missing prior ID, missing new ID)
4. StateIdentityResolver module-prefixed address resolution
"""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.app.api.runs import get_verification_orchestrator
from backend.app.aws.clients import AWSClientFactory
from backend.app.aws.errors import AWSAuthorizationError, ResourceNotFoundError
from backend.app.aws.identity import StateIdentityResolver
from backend.app.engine.orchestrator import VerificationOrchestrator
from backend.app.engine.verifier import Verifier
from backend.app.main import app
from backend.app.models.change import ActionType, CanonicalChange
from backend.app.models.evidence import Evidence, EvidenceRequirement
from backend.app.models.prediction import Prediction, VerificationApproach
from backend.app.models.run import Run, RunStatus, build_run_summary
from backend.app.models.verification import VerificationStatus


def _build_test_run(predictions, changes=None):
    changes = changes or []
    summary = build_run_summary(changes, [], [], [], [])
    return Run(
        run_id="test-audit-run",
        created_at="2026-09-28T12:00:00Z",
        status=RunStatus.PREDICTED,
        summary=summary,
        changes=changes,
        findings=[],
        predictions=predictions,
        verification_results=[],
    )


# ==============================================================================
# 1. REGION RESOLUTION TESTS (A, B, C, D)
# ==============================================================================

def test_region_scenario_a_ec2_default_us_east_1():
    """Scenario A: EC2 without AZ or override uses default us-east-1."""
    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    called_regions = []

    def mock_client_factory(svc, region_name):
        called_regions.append(region_name)
        return mock_ec2

    mock_session.client.side_effect = mock_client_factory
    mock_ec2.describe_instances.return_value = {
        "Reservations": [
            {"Instances": [{"InstanceId": "i-111", "InstanceType": "t3.micro", "State": {"Name": "running"}}]}
        ]
    }

    pred = Prediction(
        prediction_id="pred-a",
        resource_address="aws_instance.app",
        metric="instance_type",
        expected_value="t3.micro",
        verification_approach=VerificationApproach.EXACT_MATCH,
        rationale="test",
        evidence_requirement=EvidenceRequirement(
            provider="aws", service="ec2", resource_type="instance", field="instance_type"
        ),
    )
    change = CanonicalChange(
        resource_address="aws_instance.app",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        before={"instance_type": "t3.nano"},
        after={"instance_type": "t3.micro"},  # No AZ declared
    )
    run = _build_test_run([pred], [change])
    state = {"resources": [{"mode": "managed", "type": "aws_instance", "name": "app", "instances": [{"attributes": {"id": "i-111"}}]}]}

    factory = AWSClientFactory(session=mock_session)
    orchestrator = VerificationOrchestrator(client_factory=factory)
    orchestrator.verify_run(run, state)

    assert "us-east-1" in called_regions


def test_region_scenario_b_ec2_inferred_from_availability_zone():
    """Scenario B: EC2 in another region inferred from availability_zone (e.g. us-west-2b -> us-west-2)."""
    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    called_regions = []

    def mock_client_factory(svc, region_name):
        called_regions.append(region_name)
        return mock_ec2

    mock_session.client.side_effect = mock_client_factory
    mock_ec2.describe_instances.return_value = {
        "Reservations": [
            {"Instances": [{"InstanceId": "i-222", "InstanceType": "t3.large", "State": {"Name": "running"}}]}
        ]
    }

    pred = Prediction(
        prediction_id="pred-b",
        resource_address="aws_instance.worker",
        metric="instance_type",
        expected_value="t3.large",
        verification_approach=VerificationApproach.EXACT_MATCH,
        rationale="test",
        evidence_requirement=EvidenceRequirement(
            provider="aws", service="ec2", resource_type="instance", field="instance_type"
        ),
    )
    change = CanonicalChange(
        resource_address="aws_instance.worker",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        before={"instance_type": "t3.medium"},
        after={"instance_type": "t3.large", "availability_zone": "us-west-2b"},
    )
    run = _build_test_run([pred], [change])
    state = {"resources": [{"mode": "managed", "type": "aws_instance", "name": "worker", "instances": [{"attributes": {"id": "i-222"}}]}]}

    factory = AWSClientFactory(session=mock_session)
    orchestrator = VerificationOrchestrator(client_factory=factory)
    orchestrator.verify_run(run, state)

    assert "us-west-2" in called_regions


def test_region_scenario_c_explicit_verification_override():
    """Scenario C: Explicit region override parameter overrides resource AZ."""
    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    called_regions = []

    def mock_client_factory(svc, region_name):
        called_regions.append(region_name)
        return mock_ec2

    mock_session.client.side_effect = mock_client_factory
    mock_ec2.describe_instances.return_value = {
        "Reservations": [
            {"Instances": [{"InstanceId": "i-333", "InstanceType": "t3.large", "State": {"Name": "running"}}]}
        ]
    }

    pred = Prediction(
        prediction_id="pred-c",
        resource_address="aws_instance.app",
        metric="instance_type",
        expected_value="t3.large",
        verification_approach=VerificationApproach.EXACT_MATCH,
        rationale="test",
        evidence_requirement=EvidenceRequirement(
            provider="aws", service="ec2", resource_type="instance", field="instance_type"
        ),
    )
    change = CanonicalChange(
        resource_address="aws_instance.app",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        before={"instance_type": "t3.micro"},
        after={"instance_type": "t3.large", "availability_zone": "us-west-2a"},
    )
    run = _build_test_run([pred], [change])
    state = {"resources": [{"mode": "managed", "type": "aws_instance", "name": "app", "instances": [{"attributes": {"id": "i-333"}}]}]}

    factory = AWSClientFactory(session=mock_session)
    orchestrator = VerificationOrchestrator(client_factory=factory)
    # Explicitly override with eu-central-1
    orchestrator.verify_run(run, state, region="eu-central-1")

    assert "eu-central-1" in called_regions


def test_region_scenario_d_missing_region_fallback():
    """Scenario D: When neither change nor state contains region info, falls back to default region."""
    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    called_regions = []

    def mock_client_factory(svc, region_name):
        called_regions.append(region_name)
        return mock_ec2

    mock_session.client.side_effect = mock_client_factory
    mock_ec2.describe_instances.return_value = {
        "Reservations": [
            {"Instances": [{"InstanceId": "i-444", "InstanceType": "t3.micro", "State": {"Name": "running"}}]}
        ]
    }

    pred = Prediction(
        prediction_id="pred-d",
        resource_address="aws_instance.app",
        metric="instance_type",
        expected_value="t3.micro",
        verification_approach=VerificationApproach.EXACT_MATCH,
        rationale="test",
        evidence_requirement=EvidenceRequirement(
            provider="aws", service="ec2", resource_type="instance", field="instance_type"
        ),
    )
    run = _build_test_run([pred], [])
    state = {"resources": [{"mode": "managed", "type": "aws_instance", "name": "app", "instances": [{"attributes": {"id": "i-444"}}]}]}

    factory = AWSClientFactory(session=mock_session)
    orchestrator = VerificationOrchestrator(client_factory=factory)
    orchestrator.verify_run(run, state, region=None)

    assert "us-east-1" in called_regions


# ==============================================================================
# 2. DELETION SEMANTICS & RDSEvidenceCollector FIX
# ==============================================================================

def test_rds_deletion_resource_still_exists_produces_mismatch():
    """Verify that if an RDS DB instance is expected to be deleted but STILL EXISTS in AWS, it yields MISMATCH."""
    mock_session = MagicMock()
    mock_rds = MagicMock()
    mock_session.client.return_value = mock_rds

    # AWS returns DB instance still present (status='available')
    mock_rds.describe_db_instances.return_value = {
        "DBInstances": [
            {
                "DBInstanceIdentifier": "prod-db",
                "DbiResourceId": "db-12345",
                "DBInstanceClass": "db.t3.medium",
                "DBInstanceStatus": "available",
                "AllocatedStorage": 50,
                "StorageType": "gp2",
                "StorageEncrypted": True,
            }
        ]
    }

    pred = Prediction(
        prediction_id="pred-del-rds",
        resource_address="aws_db_instance.prod",
        metric="instance_deletion",
        expected_value="DELETED",
        direction="DELETED",
        verification_approach=VerificationApproach.RESOURCE_DELETED,
        rationale="confirm deleted",
        evidence_requirement=EvidenceRequirement(
            provider="aws",
            service="rds",
            resource_type="db_instance",
            field="DBInstanceNotFound",
        ),
    )
    change = CanonicalChange(
        resource_address="aws_db_instance.prod",
        resource_type="aws_db_instance",
        action=ActionType.DELETE,
        before={"identifier": "prod-db"},
        after=None,
    )
    run = _build_test_run([pred], [change])
    state = {"resources": []}  # empty state post-deletion

    factory = AWSClientFactory(session=mock_session)
    orchestrator = VerificationOrchestrator(client_factory=factory)
    updated_run = orchestrator.verify_run(run, state)

    # Must produce MISMATCH because resource still exists, not NOT_OBSERVABLE
    assert updated_run.status == RunStatus.VERIFICATION_FAILED
    assert len(updated_run.verification_results) == 1
    res = updated_run.verification_results[0]
    assert res.status == VerificationStatus.MISMATCH
    assert "still exists in AWS" in res.explanation
    assert res.observed_value == "available"


def test_rds_deletion_confirmed_when_not_found():
    """Verify that when AWS returns DBInstanceNotFound, it is VERIFIED."""
    mock_session = MagicMock()
    mock_rds = MagicMock()
    mock_session.client.return_value = mock_rds
    mock_rds.describe_db_instances.side_effect = ResourceNotFoundError(
        resource_id="prod-db",
        resource_type="RDS DB instance",
    )

    pred = Prediction(
        prediction_id="pred-del-rds-2",
        resource_address="aws_db_instance.prod",
        metric="instance_deletion",
        expected_value="DELETED",
        direction="DELETED",
        verification_approach=VerificationApproach.RESOURCE_DELETED,
        rationale="confirm deleted",
        evidence_requirement=EvidenceRequirement(
            provider="aws",
            service="rds",
            resource_type="db_instance",
            field="DBInstanceNotFound",
        ),
    )
    change = CanonicalChange(
        resource_address="aws_db_instance.prod",
        resource_type="aws_db_instance",
        action=ActionType.DELETE,
        before={"identifier": "prod-db"},
        after=None,
    )
    run = _build_test_run([pred], [change])
    state = {"resources": []}

    factory = AWSClientFactory(session=mock_session)
    orchestrator = VerificationOrchestrator(client_factory=factory)
    updated_run = orchestrator.verify_run(run, state)

    assert updated_run.status == RunStatus.VERIFIED
    assert updated_run.verification_results[0].status == VerificationStatus.VERIFIED
    assert updated_run.verification_results[0].observed_value == "RESOURCE_NOT_FOUND"


# ==============================================================================
# 3. REPLACEMENT SEMANTICS (A, B, C, D)
# ==============================================================================

def test_replacement_scenario_a_same_physical_id_is_mismatch():
    """Scenario A: If physical ID is identical after apply, replacement failed -> MISMATCH."""
    pred = Prediction(
        prediction_id="pred-rep-a",
        resource_address="aws_instance.app",
        metric="resource_identity",
        expected_value={"transition": "REPLACED", "prior_physical_id": "i-original"},
        verification_approach=VerificationApproach.IDENTITY_REPLACED,
        rationale="test",
        evidence_requirement=EvidenceRequirement(
            provider="aws", service="ec2", resource_type="instance", field="instance_id"
        ),
    )
    ev = Evidence(
        source="aws.ec2",
        resource_id="i-original",
        field="instance_id",
        observed_value={"instance_id": "i-original"},
        observed_at="2026-09-28T12:00:00Z",
    )
    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)
    assert res.status == VerificationStatus.MISMATCH


def test_replacement_scenario_b_different_physical_id_is_verified():
    """Scenario B: If physical ID changed, replacement succeeded -> VERIFIED."""
    pred = Prediction(
        prediction_id="pred-rep-b",
        resource_address="aws_instance.app",
        metric="resource_identity",
        expected_value={"transition": "REPLACED", "prior_physical_id": "i-original"},
        verification_approach=VerificationApproach.IDENTITY_REPLACED,
        rationale="test",
        evidence_requirement=EvidenceRequirement(
            provider="aws", service="ec2", resource_type="instance", field="instance_id"
        ),
    )
    ev = Evidence(
        source="aws.ec2",
        resource_id="i-new-999",
        field="instance_id",
        observed_value={"instance_id": "i-new-999"},
        observed_at="2026-09-28T12:00:00Z",
    )
    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)
    assert res.status == VerificationStatus.VERIFIED


def test_replacement_scenario_c_missing_previous_id_is_not_observable():
    """Scenario C: If pre-apply ID is missing/None, cannot confirm replacement -> NOT_OBSERVABLE."""
    pred = Prediction(
        prediction_id="pred-rep-c",
        resource_address="aws_instance.app",
        metric="resource_identity",
        expected_value={"transition": "REPLACED", "prior_physical_id": None},
        verification_approach=VerificationApproach.IDENTITY_REPLACED,
        rationale="test",
        evidence_requirement=EvidenceRequirement(
            provider="aws", service="ec2", resource_type="instance", field="instance_id"
        ),
    )
    ev = Evidence(
        source="aws.ec2",
        resource_id="i-new-999",
        field="instance_id",
        observed_value={"instance_id": "i-new-999"},
        observed_at="2026-09-28T12:00:00Z",
    )
    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)
    assert res.status == VerificationStatus.NOT_OBSERVABLE


def test_replacement_scenario_d_missing_new_id_is_not_observable():
    """Scenario D: If post-apply ID in evidence is missing/empty, cannot confirm replacement -> NOT_OBSERVABLE."""
    pred = Prediction(
        prediction_id="pred-rep-d",
        resource_address="aws_instance.app",
        metric="resource_identity",
        expected_value={"transition": "REPLACED", "prior_physical_id": "i-original"},
        verification_approach=VerificationApproach.IDENTITY_REPLACED,
        rationale="test",
        evidence_requirement=EvidenceRequirement(
            provider="aws", service="ec2", resource_type="instance", field="instance_id"
        ),
    )
    ev = Evidence(
        source="aws.ec2",
        resource_id="",
        field="instance_id",
        observed_value={},
        observed_at="2026-09-28T12:00:00Z",
    )
    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)
    assert res.status == VerificationStatus.NOT_OBSERVABLE


# ==============================================================================
# 4. TERRAFORM MODULE IDENTITY RESOLUTION
# ==============================================================================

def test_state_identity_resolver_handles_modules():
    """Verify StateIdentityResolver prefixes address with module path when present."""
    resolver = StateIdentityResolver()
    state_json = {
        "resources": [
            {
                "module": "module.vpc.subnets",
                "mode": "managed",
                "type": "aws_security_group",
                "name": "db_sg",
                "instances": [{"attributes": {"id": "sg-mod-123"}}],
            },
            {
                "mode": "managed",
                "type": "aws_instance",
                "name": "root_app",
                "instances": [{"attributes": {"id": "i-root-456"}}],
            },
        ]
    }
    identities = resolver.resolve_identities(state_json)

    assert "module.vpc.subnets.aws_security_group.db_sg" in identities
    assert identities["module.vpc.subnets.aws_security_group.db_sg"].resource_id == "sg-mod-123"

    assert "aws_instance.root_app" in identities
    assert identities["aws_instance.root_app"].resource_id == "i-root-456"
