"""Unit tests for CloudChange Domain Models."""

import pytest
from backend.app.models.change import ActionType, CanonicalChange
from backend.app.models.evidence import EvidenceRequirement
from backend.app.models.impact import ImpactCategory, ImpactFinding, Severity
from backend.app.models.prediction import Prediction, VerificationApproach
from backend.app.models.run import Run, RunStatus, build_run_summary
from backend.app.models.verification import VerificationResult, VerificationStatus


def test_canonical_change_instantiation():
    """Verify CanonicalChange instantiation and field constraints."""
    change = CanonicalChange(
        resource_address="aws_instance.api",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        before={"instance_type": "t3.medium"},
        after={"instance_type": "t3.large"},
        requires_replacement=False,
    )
    assert change.action == ActionType.UPDATE
    assert change.resource_address == "aws_instance.api"
    assert change.requires_replacement is False


def test_impact_finding_model():
    """Verify ImpactFinding instantiation with allowed severities and categories."""
    finding = ImpactFinding(
        rule_id="CC-EC2-COST-001",
        rule_version="1.0.0",
        resource_address="aws_instance.api",
        category=ImpactCategory.COST,
        severity=Severity.MEDIUM,
        title="EC2 instance type changed",
        explanation="Instance type changed from t3.medium to t3.large.",
    )
    assert finding.category == ImpactCategory.COST
    assert finding.severity == Severity.MEDIUM


def test_run_verified_status_validation():
    """A Run must not be VERIFIED if predictions remain unresolved or mismatched."""
    pred = Prediction(
        prediction_id="pred-1",
        metric="instance_type",
        expected_value="t3.large",
        verification_approach=VerificationApproach.EXACT_MATCH,
        rationale="Plan target",
        evidence_requirement=EvidenceRequirement(
            provider="aws",
            service="ec2",
            resource_type="instance",
            field="instance_type",
        ),
    )

    empty_summary = build_run_summary([], [], [], [], [])

    # Missing verification result while status=VERIFIED should raise ValueError
    with pytest.raises(ValueError, match="Run cannot be VERIFIED when predictions remain unresolved"):
        Run(
            run_id="run-1",
            created_at="2026-09-24T00:00:00Z",
            status=RunStatus.VERIFIED,
            summary=empty_summary,
            predictions=[pred],
            verification_results=[],
        )

    # Mismatched result while status=VERIFIED should raise ValueError
    mismatch_res = VerificationResult(
        prediction_id="pred-1",
        status=VerificationStatus.MISMATCH,
        expected_value="t3.large",
        observed_value="t3.medium",
        explanation="Values differed",
    )
    with pytest.raises(ValueError, match="Run cannot be VERIFIED when result pred-1 has status MISMATCH"):
        Run(
            run_id="run-1",
            created_at="2026-09-24T00:00:00Z",
            status=RunStatus.VERIFIED,
            summary=empty_summary,
            predictions=[pred],
            verification_results=[mismatch_res],
        )

    # Valid verified state
    verified_res = VerificationResult(
        prediction_id="pred-1",
        status=VerificationStatus.VERIFIED,
        expected_value="t3.large",
        observed_value="t3.large",
        explanation="Values matched",
    )
    run = Run(
        run_id="run-1",
        created_at="2026-09-24T00:00:00Z",
        status=RunStatus.VERIFIED,
        summary=empty_summary,
        predictions=[pred],
        verification_results=[verified_res],
    )
    assert run.status == RunStatus.VERIFIED


def test_prediction_evidence_requirement_invariant():
    """Verify the Phase 1 invariant: Prediction must declare evidence_requirement; None/omitted is rejected."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Prediction(
            prediction_id="pred-missing-evidence",
            metric="instance_type",
            expected_value="t3.large",
            verification_approach=VerificationApproach.EXACT_MATCH,
            rationale="Test invariant",
            # evidence_requirement intentionally omitted
        )

