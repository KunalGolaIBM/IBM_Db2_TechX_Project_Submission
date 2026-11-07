"""Report generation tests."""

from __future__ import annotations

import json
from datetime import datetime

from app.services.report_generator import build_json_report, build_markdown_report


def session() -> dict:
    return {
        "session_id": 12,
        "submitted_text": "SolarCell-X achieved 92% efficiency.",
        "model_provider": "test/model",
        "status": "COMPLETED",
        "error_message": None,
        "created_at": datetime(2026, 1, 1, 12, 0),
        "completed_at": datetime(2026, 1, 1, 12, 0, 3),
        "duration_ms": 3000,
        "counts": {
            "total": 1,
            "supported": 1,
            "contradicted": 0,
            "insufficient_evidence": 0,
            "verification_error": 0,
        },
        "claims": [
            {
                "claim_id": 1,
                "original_claim": "SolarCell-X achieved 92% efficiency.",
                "normalized_claim": "SolarCell-X achieved 92% efficiency.",
                "claim_type": "NUMERICAL",
                "classification": "SUPPORTED",
                "explanation": "Passage 4 states 92%.",
                "limitations": "Controlled test conditions only.",
                "numerical_analysis": "Deterministic numeric check: 92% matches passage 4.",
                "human_review_status": "PENDING",
                "verification_method": "test",
                "evidence": [
                    {
                        "passage_id": 4,
                        "document_title": "Synthetic study",
                        "page_number": 1,
                        "relevance_score": 4.2,
                        "evidence_relationship": "SUPPORTS",
                        "passage_text": "SolarCell-X achieved 92% efficiency.",
                    }
                ],
            }
        ],
    }


def test_json_report_contains_metadata_and_claims():
    payload = json.loads(build_json_report(session()))
    assert payload["report_version"] == "1.0"
    assert payload["session"]["session_id"] == 12
    assert payload["session"]["claims"][0]["classification"] == "SUPPORTED"
    assert "not guarantees" in payload["disclaimer"]


def test_markdown_report_contains_tables_and_evidence():
    report = build_markdown_report(session())
    assert "# AEGIS verification report — session #12" in report
    assert "| 1 | 1 | 0 | 0 | 0 |" in report
    assert "Synthetic study, page 1, passage 4" in report
    assert "Deterministic numeric check" in report
    assert "Unresolved questions" in report
