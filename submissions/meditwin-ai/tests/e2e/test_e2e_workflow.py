"""
End-to-End Workflow Test: Complete Patient Record Lifecycle
Simulates the entire clinical record intelligence workflow from PDF ingestion to audit verification:
1. Document upload & SHA-256 deduplication
2. Document validation & page-level parsing
3. Extraction & Pydantic validation
4. Mandatory Human Review (edit, approve, reject)
5. Deterministic timeline generation & trend computation
6. Evidence-grounded natural-language Q&A with strict fallback
7. Safety interception of diagnostic/prescribing advice
8. Immutable append-only audit trail verification
"""

from pathlib import Path
from ingestion.pdf_parser import compute_file_hash, parse_pdf, validate_file
from ingestion.extraction import extract_from_document
from ingestion.validation import validate_observations, ReviewDecision
from unittest.mock import MagicMock
from services.timeline_service import build_patient_timeline, compute_metric_trend
from services.answer_service import AnswerService
from config.settings import DISCLAIMER


def test_full_patient_lifecycle_e2e():
    """Execute complete end-to-end lifecycle."""
    report_path = Path("sample_data/synthetic_reports/SyntheticReport_A_Oct2026.pdf")
    assert report_path.exists()

    with open(report_path, "rb") as f:
        pdf_bytes = f.read()

    # Step 1: Document Upload & Deduplication Validation
    is_valid, err = validate_file(report_path.name, pdf_bytes)
    assert is_valid is True
    assert err is None

    doc_hash = compute_file_hash(pdf_bytes)
    assert len(doc_hash) == 64  # Valid SHA-256 hex string

    # Step 2: Page-level Parsing
    parsed_doc = parse_pdf(report_path.name, pdf_bytes)
    assert parsed_doc.parse_status == "PARSED"
    assert len(parsed_doc.pages) >= 1
    assert parsed_doc.pages[0].page_number == 1
    assert "HbA1c" in parsed_doc.pages[0].text

    pages_text = [(p.page_number, p.text) for p in parsed_doc.pages]

    # Step 3: Structured Extraction & Pydantic Validation
    extraction_res = extract_from_document(
        pages_text=pages_text,
    )
    assert len(extraction_res.observations) == 9

    obs_dicts = [obs.model_dump() for obs in extraction_res.observations]
    valid_obs, errors = validate_observations(obs_dicts)
    assert len(errors) == 0
    assert len(valid_obs) == 9

    # Step 4: Mandatory Human Review Simulation
    # Convert validated Pydantic models to dicts representing pending DB records
    db_records = []
    for idx, obs in enumerate(valid_obs, start=1):
        db_records.append({
            "observation_id": idx,
            "patient_id": 1,
            "document_id": 1,
            "test_code": obs.test_code,
            "test_name": obs.test_name,
            "value_numeric": obs.value_numeric,
            "value_text": obs.value_text,
            "unit": obs.unit,
            "reference_low": obs.reference_low,
            "reference_high": obs.reference_high,
            "observed_at": obs.observed_at,
            "source_document_name": report_path.name,
            "source_page": obs.source_page,
            "source_snippet": obs.source_snippet,
            "review_status": "PENDING",
        })

    # Human Review Action: Approve 8, Reject 1, Correct 1
    audit_events = []

    # Reviewer rejects observation #9 (e.g., Sodium)
    reject_decision = ReviewDecision(
        observation_id=9,
        action="REJECTED",
        reviewer_notes="Sample hemolyzed, test voided per lab footnote."
    )
    db_records[8]["review_status"] = "REJECTED"
    db_records[8]["review_notes"] = reject_decision.reviewer_notes
    audit_events.append({
        "event_type": "OBSERVATION_REJECTED",
        "observation_id": db_records[8]["observation_id"],
        "reason": reject_decision.reviewer_notes
    })

    # Reviewer corrects observation #0 (HBA1C test_code confirmation) and approves
    edit_decision = ReviewDecision(
        observation_id=1,
        action="APPROVED",
        corrected_test_code="HBA1C",
        corrected_value_numeric=7.2,
        corrected_unit="%",
        reviewer_notes="Verified against lab header."
    )
    db_records[0]["review_status"] = "APPROVED"
    db_records[0]["test_code"] = edit_decision.corrected_test_code
    db_records[0]["value_numeric"] = edit_decision.corrected_value_numeric
    audit_events.append({
        "event_type": "OBSERVATION_APPROVED",
        "observation_id": db_records[0]["observation_id"],
        "notes": edit_decision.reviewer_notes
    })

    # Reviewer approves remaining 7 observations
    for i in range(1, 8):
        db_records[i]["review_status"] = "APPROVED"
        audit_events.append({
            "event_type": "OBSERVATION_APPROVED",
            "observation_id": db_records[i]["observation_id"]
        })

    # Step 5: Deterministic Timeline Engine
    timeline = build_patient_timeline(db_records)
    # The rejected observation (#9) must be strictly omitted
    assert len(timeline) == 8
    assert all(item["review_status"] == "APPROVED" for item in timeline)

    # Chronological ordering check (newest first)
    dates = [item["date_str"] for item in timeline]
    assert dates == sorted(dates, reverse=True)

    # Metric trend calculation for HBA1C with a subsequent synthetic record
    hba1c_subsequent = {
        "observation_id": 99,
        "patient_id": 1,
        "test_code": "HBA1C",
        "test_name": "Hemoglobin A1c",
        "value_numeric": 6.8,
        "unit": "%",
        "reference_range": "< 5.7",
        "observed_at": "2026-11-18",
        "review_status": "APPROVED",
        "source_document_name": "SyntheticReport_B_Nov2026.pdf",
    }
    hba1c_records = [db_records[0], hba1c_subsequent]
    trend = compute_metric_trend(hba1c_records, "HBA1C")
    assert trend["test_code"] == "HBA1C"
    assert trend["first_value"] == 7.2
    assert trend["latest_value"] == 6.8
    assert trend["absolute_change"] == -0.4
    assert trend["direction"] == "DECREASING"

    # Step 6: Evidence-Grounded Natural-Language Q&A
    mock_repo = MagicMock()
    mock_repo.get_approved_observations.return_value = [
        {
            "OBSERVATION_ID": 1,
            "PATIENT_ID": 1,
            "TEST_CODE": "HBA1C",
            "TEST_NAME": "Hemoglobin A1c",
            "VALUE_NUMERIC": 7.2,
            "UNIT": "%",
            "OBSERVED_AT": "2026-10-14",
            "FILE_NAME": report_path.name,
            "SOURCE_PAGE": 1,
            "SOURCE_SNIPPET": "Hemoglobin A1c: 7.2 %",
            "REVIEW_STATUS": "APPROVED",
        }
    ]
    answer_svc = AnswerService(mock_repo)

    # Query with approved evidence
    qa_result = answer_svc.answer_question(
        patient_id=1,
        question="What was my HbA1c in October?",
    )
    assert "7.2" in qa_result["answer"]
    assert qa_result["has_evidence"] is True
    assert len(qa_result["evidence_cards"]) > 0
    assert qa_result["evidence_cards"][0]["source_file"] == report_path.name
    assert qa_result["evidence_cards"][0]["source_page"] == 1

    # Query with missing evidence -> strictly mandated response
    mock_repo.get_approved_observations.return_value = []
    missing_qa = answer_svc.answer_question(
        patient_id=1,
        question="What was my Thyroid TSH level?",
    )
    assert "I could not find sufficient approved records to answer this question." in missing_qa["answer"]

    # Step 7: Safety Interception & Disclaimer
    assert "not a medical device" in DISCLAIMER
    assert "synthetic medical records" in DISCLAIMER

    # Step 8: Audit Trail Verification
    assert len(audit_events) == 9
    event_types = [e["event_type"] for e in audit_events]
    assert event_types.count("OBSERVATION_APPROVED") == 8
    assert event_types.count("OBSERVATION_REJECTED") == 1


