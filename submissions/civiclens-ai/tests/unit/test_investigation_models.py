import pytest
from pydantic import ValidationError

from civiclens.domain.investigation_models import DecisionRequest, EvidenceCreate, RecommendationDraft

GOOD = dict(summary="Inspect cluster", rationale="Evidence shows a cluster.", priority=2, confidence=0.7,
            evidence_ids=[3, 1, 3])  # fmt: skip


def test_draft_normalises_evidence_ids():
    assert RecommendationDraft(**GOOD).evidence_ids == [1, 3]


@pytest.mark.parametrize(
    "override",
    [
        {"priority": 0}, {"priority": 6}, {"confidence": 1.5}, {"evidence_ids": []},
        {"evidence_ids": [0]}, {"evidence_ids": [-4]}, {"evidence_ids": [True]},
        {"evidence_ids": list(range(1, 60))}, {"status": "APPROVED"}, {"summary": "x"},
    ],
)  # fmt: skip
def test_draft_rejects_invalid_values_and_status_injection(override):
    with pytest.raises(ValidationError):
        RecommendationDraft(**{**GOOD, **override})


def test_decision_request_rules():
    assert DecisionRequest(decision="APPROVED").comment is None
    assert DecisionRequest(decision="REJECTED", comment="Not enough evidence").decision == "REJECTED"
    for bad in (
        {"decision": "REJECTED"},
        {"decision": "REJECTED", "comment": "no"},
        {"decision": "NEEDS_INFO"},
    ):
        with pytest.raises(ValidationError):
            DecisionRequest(**bad)


def test_evidence_create_validation():
    assert EvidenceCreate(complaint_ids=[5, 2, 5]).complaint_ids == [2, 5]
    for bad in ([], [0], list(range(1, 60))):
        with pytest.raises(ValidationError):
            EvidenceCreate(complaint_ids=bad)
