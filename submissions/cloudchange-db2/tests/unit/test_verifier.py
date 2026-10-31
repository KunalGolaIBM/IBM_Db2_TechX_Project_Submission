"""Unit tests for the Verification Engine (Phase F3)."""

from backend.app.aws.errors import (
    AWSAuthorizationError,
    AWSServiceError,
    ResourceNotFoundError,
)
from backend.app.engine.verifier import Verifier
from backend.app.models.evidence import Evidence, EvidenceRequirement
from backend.app.models.prediction import Prediction, VerificationApproach
from backend.app.models.verification import VerificationStatus


def _make_prediction(
    prediction_id: str,
    metric: str,
    expected_value: any,
    approach: VerificationApproach,
    resource_address: str = "aws_instance.api",
) -> Prediction:
    return Prediction(
        prediction_id=prediction_id,
        resource_address=resource_address,
        metric=metric,
        expected_value=expected_value,
        verification_approach=approach,
        rationale="Test prediction",
        evidence_requirement=EvidenceRequirement(
            provider="aws",
            service="ec2",
            resource_type="instance",
            field=metric,
        ),
    )


def _make_evidence(
    resource_id: str,
    field: str,
    observed_value: any,
    source: str = "aws.ec2",
) -> Evidence:
    return Evidence(
        source=source,
        resource_id=resource_id,
        field=field,
        observed_value=observed_value,
        observed_at="2026-09-27T11:00:00Z",
    )


# ==========================================
# 1. EXACT_MATCH Tests
# ==========================================

def test_exact_match_verified():
    """Verify exact scalar match results in VERIFIED."""
    pred = _make_prediction("pred-1", "instance_type", "t3.large", VerificationApproach.EXACT_MATCH)
    ev = _make_evidence("i-12345", "instance_type", "t3.large")

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)

    assert res.status == VerificationStatus.VERIFIED
    assert res.prediction_id == "pred-1"
    assert res.expected_value == "t3.large"
    assert res.observed_value == "t3.large"
    assert "exactly matches" in res.explanation
    assert res.evidence_reference == {"source": "aws.ec2", "resource_id": "i-12345"}


def test_exact_match_mismatch():
    """Verify differing scalar results in MISMATCH."""
    pred = _make_prediction("pred-2", "instance_type", "t3.large", VerificationApproach.EXACT_MATCH)
    ev = _make_evidence("i-12345", "instance_type", "t3.small")

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)

    assert res.status == VerificationStatus.MISMATCH
    assert res.expected_value == "t3.large"
    assert res.observed_value == "t3.small"
    assert "Mismatch" in res.explanation


def test_exact_match_null_observed():
    """Verify null/missing observed value produces NOT_OBSERVABLE."""
    pred = _make_prediction("pred-3", "instance_type", "t3.large", VerificationApproach.EXACT_MATCH)
    ev = _make_evidence("i-12345", "instance_type", None)

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)

    assert res.status == VerificationStatus.NOT_OBSERVABLE
    assert res.observed_value is None


# ==========================================
# 2. CONFIG_MATCH Tests
# ==========================================

def test_config_match_verified():
    """Verify complete matching configuration results in VERIFIED."""
    pred = _make_prediction(
        "pred-cfg-1",
        "operational_config",
        {"ebs_optimized": True, "monitoring": "enabled"},
        VerificationApproach.CONFIG_MATCH,
    )
    ev = _make_evidence(
        "i-12345",
        "operational_config",
        {"ebs_optimized": True, "monitoring": "enabled", "source_dest_check": True},
    )

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)

    assert res.status == VerificationStatus.VERIFIED
    assert "All 2 expected configuration attributes match" in res.explanation


def test_config_match_attribute_mismatch():
    """Verify contradictory configuration attribute results in MISMATCH."""
    pred = _make_prediction(
        "pred-cfg-2",
        "operational_config",
        {"ebs_optimized": True},
        VerificationApproach.CONFIG_MATCH,
    )
    ev = _make_evidence(
        "i-12345",
        "operational_config",
        {"ebs_optimized": False, "monitoring": "enabled"},
    )

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)

    assert res.status == VerificationStatus.MISMATCH
    assert "Configuration attribute 'ebs_optimized' mismatch" in res.explanation


def test_config_match_missing_attribute_in_observed():
    """Verify missing expected attribute from observed evidence produces NOT_OBSERVABLE."""
    pred = _make_prediction(
        "pred-cfg-3",
        "operational_config",
        {"ebs_optimized": True, "quantum_encrypted": True},
        VerificationApproach.CONFIG_MATCH,
    )
    ev = _make_evidence(
        "i-12345",
        "operational_config",
        {"ebs_optimized": True},
    )

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)

    assert res.status == VerificationStatus.NOT_OBSERVABLE
    assert "Required configuration attribute 'quantum_encrypted' is missing" in res.explanation


