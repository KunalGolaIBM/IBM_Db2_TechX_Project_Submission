"""
Test Category 9: Human Approval Test
Validates the human-in-the-loop verification gate and review decision structure.
"""

from ingestion.validation import ReviewDecision


def test_valid_approval_decision():
    """Verify approval decision passes validation with reviewer audit."""
    decision = ReviewDecision(
        observation_id=42,
        action="APPROVED",
        reviewed_by="DR_REVIEWER_1",
        reviewer_notes="Verified against report page 1"
    )
    assert decision.action == "APPROVED"
    assert decision.observation_id == 42
    assert decision.reviewed_by == "DR_REVIEWER_1"


def test_approval_with_value_correction():
    """Verify reviewer can correct numeric value and unit during approval."""
    decision = ReviewDecision(
        observation_id=42,
        action="APPROVED",
        corrected_value_numeric=6.5,
        corrected_unit="%",
        corrected_date="2026-10-15",
        reviewed_by="CLINICAL_VERIFIER"
    )
    assert decision.corrected_value_numeric == 6.5
    assert decision.corrected_unit == "%"
    assert decision.corrected_date == "2026-10-15"

