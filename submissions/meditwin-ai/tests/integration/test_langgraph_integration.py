"""
Integration Tests: LangGraph State Machine & End-to-End Execution
Tests full execution paths for both Ingestion and Patient Intelligence pipelines.
"""

from unittest.mock import MagicMock
from graph.workflow import run_upload_workflow, run_question_workflow


def test_run_upload_workflow_end_to_end():
    """Verify upload pipeline traverses all nodes and enforces human review gate."""
    # Use real synthetic PDF
    pdf_path = "sample_data/synthetic_reports/SyntheticReport_A_Oct2026.pdf"
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    result = run_upload_workflow(
        file_name="SyntheticReport_A_Oct2026.pdf",
        file_bytes=pdf_bytes,
        patient_id=1,
    )

    assert result is not None
    assert "completed_nodes" in result
    nodes = result["completed_nodes"]

    # Verify all expected pipeline nodes were traversed
    assert "classify_request" in nodes
    assert "parse_document" in nodes
    assert "extract_observations" in nodes
    assert "validate_extraction" in nodes
    assert "human_review_gate" in nodes
    assert "persist_to_db2" in nodes
    assert "finalize_response" in nodes

    # Verify extraction succeeded and human review gate is mandatory
    assert len(result.get("extracted_observations", [])) == 9
    assert result.get("review_required") is True
    assert result.get("parse_status") == "PARSED"


def test_run_question_workflow_insufficient_evidence():
    """Verify question pipeline returns exact mandated fallback when DB has no records."""
    mock_repo = MagicMock()
    mock_repo.get_approved_observations.return_value = []
    mock_repo.get_distinct_test_codes.return_value = []

    result = run_question_workflow(
        question="How has my HbA1c changed over the last 6 months?",
        patient_id=1,
        repo=mock_repo,
    )

    assert result is not None
    nodes = result["completed_nodes"]
    assert "classify_request" in nodes
    assert "retrieve_evidence" in nodes
    assert "generate_answer" in nodes
    assert "safety_check" in nodes
    assert "finalize_response" in nodes

    answer = result.get("final_answer", "")
    assert "I could not find sufficient approved records to answer this question." in answer


def test_run_question_workflow_with_evidence():
    """Verify question pipeline synthesizes answer with provenance when evidence exists."""
    mock_repo = MagicMock()
    mock_repo.get_approved_observations.return_value = [
        {
            "observation_id": 101,
            "patient_id": 1,
            "test_code": "HBA1C",
            "test_name": "Hemoglobin A1c",
            "value_numeric": 7.2,
            "unit": "%",
            "reference_range": "< 5.7",
            "observed_at": "2026-10-14",
            "source_document_name": "SyntheticReport_A_Oct2026.pdf",
            "source_page": 1,
            "source_snippet": "Hemoglobin A1c (HbA1c): 7.2 % (Ref: < 5.7 %)",
            "review_status": "APPROVED",
        },
        {
            "observation_id": 102,
            "patient_id": 1,
            "test_code": "HBA1C",
            "test_name": "Hemoglobin A1c",
            "value_numeric": 6.8,
            "unit": "%",
            "reference_range": "< 5.7",
            "observed_at": "2026-11-18",
            "source_document_name": "SyntheticReport_B_Nov2026.pdf",
            "source_page": 1,
            "source_snippet": "Hemoglobin A1c (HbA1c): 6.8 % (Ref: < 5.7 %)",
            "review_status": "APPROVED",
        },
    ]

    result = run_question_workflow(
        question="What was my HbA1c in November?",
        patient_id=1,
        repo=mock_repo,
    )

    assert result is not None
    assert result.get("sufficient_evidence") is True
    answer = result.get("final_answer", "")
    assert "6.8" in answer or "HBA1C" in answer.upper()
    assert len(result.get("evidence_cards", [])) > 0
    # Provenance preserved
    assert any("SyntheticReport" in card.get("source_file", "") or "SyntheticReport" in card.get("source_document", "") for card in result["evidence_cards"])