def test_config_match_non_dict_observed():
    """Verify non-dictionary observed value produces NOT_OBSERVABLE."""
    pred = _make_prediction(
        "pred-cfg-4",
        "operational_config",
        {"ebs_optimized": True},
        VerificationApproach.CONFIG_MATCH,
    )
    ev = _make_evidence("i-12345", "operational_config", "not-a-dict")

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)

    assert res.status == VerificationStatus.NOT_OBSERVABLE


# ==========================================
# 3. SET_CONTAINS Tests
# ==========================================

def test_set_contains_verified_exact_item():
    """Verify expected element contained in observed list results in VERIFIED."""
    expected = [
        {"protocol": "tcp", "from_port": 80, "to_port": 80, "cidr": "0.0.0.0/0"},
        {"protocol": "tcp", "from_port": 443, "to_port": 443, "cidr": "0.0.0.0/0"},
    ]
    observed = [
        {"protocol": "tcp", "from_port": 22, "to_port": 22, "cidr": "10.0.0.0/8"},
        {"protocol": "tcp", "from_port": 80, "to_port": 80, "cidr": "0.0.0.0/0"},
        {"protocol": "tcp", "from_port": 443, "to_port": 443, "cidr": "0.0.0.0/0"},
    ]
    pred = _make_prediction("pred-set-1", "ingress", expected, VerificationApproach.SET_CONTAINS)
    ev = _make_evidence("sg-12345", "ingress", observed, source="aws.ec2.security_group")

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)

    assert res.status == VerificationStatus.VERIFIED
    assert "All 2 expected elements are contained" in res.explanation


def test_set_contains_sensitive_port_encompassing_range():
    """Verify sensitive port matching against broader port range or -1 protocol."""
    expected = [
        {"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0"}
    ]
    # Observed covers port 22 via range 20-25
    observed = [
        {"protocol": "tcp", "from_port": 20, "to_port": 25, "cidr": "0.0.0.0/0"}
    ]
    pred = _make_prediction("pred-sens-1", "sensitive_port", expected, VerificationApproach.SET_CONTAINS)
    ev = _make_evidence("sg-12345", "sensitive_port", observed, source="aws.ec2.security_group")

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)

    assert res.status == VerificationStatus.VERIFIED


def test_set_contains_absent_item_mismatch():
    """Verify missing expected element results in MISMATCH."""
    expected = [
        {"protocol": "tcp", "from_port": 22, "to_port": 22, "cidr": "0.0.0.0/0"}
    ]
    observed = [
        {"protocol": "tcp", "from_port": 80, "to_port": 80, "cidr": "0.0.0.0/0"}
    ]
    pred = _make_prediction("pred-set-2", "ingress", expected, VerificationApproach.SET_CONTAINS)
    ev = _make_evidence("sg-12345", "ingress", observed, source="aws.ec2.security_group")

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)

    assert res.status == VerificationStatus.MISMATCH
    assert "was not found in observed collection" in res.explanation


def test_set_contains_non_list_observed():
    """Verify non-list observed value produces NOT_OBSERVABLE."""
    pred = _make_prediction("pred-set-3", "ingress", [{"port": 80}], VerificationApproach.SET_CONTAINS)
    ev = _make_evidence("sg-12345", "ingress", "string-not-list")

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)

    assert res.status == VerificationStatus.NOT_OBSERVABLE


# ==========================================
# 4. IDENTITY_REPLACED Tests
# ==========================================

def test_identity_replaced_verified():
    """Verify physical resource ID difference confirms replacement."""
    pred = _make_prediction(
        "pred-id-1",
        "resource_identity",
        {"transition": "REPLACED", "prior_physical_id": "i-11111"},
        VerificationApproach.IDENTITY_REPLACED,
    )
    ev = _make_evidence(
        "i-22222",
        "resource_identity",
        {"instance_id": "i-22222", "state": "running"},
    )

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)

    assert res.status == VerificationStatus.VERIFIED
    assert "Physical resource identity changed from 'i-11111' to 'i-22222'" in res.explanation


def test_identity_replaced_mismatch_same_id():
    """Verify identical physical ID results in MISMATCH (not replaced)."""
    pred = _make_prediction(
        "pred-id-2",
        "resource_identity",
        {"transition": "REPLACED", "prior_physical_id": "i-11111"},
        VerificationApproach.IDENTITY_REPLACED,
    )
    ev = _make_evidence(
        "i-11111",
        "resource_identity",
        {"instance_id": "i-11111", "state": "running"},
    )

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)

    assert res.status == VerificationStatus.MISMATCH
    assert "matches prior identity 'i-11111' (resource was not replaced)" in res.explanation


def test_identity_replaced_unresolved_prior_id_not_observable():
    """Verify missing/unresolved prior ID produces NOT_OBSERVABLE."""
    pred = _make_prediction(
        "pred-id-3",
        "resource_identity",
        {"transition": "REPLACED", "prior_physical_id": None},
        VerificationApproach.IDENTITY_REPLACED,
    )
    ev = _make_evidence(
        "i-22222",
        "resource_identity",
        {"instance_id": "i-22222"},
    )

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)

    assert res.status == VerificationStatus.NOT_OBSERVABLE
    assert "Prior physical resource identity is unresolved or missing" in res.explanation