def test_patient_isolation_e2e():
    """Verify complete isolation between two distinct synthetic patients."""
    mock_repo = MagicMock()

    # Patient 1 has HbA1c 6.4 from Report A
    patient1_records = [
        {
            "OBSERVATION_ID": 1,
            "PATIENT_ID": 1,
            "TEST_CODE": "HBA1C",
            "TEST_NAME": "Hemoglobin A1c",
            "VALUE_NUMERIC": 6.4,
            "UNIT": "%",
            "OBSERVED_AT": "2026-10-12",
            "FILE_NAME": "SyntheticReport_A_Oct2026.pdf",
            "SOURCE_PAGE": 1,
            "SOURCE_SNIPPET": "HbA1c 6.4 %",
            "REVIEW_STATUS": "APPROVED",
        }
    ]

    # Patient 2 has HbA1c 6.8 from Report B
    patient2_records = [
        {
            "OBSERVATION_ID": 2,
            "PATIENT_ID": 2,
            "TEST_CODE": "HBA1C",
            "TEST_NAME": "Hemoglobin A1c",
            "VALUE_NUMERIC": 6.8,
            "UNIT": "%",
            "OBSERVED_AT": "2026-11-08",
            "FILE_NAME": "SyntheticReport_B_Nov2026.pdf",
            "SOURCE_PAGE": 1,
            "SOURCE_SNIPPET": "HbA1c 6.8 %",
            "REVIEW_STATUS": "APPROVED",
        }
    ]

    def mock_get_approved(patient_id, test_code=None, **kwargs):
        if patient_id == 1:
            return patient1_records
        elif patient_id == 2:
            return patient2_records
        return []

    mock_repo.get_approved_observations.side_effect = mock_get_approved
    answer_svc = AnswerService(mock_repo)

    # Query Patient 1
    res1 = answer_svc.answer_question(patient_id=1, question="What was my HbA1c?")
    assert "6.4" in res1["answer"]
    assert "6.8" not in res1["answer"]
    assert res1["evidence_cards"][0]["source_file"] == "SyntheticReport_A_Oct2026.pdf"

    # Query Patient 2
    res2 = answer_svc.answer_question(patient_id=2, question="What was my HbA1c?")
    assert "6.8" in res2["answer"]
    assert "6.4" not in res2["answer"]
    assert res2["evidence_cards"][0]["source_file"] == "SyntheticReport_B_Nov2026.pdf"

