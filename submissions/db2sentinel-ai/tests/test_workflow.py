import pytest
from src.workflows.security_workflow import execute_incident_investigation

def test_langgraph_investigation_workflow():
    """Validates the stateful LangGraph multi-agent execution."""
    sample_events = [
        {
            "event_id": 101,
            "event_type": "AUTHENTICATION",
            "username": "REPORT_USER",
            "source_ip": "198.51.100.44",
            "status": "FAILURE",
            "event_timestamp": "2026-11-10 02:14:00",
            "raw_details": "{\"note\": \"off-hours login\"}"
        },
        {
            "event_id": 102,
            "event_type": "SENSITIVE_ACCESS",
            "username": "REPORT_USER",
            "source_ip": "198.51.100.44",
            "object_name": "CUSTOMER_FINANCIAL_RECORDS",
            "status": "SUCCESS",
            "event_timestamp": "2026-11-10 02:16:00",
            "raw_details": "{\"rows_read\": 28400}"
        }
    ]
    sample_alerts = [
        {
            "alert_name": "Sensitive Table Access",
            "severity": "CRITICAL",
            "risk_score": 85.0
        }
    ]

    final_state = execute_incident_investigation(
        incident_id="INC-TEST-001",
        target_username="REPORT_USER",
        target_ip="198.51.100.44",
        events=sample_events,
        alerts=sample_alerts
    )

    assert final_state["incident_id"] == "INC-TEST-001"
    assert len(final_state["evidence_dossier"]) == 2
    assert len(final_state["attack_hypotheses"]) > 0
    assert final_state["human_approval_required"] is True
    assert len(final_state["recommended_actions"]) > 0
    assert len(final_state["investigation_reports"]) > 0