# ==========================================
# 5. RESOURCE_DELETED Tests
# ==========================================

def test_resource_deleted_verified_on_not_found_error():
    """Verify ResourceNotFoundError confirms deletion -> VERIFIED."""
    pred = _make_prediction(
        "pred-del-1",
        "instance_deletion",
        "DELETED",
        VerificationApproach.RESOURCE_DELETED,
        resource_address="aws_db_instance.db_temp",
    )
    err = ResourceNotFoundError(resource_id="db-temp", resource_type="RDS DB instance")

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=None, error=err)

    assert res.status == VerificationStatus.VERIFIED
    assert res.observed_value == "RESOURCE_NOT_FOUND"
    assert "confirmed deleted" in res.explanation


def test_resource_deleted_mismatch_if_resource_still_exists():
    """Verify resource presence results in MISMATCH when deletion was expected."""
    pred = _make_prediction(
        "pred-del-2",
        "instance_deletion",
        "DELETED",
        VerificationApproach.RESOURCE_DELETED,
    )
    ev = _make_evidence("db-temp", "instance_deletion", "available", source="aws.rds")

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=ev)

    assert res.status == VerificationStatus.MISMATCH
    assert "still exists in AWS" in res.explanation


def test_resource_deleted_auth_error_not_observable():
    """Verify authorization failure is NOT treated as confirmed deletion."""
    pred = _make_prediction(
        "pred-del-3",
        "instance_deletion",
        "DELETED",
        VerificationApproach.RESOURCE_DELETED,
    )
    err = AWSAuthorizationError("Access denied to RDS")

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=None, error=err)

    assert res.status == VerificationStatus.NOT_OBSERVABLE
    assert "AWS observation failed" in res.explanation


def test_resource_deleted_service_error_not_observable():
    """Verify service/throttling error is NOT treated as confirmed deletion."""
    pred = _make_prediction(
        "pred-del-4",
        "instance_deletion",
        "DELETED",
        VerificationApproach.RESOURCE_DELETED,
    )
    err = AWSServiceError("ThrottlingException")

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=None, error=err)

    assert res.status == VerificationStatus.NOT_OBSERVABLE


# ==========================================
# 6. General / Edge Cases & Batch Execution
# ==========================================

def test_missing_evidence_and_no_error_produces_not_observable():
    """Verify missing evidence returns NOT_OBSERVABLE."""
    pred = _make_prediction("pred-none", "instance_type", "t3.large", VerificationApproach.EXACT_MATCH)

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=None, error=None)

    assert res.status == VerificationStatus.NOT_OBSERVABLE
    assert "Evidence could not be retrieved" in res.explanation


def test_resource_not_found_on_exact_match_produces_mismatch():
    """Verify ResourceNotFoundError on an expectation of existence results in MISMATCH."""
    pred = _make_prediction("pred-exist", "instance_type", "t3.large", VerificationApproach.EXACT_MATCH)
    err = ResourceNotFoundError(resource_id="i-missing", resource_type="EC2 instance")

    verifier = Verifier()
    res = verifier.verify_prediction(pred, evidence=None, error=err)

    assert res.status == VerificationStatus.MISMATCH
    assert "was not found in AWS, but was expected to exist" in res.explanation


def test_verify_all_batch_execution():
    """Verify verify_all evaluates multiple predictions against evidence and error maps."""
    pred1 = _make_prediction("pred-1", "instance_type", "t3.large", VerificationApproach.EXACT_MATCH)
    pred2 = _make_prediction("pred-2", "instance_type", "t3.large", VerificationApproach.EXACT_MATCH)
    pred3 = _make_prediction("pred-3", "instance_deletion", "DELETED", VerificationApproach.RESOURCE_DELETED)

    ev1 = _make_evidence("i-1", "instance_type", "t3.large")
    ev2 = _make_evidence("i-2", "instance_type", "t3.micro")
    err3 = ResourceNotFoundError(resource_id="db-3", resource_type="RDS DB instance")

    verifier = Verifier()
    results = verifier.verify_all(
        predictions=[pred1, pred2, pred3],
        evidence_map={"pred-1": ev1, "pred-2": ev2},
        error_map={"pred-3": err3},
    )

    assert len(results) == 3
    assert results[0].status == VerificationStatus.VERIFIED
    assert results[1].status == VerificationStatus.MISMATCH
    assert results[2].status == VerificationStatus.VERIFIED


def test_verification_determinism():
    """Verify verification produces identical results on repeated execution."""
    pred = _make_prediction("pred-det", "instance_type", "t3.large", VerificationApproach.EXACT_MATCH)
    ev = _make_evidence("i-12345", "instance_type", "t3.large")

    verifier = Verifier()
    res1 = verifier.verify_prediction(pred, evidence=ev)
    res2 = verifier.verify_prediction(pred, evidence=ev)

    assert res1.status == res2.status
    assert res1.expected_value == res2.expected_value
    assert res1.observed_value == res2.observed_value
    assert res1.explanation == res2.explanation
