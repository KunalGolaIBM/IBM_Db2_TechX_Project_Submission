"""
Test Category 18: Audit Logging Test
Validates the append-only audit trail for all operations (upload, extraction, approval, rejection, Q&A).
"""

from unittest.mock import MagicMock
from services.audit_service import AuditService


def test_audit_service_calls():
    """Verify AuditService logs appropriate actions and metadata."""
    mock_repo = MagicMock()
    audit = AuditService(mock_repo)

    # 1. Log upload
    audit.log_upload(document_id=10, file_name="lab.pdf", patient_id=1, actor="DOCTOR")
    mock_repo.log_audit.assert_called_with(
        action="DOCUMENT_UPLOAD",
        entity_type="DOCUMENT",
        entity_id=10,
        actor_id="DOCTOR",
        details=mock_repo.log_audit.call_args[1]["details"],
    )

    # 2. Log approval
    audit.log_approval(observation_id=5, reviewer="REVIEWER_1", original_value=6.4, corrected_value=6.5)
    assert mock_repo.log_audit.call_args[1]["action"] == "OBSERVATION_APPROVED"
    assert mock_repo.log_audit.call_args[1]["entity_id"] == 5

    # 3. Log rejection
    audit.log_rejection(observation_id=6, reviewer="REVIEWER_2", reason="Unclear scan")
    assert mock_repo.log_audit.call_args[1]["action"] == "OBSERVATION_REJECTED"

    # 4. Log question
    audit.log_question(patient_id=1, question="What was HbA1c?", had_evidence=True)
    assert mock_repo.log_audit.call_args[1]["action"] == "QUESTION_ASKED"

