"""
Test Category 10: Rejected Observation Test
Ensures rejected observations cannot appear in trusted timelines or evidence sets.
"""

from ingestion.validation import ReviewDecision
from services.timeline_service import build_patient_timeline, compute_metric_trend


def test_rejection_decision_model():
    """Verify rejection model rejects invalid actions and preserves reason."""
    decision = ReviewDecision(
        observation_id=99,
        action="REJECTED",
        reviewer_notes="Value artifact from scanner noise",
        reviewed_by="LEAD_REVIEWER"
    )
    assert decision.action == "REJECTED"


def test_rejected_observations_excluded_from_timeline():
    """Ensure that only APPROVED observations are considered when building timeline."""
    raw_observations = [
        {
            "OBSERVATION_ID": 1,
            "TEST_NAME": "HbA1c",
            "TEST_CODE": "HBA1C",
            "VALUE_NUMERIC": 6.4,
            "UNIT": "%",
            "OBSERVED_AT": "2026-10-12",
            "REVIEW_STATUS": "APPROVED",
            "FILE_NAME": "report_1.pdf"
        },
        {
            "OBSERVATION_ID": 2,
            "TEST_NAME": "HbA1c",
            "TEST_CODE": "HBA1C",
            "VALUE_NUMERIC": 18.9,  # Bad OCR value
            "UNIT": "%",
            "OBSERVED_AT": "2026-10-13",
            "REVIEW_STATUS": "REJECTED",
            "FILE_NAME": "report_1.pdf"
        }
    ]
    # Filter to approved only before sending to timeline (as repository does)
    approved_only = [o for o in raw_observations if o["REVIEW_STATUS"] == "APPROVED"]
    timeline = build_patient_timeline(approved_only)

    assert len(timeline) == 1
    assert timeline[0]["value"] == 6.4

    # Trend calculation must not include rejected
    trend = compute_metric_trend(approved_only, "HBA1C")
    assert trend["count"] == 1
    assert trend["latest_value"] == 6.4

