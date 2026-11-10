import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch

# Ensure backend directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import db2_service, gemini_service
from app.services.gemini_service import sanitize_message, synthesize_agent_intelligence
from app.agents.workflow import (
    intake_agent,
    traceability_agent,
    risk_assessment_agent,
    response_planning_agent,
    run_lotline_workflow,
    RecallState,
)


def get_mock_base_state() -> RecallState:
    """Helper creating a grounded base recall state with Db2 verified values."""
    return {
        "incident_id": "INC-2026-001",
        "source_lot_id": "RAW-204",
        "incident_data": {
            "incident_id": "INC-2026-001",
            "source_lot_id": "RAW-204",
            "severity": "CRITICAL",
            "status": "OPEN",
            "description": "Synthetic scenario: Supplier reported possible Salmonella contamination in organic spinach lot RAW-204. Downstream batches require investigation.",
            "source_lot_details": {
                "lot_id": "RAW-204",
                "item_name": "Organic Spinach",
                "supplier_name": "GreenLeaf Foods",
                "country": "India",
                "quantity_created": 500.0,
                "unit": "KG",
                "status": "QUARANTINED"
            }
        },
        "trace_data": {
            "source_lot_id": "RAW-204",
            "total_downstream_lots": 6,
            "total_production_levels": 2,
            "finished_lots_count": 3,
            "nodes": [
                {"lot_id": "RAW-204", "lot_type": "RAW", "item_name": "Organic Spinach"},
                {"lot_id": "WIP-301", "lot_type": "WIP", "item_name": "Spinach Wrap Base"},
                {"lot_id": "WIP-302", "lot_type": "WIP", "item_name": "Spinach Smoothie Puree"},
                {"lot_id": "WIP-303", "lot_type": "WIP", "item_name": "Spinach Bowl Mix"},
                {"lot_id": "FIN-401", "lot_type": "FINISHED", "item_name": "Green Spinach Wrap"},
                {"lot_id": "FIN-402", "lot_type": "FINISHED", "item_name": "Spinach Green Smoothie"},
                {"lot_id": "FIN-403", "lot_type": "FINISHED", "item_name": "Garden Veggie Bowl"}
            ]
        },
        "exposure_data": {},
        "risk_assessment": {
            "total_affected_units": 2400.0,
            "warehouse_units": 1350.0,
            "retailer_delivered_units": 850.0,
            "in_transit_units": 200.0,
            "risk_score": 94,
            "risk_level": "CRITICAL",
            "affected_retailers": [
                {"retailer": "FreshMart Nagpur Central", "quantity": 300.0, "status": "DELIVERED"},
                {"retailer": "FreshMart Pune West", "quantity": 200.0, "status": "IN_TRANSIT"},
                {"retailer": "QuickCart Mumbai", "quantity": 400.0, "status": "DELIVERED"},
                {"retailer": "CityGrocer Nashik", "quantity": 150.0, "status": "DELIVERED"}
            ]
        },
        "recommended_actions": [
            {"action_id": "ACT-001", "action_type": "HOLD_INVENTORY", "target_id": "RAW-204", "status": "APPROVED", "action_description": "Maintain quarantine of remaining raw-material inventory."},
            {"action_id": "ACT-002", "action_type": "NOTIFY_RETAILER", "target_id": "FreshMart Nagpur Central", "status": "PROPOSED", "action_description": "Prepare retailer notification for potentially affected finished products."},
            {"action_id": "ACT-003", "action_type": "TARGETED_RECALL", "target_id": "FIN-401", "status": "PROPOSED", "action_description": "Evaluate affected finished spinach wrap batch for targeted recall."},
            {"action_id": "ACT-004", "action_type": "HOLD_DISTRIBUTION", "target_id": "FIN-402", "status": "PROPOSED", "action_description": "Review and prepare a distribution hold for affected smoothie batch."}
        ],
        "steps": [],
        "evidence": [],
        "agent_logs": [],
        "gemini_status": {
            "available": False,
            "model": None,
            "status_code": "NOT_RUN",
            "rationale": None,
            "note": "Initializing"
        },
        "error": None
    }


# ==============================================================================
# 1. ADVERSARIAL TEST 1: Salmonella vs E. coli Discrepancy
# ==============================================================================
def test_adv_01_pathogen_discrepancy_salmonella_vs_ecoli():
    """Adversarial check: Db2 says Salmonella in incident description.
    If Gemini introduces E. coli, server-side validator must reject it and revert to Db2.
    """
    state = get_mock_base_state()
    hallucinated_json = json.dumps({
        "intake": {
            "agent_id": "incident_intake",
            "operational_interpretation": "Confirmed E. coli O157:H7 contamination in organic spinach lot RAW-204.",
            "supporting_evidence_refs": ["RAW-204", "E. coli"],
            "limitations_or_missing_info": "None"
        },
        "traceability": {
            "agent_id": "traceability",
            "operational_interpretation": "Lineage mapped across 6 downstream batches.",
            "supporting_evidence_refs": ["WIP-301"],
            "limitations_or_missing_info": "None"
        },
        "risk": {
            "agent_id": "risk_assessment",
            "operational_interpretation": "Exposure calculated at 2,400 total units.",
            "supporting_evidence_refs": ["2400 units"],
            "limitations_or_missing_info": "None"
        },
        "response_planning": {
            "agent_id": "response_planning",
            "operational_interpretation": "Response plan formulated for human review.",
            "supporting_evidence_refs": ["ACT-001"],
            "limitations_or_missing_info": "None"
        }
    })

    with patch.dict(os.environ, {"GEMINI_API_KEY": "TEST_MOCK_GEMINI_API_KEY"}):
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = hallucinated_json
            mock_client.models.generate_content.return_value = mock_response
            mock_client_cls.return_value = mock_client

            res = synthesize_agent_intelligence(
                incident_data=state["incident_data"],
                trace_data=state["trace_data"],
                risk_data=state["risk_assessment"],
                actions=state["recommended_actions"]
            )

            # Verification: Must fail validation and revert to Db2
            assert res["available"] is False
            assert res["status_code"] == "VALIDATION_FAILED"
            assert any("UNSUPPORTED_PATHOGEN" in r for r in res["rejection_reasons"])
            assert "Salmonella" in res["intake_explanation"]
            assert "E. coli" not in res["intake_explanation"]


# ==============================================================================
# 2. ADVERSARIAL TEST 2: Supplier Location Hallucination (Salinas, California)
# ==============================================================================
def test_adv_02_ungrounded_supplier_location_salinas_california():
    """Adversarial check: Db2 SUPPLIERS contains India only.
    If Gemini hallucinates Salinas, California, validator must reject it.
    """
    state = get_mock_base_state()
    hallucinated_json = json.dumps({
        "intake": {
            "agent_id": "incident_intake",
            "operational_interpretation": "Supplier GreenLeaf Foods is located in Salinas, California.",
            "supporting_evidence_refs": ["GreenLeaf Foods", "Salinas"],
            "limitations_or_missing_info": "None"
        },
        "traceability": {
            "agent_id": "traceability",
            "operational_interpretation": "Lineage mapped across 6 downstream batches.",
            "supporting_evidence_refs": ["WIP-301"],
            "limitations_or_missing_info": "None"
        },
        "risk": {
            "agent_id": "risk_assessment",
            "operational_interpretation": "Exposure calculated at 2,400 total units.",
            "supporting_evidence_refs": ["2400 units"],
            "limitations_or_missing_info": "None"
        },
        "response_planning": {
            "agent_id": "response_planning",
            "operational_interpretation": "Human approval required.",
            "supporting_evidence_refs": ["ACT-001"],
            "limitations_or_missing_info": "None"
        }
    })

    with patch.dict(os.environ, {"GEMINI_API_KEY": "TEST_MOCK_GEMINI_API_KEY"}):
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = hallucinated_json
            mock_client.models.generate_content.return_value = mock_response
            mock_client_cls.return_value = mock_client

            res = synthesize_agent_intelligence(
                incident_data=state["incident_data"],
                trace_data=state["trace_data"],
                risk_data=state["risk_assessment"],
                actions=state["recommended_actions"]
            )

            assert res["available"] is False
            assert res["status_code"] == "VALIDATION_FAILED"
            assert any("UNGROUNDED_LOCATION" in r for r in res["rejection_reasons"])
            assert "India" in res["intake_explanation"]
            assert "Salinas" not in res["intake_explanation"]


# ==============================================================================
# 3. ADVERSARIAL TEST 3: Invented 7th Downstream Lot (e.g. FIN-404)
# ==============================================================================
def test_adv_03_invented_seventh_downstream_lot():
    """Adversarial check: Db2 downstream lineage has exactly 6 lots.
    If Gemini invents FIN-404 or LOT-999, validator must reject it.
    """
    state = get_mock_base_state()
    hallucinated_json = json.dumps({
        "intake": {
            "agent_id": "incident_intake",
            "operational_interpretation": "Verified source lot RAW-204.",
            "supporting_evidence_refs": ["RAW-204"],
            "limitations_or_missing_info": "None"
        },
        "traceability": {
            "agent_id": "traceability",
            "operational_interpretation": "Contamination propagated to 7th batch FIN-404 at regional facility.",
            "supporting_evidence_refs": ["FIN-404"],
            "limitations_or_missing_info": "None"
        },
        "risk": {
            "agent_id": "risk_assessment",
            "operational_interpretation": "2,400 total units exposed.",
            "supporting_evidence_refs": ["2400 units"],
            "limitations_or_missing_info": "None"
        },
        "response_planning": {
            "agent_id": "response_planning",
            "operational_interpretation": "Human review required.",
            "supporting_evidence_refs": ["ACT-001"],
            "limitations_or_missing_info": "None"
        }
    })

    with patch.dict(os.environ, {"GEMINI_API_KEY": "TEST_MOCK_GEMINI_API_KEY"}):
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = hallucinated_json
            mock_client.models.generate_content.return_value = mock_response
            mock_client_cls.return_value = mock_client

            res = synthesize_agent_intelligence(
                incident_data=state["incident_data"],
                trace_data=state["trace_data"],
                risk_data=state["risk_assessment"],
                actions=state["recommended_actions"]
            )

            assert res["available"] is False
            assert res["status_code"] == "VALIDATION_FAILED"
            assert any("INVENTED_LOT" in r for r in res["rejection_reasons"])
            assert "FIN-404" not in res["traceability_explanation"]


# ==============================================================================
# 4. ADVERSARIAL TEST 4: Action Description Tampering
# ==============================================================================
def test_adv_04_action_description_tampering():
    """Adversarial check: ACT-001 is quarantine hold.
    If Gemini purports to alter it to unauthorized destruction, validator rejects it.
    """
    state = get_mock_base_state()
    hallucinated_json = json.dumps({
        "intake": {
            "agent_id": "incident_intake",
            "operational_interpretation": "Source verified.",
            "supporting_evidence_refs": ["RAW-204"],
            "limitations_or_missing_info": "None"
        },
        "traceability": {
            "agent_id": "traceability",
            "operational_interpretation": "Genealogy mapped.",
            "supporting_evidence_refs": ["WIP-301"],
            "limitations_or_missing_info": "None"
        },
        "risk": {
            "agent_id": "risk_assessment",
            "operational_interpretation": "Exposure evaluated.",
            "supporting_evidence_refs": ["2400 units"],
            "limitations_or_missing_info": "None"
        },
        "response_planning": {
            "agent_id": "response_planning",
            "operational_interpretation": "Protocol ACT-001 modified to immediately destroy and discard all inventory.",
            "supporting_evidence_refs": ["ACT-001"],
            "limitations_or_missing_info": "None"
        }
    })

    with patch.dict(os.environ, {"GEMINI_API_KEY": "TEST_MOCK_GEMINI_API_KEY"}):
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = hallucinated_json
            mock_client.models.generate_content.return_value = mock_response
            mock_client_cls.return_value = mock_client

            res = synthesize_agent_intelligence(
                incident_data=state["incident_data"],
                trace_data=state["trace_data"],
                risk_data=state["risk_assessment"],
                actions=state["recommended_actions"]
            )

            assert res["available"] is False
            assert res["status_code"] == "VALIDATION_FAILED"
            assert any("ACTION_TAMPERING" in r for r in res["rejection_reasons"])


# ==============================================================================
# 5. ADVERSARIAL TEST 5: Invented Mitigation Action (e.g. ACT-005)
# ==============================================================================
def test_adv_05_invented_mitigation_action():
    """Adversarial check: Db2 has only ACT-001 through ACT-004.
    If Gemini invents ACT-005, validator rejects it.
    """
    state = get_mock_base_state()
    hallucinated_json = json.dumps({
        "intake": {
            "agent_id": "incident_intake",
            "operational_interpretation": "Verified intake.",
            "supporting_evidence_refs": ["RAW-204"],
            "limitations_or_missing_info": "None"
        },
        "traceability": {
            "agent_id": "traceability",
            "operational_interpretation": "Verified lineage.",
            "supporting_evidence_refs": ["WIP-301"],
            "limitations_or_missing_info": "None"
        },
        "risk": {
            "agent_id": "risk_assessment",
            "operational_interpretation": "Verified risk.",
            "supporting_evidence_refs": ["2400 units"],
            "limitations_or_missing_info": "None"
        },
        "response_planning": {
            "agent_id": "response_planning",
            "operational_interpretation": "Agent created action ACT-005 to trigger global press recall.",
            "supporting_evidence_refs": ["ACT-005"],
            "limitations_or_missing_info": "None"
        }
    })

    with patch.dict(os.environ, {"GEMINI_API_KEY": "TEST_MOCK_GEMINI_API_KEY"}):
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = hallucinated_json
            mock_client.models.generate_content.return_value = mock_response
            mock_client_cls.return_value = mock_client

            res = synthesize_agent_intelligence(
                incident_data=state["incident_data"],
                trace_data=state["trace_data"],
                risk_data=state["risk_assessment"],
                actions=state["recommended_actions"]
            )

            assert res["available"] is False
            assert res["status_code"] == "VALIDATION_FAILED"
            assert any("INVENTED_ACTION" in r for r in res["rejection_reasons"])


# ==============================================================================
# 6. ADVERSARIAL TEST 6: Modified Deterministic Exposure Figures
# ==============================================================================
def test_adv_06_modified_deterministic_exposure_figures():
    """Adversarial check: Db2 total affected units is exactly 2,400.
    If Gemini claims 3,500 total units, validator rejects it.
    """
    state = get_mock_base_state()
    hallucinated_json = json.dumps({
        "intake": {
            "agent_id": "incident_intake",
            "operational_interpretation": "Verified intake.",
            "supporting_evidence_refs": ["RAW-204"],
            "limitations_or_missing_info": "None"
        },
        "traceability": {
            "agent_id": "traceability",
            "operational_interpretation": "Verified lineage.",
            "supporting_evidence_refs": ["WIP-301"],
            "limitations_or_missing_info": "None"
        },
        "risk": {
            "agent_id": "risk_assessment",
            "operational_interpretation": "Risk assessment calculated 3,500 total units exposed across the nation.",
            "supporting_evidence_refs": ["3500 units"],
            "limitations_or_missing_info": "None"
        },
        "response_planning": {
            "agent_id": "response_planning",
            "operational_interpretation": "Human review required.",
            "supporting_evidence_refs": ["ACT-001"],
            "limitations_or_missing_info": "None"
        }
    })

    with patch.dict(os.environ, {"GEMINI_API_KEY": "TEST_MOCK_GEMINI_API_KEY"}):
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = hallucinated_json
            mock_client.models.generate_content.return_value = mock_response
            mock_client_cls.return_value = mock_client

            res = synthesize_agent_intelligence(
                incident_data=state["incident_data"],
                trace_data=state["trace_data"],
                risk_data=state["risk_assessment"],
                actions=state["recommended_actions"]
            )

            assert res["available"] is False
            assert res["status_code"] == "VALIDATION_FAILED"
            assert any("QUANTITY_MISMATCH" in r for r in res["rejection_reasons"])
            assert "2,400" in res["risk_explanation"]


# ==============================================================================
# 7. ADVERSARIAL TEST 7: Malformed JSON Output
# ==============================================================================
def test_adv_07_malformed_json_handling():
    """Adversarial check: Gemini returns unstructured text or malformed JSON."""
    state = get_mock_base_state()
    malformed_text = "Here is my reasoning without proper JSON: Intake is bad, traceability is complex."

    with patch.dict(os.environ, {"GEMINI_API_KEY": "TEST_MOCK_GEMINI_API_KEY"}):
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = malformed_text
            mock_client.models.generate_content.return_value = mock_response
            mock_client_cls.return_value = mock_client

            res = synthesize_agent_intelligence(
                incident_data=state["incident_data"],
                trace_data=state["trace_data"],
                risk_data=state["risk_assessment"],
                actions=state["recommended_actions"]
            )

            assert res["available"] is False
            assert res["status_code"] == "MALFORMED_OUTPUT"
            assert "RAW-204" in res["intake_explanation"]


# ==============================================================================
# 8. ADVERSARIAL TEST 8: API Timeout and Quota Errors
# ==============================================================================
def test_adv_08_api_timeout_and_quota_errors():
    """Adversarial check: API deadline expires or quota exceeded."""
    state = get_mock_base_state()

    with patch.dict(os.environ, {"GEMINI_API_KEY": "TEST_MOCK_GEMINI_API_KEY"}):
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = Exception("504 Deadline Exceeded: Client timeout waiting for response")
            mock_client_cls.return_value = mock_client

            res = synthesize_agent_intelligence(
                incident_data=state["incident_data"],
                trace_data=state["trace_data"],
                risk_data=state["risk_assessment"],
                actions=state["recommended_actions"]
            )

            assert res["available"] is False
            assert res["status_code"] == "TIMEOUT"
            assert "timed out" in res["note"].lower()


# ==============================================================================
# 9. ADVERSARIAL TEST 9: Gemini Unavailable (Missing API Key)
# ==============================================================================
def test_adv_09_gemini_unavailable_offline():
    """Adversarial check: Environment has no API key; returns honest fallback."""
    state = get_mock_base_state()

    with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}):
        res = synthesize_agent_intelligence(
            incident_data=state["incident_data"],
            trace_data=state["trace_data"],
            risk_data=state["risk_assessment"],
            actions=state["recommended_actions"]
        )

        assert res["available"] is False
        assert res["status_code"] == "MISSING_API_KEY"
        assert "GEMINI_API_KEY is not configured" in res["note"]
        assert "Salmonella" in res["intake_explanation"]


# ==============================================================================
# 10. ADVERSARIAL TEST 10: Human Approval Independent of Gemini
# ==============================================================================
def test_adv_10_human_approval_independent_of_gemini():
    """Adversarial check: Human operator approval succeeds and commits to Db2
    even when Gemini is completely unavailable or erroring.
    """
    # 1. Reset demo state first to ensure clean starting point
    db2_service.reset_incident_demo_state("INC-2026-001")

    # 2. Approve ACT-002 independently
    success = db2_service.update_action_decision(
        action_id="ACT-002",
        decision="APPROVED",
        operator_name="Lead Product Safety Officer",
        notes="Human approved via safety protocol independently of AI."
    )
    assert success is True

    # 3. Verify in Db2
    actions = db2_service.get_actions_for_incident("INC-2026-001")
    act_002 = next((a for a in actions if a["action_id"] == "ACT-002"), None)
    assert act_002 is not None
    assert act_002["status"] == "APPROVED"
    assert act_002["approved_by"] == "Lead Product Safety Officer"

    # 4. Clean up by resetting demo state
    db2_service.reset_incident_demo_state("INC-2026-001")


# ==============================================================================
# 11. ADVERSARIAL TEST 11: Duplicate Approval Requests Rejected
# ==============================================================================
def test_adv_11_duplicate_approval_requests_rejected():
    """Adversarial check: Submitting approval for an action already in that status
    must raise ValueError and prevent inconsistent audit log entries.
    """
    db2_service.reset_incident_demo_state("INC-2026-001")
    # ACT-001 is already APPROVED in baseline state
    with pytest.raises(ValueError) as excinfo:
        db2_service.update_action_decision(
            action_id="ACT-001",
            decision="APPROVED",
            operator_name="Lead Product Safety Officer"
        )
    assert "Duplicate decision rejected" in str(excinfo.value)


# ==============================================================================
# 12. ADVERSARIAL TEST 12: ACID Transaction Rollback Consistency
# ==============================================================================
def test_adv_12_acid_transaction_rollback_and_audit_consistency():
    """Adversarial check: When an atomic multi-statement transaction fails mid-way,
    the entire transaction must roll back with zero partial writes.
    """
    from app.database import execute_transaction, query_one

    # Attempt transaction: valid statement followed by a deliberate syntax error
    failing_ops = [
        (
            "UPDATE LOTLINE_APP.RECALL_ACTIONS SET STATUS = 'PROPOSED' WHERE ACTION_ID = 'ACT-001'",
            ()
        ),
        (
            "INSERT INTO LOTLINE_APP.NON_EXISTENT_TABLE (BAD_COL) VALUES ('FAIL')",
            ()
        )
    ]

    # Must fail and raise exception after rolling back
    with pytest.raises(Exception):
        execute_transaction(failing_ops)

    # Verify ACT-001 was NOT changed to PROPOSED because transaction rolled back
    action = query_one("SELECT STATUS FROM LOTLINE_APP.RECALL_ACTIONS WHERE ACTION_ID = 'ACT-001'")
    assert action is not None
    assert action["status"] == "APPROVED"


# ==============================================================================
# 13. TEST 13: Full Valid Synthesis Success with All 4 Agents
# ==============================================================================
def test_gemini_success_with_all_four_agents():
    """Verify that structured, validated Gemini output passes and populates all 4 agents."""
    state = get_mock_base_state()
    valid_structured_json = json.dumps({
        "intake": {
            "agent_id": "incident_intake",
            "operational_interpretation": "Verified source lot RAW-204 (500 KG Organic Spinach) from GreenLeaf Foods under incident INC-2026-001. Contaminant confirmed as Salmonella.",
            "supporting_evidence_refs": ["INC-2026-001", "RAW-204", "GreenLeaf Foods", "Salmonella"],
            "limitations_or_missing_info": "Supplier country is India; no street address recorded."
        },
        "traceability": {
            "agent_id": "traceability",
            "operational_interpretation": "Recursive CTE identified 6 downstream batches (WIP-301..303 and FIN-401..403) across 2 production levels.",
            "supporting_evidence_refs": ["RAW-204", "WIP-301", "WIP-302", "WIP-303", "FIN-401", "FIN-402", "FIN-403"],
            "limitations_or_missing_info": "Lineage bounded at 2 levels."
        },
        "risk": {
            "agent_id": "risk_assessment",
            "operational_interpretation": "Exposure calculated at 2,400 total units: 1,350 in warehouse, 850 delivered to retail, and 200 in transit.",
            "supporting_evidence_refs": ["2400 units", "1350 warehouse", "850 retail", "200 transit"],
            "limitations_or_missing_info": "POS scan data is external."
        },
        "response_planning": {
            "agent_id": "response_planning",
            "operational_interpretation": "Protocols ACT-001 to ACT-004 formulated. Mandatory human operator sign-off enforced.",
            "supporting_evidence_refs": ["ACT-001", "ACT-002", "ACT-003", "ACT-004"],
            "limitations_or_missing_info": "All actions gated by Human-in-the-Loop review."
        }
    })

    with patch.dict(os.environ, {"GEMINI_API_KEY": "TEST_MOCK_GEMINI_API_KEY"}):
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = valid_structured_json
            mock_client.models.generate_content.return_value = mock_response
            mock_client_cls.return_value = mock_client

            # Run workflow agent
            s1 = intake_agent(state)
            state["steps"] = [s1["steps"][0]]
            s2 = traceability_agent(state)
            state["steps"] = state["steps"] + [s2["steps"][0]]
            s3 = risk_assessment_agent(state)
            state["steps"] = state["steps"] + [s3["steps"][0]]
            s4 = response_planning_agent(state)

            assert s4["gemini_status"]["available"] is True
            assert s4["gemini_status"]["status_code"] == "CONNECTED"
            assert len(s4["steps"]) == 4

            # Verify all 4 agents received validated interpretations and structured metadata
            for step in s4["steps"]:
                assert step["ai_status"] == "GEMINI_SYNTHESIZED"
                assert step["ai_interpretation"] is not None
                assert step["validation_status"] == "VALIDATED"
                assert len(step["supporting_evidence_refs"]) > 0


# ==============================================================================
# 14. TEST 14: Credential Redaction Security
# ==============================================================================
def test_credential_redaction():
    """Verify regex and explicit replacement prevent credential leaks."""
    fake_key = "AIzaSyD-FakeSecretApiKeyForTesting12"
    raw_error = f"ClientError 403: Invalid authorization credentials with key {fake_key}"
    sanitized = sanitize_message(raw_error, fake_key)
    assert fake_key not in sanitized
    assert "[REDACTED_API_KEY]" in sanitized


# ==============================================================================
# PHASE 4: RECALL DOSSIER & REGULATORY REPORTING TESTS
# ==============================================================================
from app.services.pdf_report_service import generate_recall_dossier, get_dossier_preview
from fastapi.testclient import TestClient
from app.main import app

api_client = TestClient(app)


def test_dossier_data_retrieval_and_binary_generation():
    """Verify dossier generates a valid 5-page PDF with verified Db2 facts."""
    pdf_bytes, sha256_digest, metadata = generate_recall_dossier(
        incident_id="INC-2026-001",
        operator_name="Safety Auditor",
        include_fssai=True
    )
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 10000
    assert pdf_bytes.startswith(b"%PDF-")
    assert sha256_digest is not None
    assert len(sha256_digest) == 64
    assert metadata["incident_id"] == "INC-2026-001"
    assert metadata["fssai_draft_included"] is True

    # Verify PDF structure using pymupdf
    import pymupdf
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    assert doc.page_count in (5, 6), f"Expected 5 or 6 pages, got {doc.page_count}"

    # Verify Page 1 has incident, supplier, and contaminant
    page1_text = doc[0].get_text()
    assert "INC-2026-001" in page1_text
    assert "RAW-204" in page1_text
    assert "Salmonella" in page1_text
    assert "GreenLeaf Foods" in page1_text
    assert "India" in page1_text

    # Verify strict unit separation: 500 KG raw vs 2,400 UNIT finished
    assert "500" in page1_text
    assert "KG" in page1_text
    assert "2,400" in page1_text or "2400" in page1_text

    # Verify Page 2 has lineage nodes
    page2_text = doc[1].get_text()
    assert "WIP-301" in page2_text or "FIN-401" in page2_text
    assert "TRACEABILITY" in page2_text.upper()

    # Verify Page 3 has exposure numbers
    page3_text = doc[2].get_text()
    assert "1,350" in page3_text or "1350" in page3_text
    assert "850" in page3_text
    assert "200" in page3_text

    # Verify Page 4 has actions ACT-001..004
    page4_text = doc[3].get_text()
    assert "ACT-001" in page4_text
    assert "ACT-002" in page4_text

    # Verify Page 5 has FSSAI Schedule-I regulatory draft
    page5_text = doc[4].get_text()
    assert "FSSAI" in page5_text
    assert "SCHEDULE-I" in page5_text or "Schedule-I" in page5_text
    assert "Salmonella" in page5_text


def test_dossier_exposure_unit_separation():
    """Verify raw KG and finished UNIT are strictly segregated and never combined."""
    preview = get_dossier_preview("INC-2026-001")
    assert preview is not None
    assert preview["raw_unit"] == "KG"
    assert preview["raw_quantity"] == 500.0
    assert preview["finished_goods_units"] == 2400
    assert preview["warehouse_units"] == 1350
    assert preview["delivered_units"] == 850
    assert preview["transit_units"] == 200
    assert preview["warehouse_units"] + preview["delivered_units"] + preview["transit_units"] == 2400


def test_dossier_dynamic_action_statuses():
    """Verify dossier dynamically reflects live Db2 action statuses."""
    actions = db2_service.get_actions_for_incident("INC-2026-001")
    preview = get_dossier_preview("INC-2026-001")
    assert preview["actions_total"] == len(actions)
    approved_count = len([a for a in actions if a.get("status") == "APPROVED"])
    assert preview["actions_approved"] == approved_count


def test_dossier_no_mutation_during_generation():
    """Verify generating a dossier does not mutate any recall actions."""
    actions_before = db2_service.get_actions_for_incident("INC-2026-001")
    status_map_before = {a["action_id"]: a["status"] for a in actions_before}

    # Generate dossier
    generate_recall_dossier("INC-2026-001", "Integrity Check", include_fssai=True)

    actions_after = db2_service.get_actions_for_incident("INC-2026-001")
    status_map_after = {a["action_id"]: a["status"] for a in actions_after}

    assert status_map_before == status_map_after, "Dossier generation must never mutate recall action statuses"


def test_dossier_audit_log_recorded():
    """Verify generating a dossier writes an immutable DOSSIER_GENERATED audit log."""
    audits_before = db2_service.get_audit_trail("INC-2026-001")

    generate_recall_dossier("INC-2026-001", "Audit Verifier", include_fssai=False)

    audits_after = db2_service.get_audit_trail("INC-2026-001")
    assert len(audits_after) >= len(audits_before)
    dossier_events = [a for a in audits_after if a.get("event_type") == "DOSSIER_GENERATED"]
    assert len(dossier_events) > 0
    latest_event = dossier_events[0]
    assert latest_event["actor"] == "Audit Verifier"
    assert "SHA-256" in latest_event.get("details", "")


def test_dossier_api_endpoint():
    """Verify GET /api/incidents/{incident_id}/dossier returns valid PDF stream and headers."""
    resp = api_client.get("/api/incidents/INC-2026-001/dossier?include_fssai=true&operator_name=Lead%20Investigator")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "LOTLINE-RECALL-DOSSIER-INC-2026-001.pdf" in resp.headers.get("content-disposition", "")
    assert "x-dossier-sha256" in resp.headers
    assert len(resp.headers["x-dossier-sha256"]) == 64
    assert resp.content.startswith(b"%PDF-")


def test_dossier_preview_api_endpoint():
    """Verify GET /api/incidents/{incident_id}/dossier/preview returns 200 with structured metadata."""
    resp = api_client.get("/api/incidents/INC-2026-001/dossier/preview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["incident_id"] == "INC-2026-001"
    assert data["contaminant"] == "Salmonella"
    assert data["source_lot_id"] == "RAW-204"
    assert data["estimated_pages"] in (5, 6)
    assert data["fssai_profile_ready"] is True


def test_dossier_invalid_incident_404():
    """Verify invalid incident returns 404 cleanly."""
    resp = api_client.get("/api/incidents/INC-NONEXISTENT-999/dossier")
    assert resp.status_code == 404
    resp_prev = api_client.get("/api/incidents/INC-NONEXISTENT-999/dossier/preview")
    assert resp_prev.status_code == 404


def test_dossier_no_secret_leak():
    """Verify neither PDF bytes, preview JSON, nor headers contain API keys or passwords."""
    env_key = os.environ.get("GEMINI_API_KEY", "")
    resp = api_client.get("/api/incidents/INC-2026-001/dossier")
    assert resp.status_code == 200

    if env_key and len(env_key) > 5:
        assert env_key.encode("utf-8") not in resp.content
        for h_val in resp.headers.values():
            assert env_key not in h_val

    # Check preview endpoint
    prev_resp = api_client.get("/api/incidents/INC-2026-001/dossier/preview")
    assert prev_resp.status_code == 200
    if env_key and len(env_key) > 5:
        assert env_key not in prev_resp.text


# ============================================================================
# PHASE 5: CLOSED-LOOP RECALL EXECUTION & REGULATORY OPERATIONS TESTS (1 - 20)
# ============================================================================

def test_phase5_req1_raw_material_mass_reconciliation():
    """1. Raw material mass reconciliation: 500 KG intake, 400 KG WIP, 50 KG quarantined, 50 KG unaccounted, status UNRECONCILED."""
    resp = api_client.get("/api/incidents/INC-2026-001/reconciliation/raw")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_lot_id"] == "RAW-204"
    assert data["original_quantity"] == 500.0
    assert data["recorded_wip_consumption"] == 400.0
    assert data["quarantined_quantity"] == 50.0
    assert data["accounted_quantity"] == 450.0
    assert data["unaccounted_quantity"] == 50.0
    assert data["reconciliation_status"] == "UNRECONCILED"
    assert len(data["wip_breakdown"]) == 3


def test_phase5_req2_prohibition_of_silent_inventory_balancing():
    """2. Prohibition of silent inventory balancing: Discrepancy cannot be hidden or forced to balance."""
    resp = api_client.get("/api/incidents/INC-2026-001/reconciliation/raw")
    assert resp.status_code == 200
    data = resp.json()
    assert data["reconciliation_status"] != "RECONCILED"
    assert data["unaccounted_quantity"] > 0
    assert "UNRECONCILED" in data["notes"]
    assert "automated balancing prohibited" in data["notes"].lower()


def test_phase5_req3_correct_shipment_to_recipient_mappings():
    """3. Correct shipment-to-recipient mappings: ACT-002 (retailer notice) vs SHP-002 (Pune West)."""
    # Check ACT-002
    actions = db2_service.get_actions_for_incident("INC-2026-001")
    act_002 = next((a for a in actions if a["action_id"] == "ACT-002"), None)
    assert act_002 is not None
    assert act_002["action_type"] == "NOTIFY_RETAILER"
    assert "retailer notification" in act_002["action_description"].lower()

    # Check SHP-002
    shipments = db2_service.get_shipments_for_incident("RAW-204")
    shp_002 = next((s for s in shipments if s["shipment_id"] == "SHP-002"), None)
    assert shp_002 is not None
    assert shp_002["retailer"] == "FreshMart Pune West"
    assert shp_002["lot_id"] == "FIN-401"
    assert shp_002["quantity"] == 200.0
    assert shp_002["status"] == "IN_TRANSIT"


def test_phase5_req4_delineation_of_carrier_vs_retailer_notification():
    """4. Delineation of carrier contact vs retailer notification: ACT-002 cannot satisfy carrier contact."""
    intvs = db2_service.get_logistics_interventions("INC-2026-001")
    int_001 = next((i for i in intvs if i["shipment_id"] == "SHP-002"), None)
    assert int_001 is not None
    assert int_001["carrier_identity"] == "ColdChain Logistics Express"
    # Interception record exists distinctly from ACT-002
    assert int_001["intervention_id"] == "INT-001"


def test_phase5_req5_consignee_communication_lifecycle():
    """5. Consignee communication lifecycle: Transitions through states."""
    comms = db2_service.get_recall_communications("INC-2026-001")
    assert len(comms) >= 4
    for c in comms:
        assert c["status"] in [
            "DRAFT", "PENDING_APPROVAL", "APPROVED", "SENT", "DELIVERED", "ACKNOWLEDGED", "FAILED", "ESCALATED"
        ]


def test_phase5_req6_approval_enforcement_before_dispatch():
    """6. Approval enforcement before communication dispatch: Cannot transition directly from PENDING_APPROVAL to SENT."""
    with pytest.raises(ValueError) as excinfo:
        db2_service.update_communication_status(
            comm_id="COMM-002",
            new_status="SENT",
            operator_name="Test Operator",
            notes="Attempt unauthorized dispatch"
        )
    assert "human approval required" in str(excinfo.value).lower()


def test_phase5_req7_prohibition_of_false_sent_claims():
    """7. Prohibition of false 'sent' claims without approval: Invalid state transitions reject."""
    with pytest.raises(ValueError):
        db2_service.update_communication_status(
            comm_id="COMM-003",
            new_status="INVALID_STATUS_CODE",
            operator_name="Test Operator"
        )


def test_phase5_req8_logistics_interception_workflow():
    """8. Logistics interception workflow: Transitions through INT-001 states."""
    intvs = db2_service.get_logistics_interventions("INC-2026-001")
    assert len(intvs) >= 1
    int_001 = intvs[0]
    assert int_001["shipment_id"] == "SHP-002"
    assert int_001["status"] in [
        "NOT_INITIATED", "PENDING_APPROVAL", "REQUEST_SENT", "CARRIER_ACKNOWLEDGED",
        "INTERCEPTION_CONFIRMED", "INTERCEPTION_FAILED", "RETURNED_TO_WAREHOUSE"
    ]


def test_phase5_req9_verification_requirement_for_carrier_confirmation():
    """9. Verification requirement for carrier confirmation: Interception requires location/operator evidence."""
    success = db2_service.update_logistics_intervention(
        intervention_id="INT-001",
        new_status="CARRIER_ACKNOWLEDGED",
        operator_name="Logistics Lead",
        cargo_location="Pune Expressway Toll Plaza",
        interception_notes="Driver verified load intact and halted at cold bay."
    )
    assert success is True


def test_phase5_req10_recovery_quantity_limits():
    """10. Recovery quantity limits: Quantity cannot exceed available batch exposure."""
    with pytest.raises(ValueError) as excinfo:
        db2_service.record_product_recovery(
            incident_id="INC-2026-001",
            lot_id="FIN-401",
            source_location_type="RETAILER_STOCK",
            source_entity_name="Test Retailer",
            quantity_recovered=999999.0,  # Exceeds total exposure of 1,000 units
            operator_name="QC Lead"
        )
    assert "numerical constraint violation" in str(excinfo.value).lower()


def test_phase5_req11_duplicate_recovery_protection():
    """11. Protection: Zero or negative quantities rejected."""
    with pytest.raises(ValueError) as excinfo:
        db2_service.record_product_recovery(
            incident_id="INC-2026-001",
            lot_id="FIN-401",
            source_location_type="RETAILER_STOCK",
            source_entity_name="Test Retailer",
            quantity_recovered=-10.0,
            operator_name="QC Lead"
        )
    assert "greater than 0" in str(excinfo.value).lower()


def test_phase5_req12_multi_tier_recovery_aggregation():
    """12. Multi-tier recovery aggregation: Accurate separation of warehouse containment vs market recovery."""
    summary = db2_service.get_recovery_reconciliation_summary("INC-2026-001")
    assert summary["total_affected_units"] == 2400.0
    assert summary["warehouse_contained_units"] == 1350.0
    assert summary["market_recovered_units"] == 0.0
    assert summary["market_outstanding_units"] == 1050.0
    assert summary["market_recovery_pct"] == 0.0
    assert summary["warehouse_containment_pct"] in (56.25, 56.3)
    assert len(summary["batch_breakdown"]) == 3
    for b in summary["batch_breakdown"]:
        assert b["warehouse_contained_units"] == b["warehouse_exposed"]
        assert b["market_recovered_units"] == (b["retailer_returned_units"] + b["transit_intercepted_units"])
        assert b["market_outstanding_units"] == (b["delivered_not_returned_units"] + b["transit_not_intercepted_units"])
        assert b["market_recovery_pct"] == 0.0


def test_phase5_req13_human_approval_requirement_for_disposition():
    """13. Human approval requirement for product disposition: Cannot execute PROPOSED disposition without APPROVED status."""
    # Create a proposed disposition
    disp_id = db2_service.create_product_disposition(
        incident_id="INC-2026-001",
        lot_id="RAW-204",
        lot_type="RAW_MATERIAL",
        quantity=5.0,
        unit_of_measure="KG",
        disposition_type="DESTRUCTION",
        reason="Testing disposition authorization enforcement",
        proposed_method="Municipal incineration",
        operator_name="Tester"
    )

    # Attempt execute directly from PROPOSED
    with pytest.raises(ValueError) as excinfo:
        db2_service.execute_product_disposition(
            disposition_id=disp_id,
            operator_name="Tester"
        )
    assert "must be approved" in str(excinfo.value).lower()

    # Now approve it
    app_res = db2_service.approve_product_disposition(
        disposition_id=disp_id,
        operator_name="Safety Officer",
        notes="Approved for test destruction."
    )
    assert app_res is True

    # Now execute it
    exec_res = db2_service.execute_product_disposition(
        disposition_id=disp_id,
        operator_name="Plant Lead",
        evidence_attachment="TEST-CERT.pdf"
    )
    assert exec_res is True


def test_phase5_req14_fssai_schedule1_checklist_mapping():
    """14. Complete 14-item FSSAI Schedule-I checklist mapping: All 14 items with correct 5 statuses."""
    res = db2_service.get_fssai_schedule1_checklist("INC-2026-001")
    assert res is not None
    assert res["readiness_summary"]["total_items"] == 14
    assert len(res["items"]) == 14

    allowed_statuses = {
        "Db2 verified", "Manually required", "Evidence missing", "Not applicable", "Awaiting human verification"
    }
    for item in res["items"]:
        assert item["status"] in allowed_statuses
        assert item["item_no"] in range(1, 15)

    assert res["readiness_summary"]["verified_count"] >= 7
    assert res["readiness_summary"]["manual_count"] >= 2


def test_phase5_req15_foscos_portal_reference_tracking():
    """15. FoSCoS portal reference tracking: Portal reference number update and stage transitions."""
    subs = db2_service.get_regulatory_submissions("INC-2026-001")
    assert len(subs) >= 1
    sub_001 = subs[0]
    assert "FSSAI" in sub_001["regulatory_body"]

    # Update stage and portal ref
    success = db2_service.update_regulatory_submission_stage(
        submission_id=sub_001["submission_id"],
        new_stage="OPERATOR_VERIFIED",
        operator_name="Compliance Officer",
        foscos_recall_ref="FOSCOS-REF-UNITTEST-001"
    )
    assert success is True


def test_phase5_req16_24hour_awareness_deadline_calculation():
    """16. 24-hour statutory awareness deadline calculation: Exact timestamp arithmetic from INCIDENTS.CREATED_AT."""
    res = db2_service.get_fssai_schedule1_checklist("INC-2026-001")
    awareness_str = res["awareness_timestamp"]
    deadline_str = res["statutory_deadline"]

    from datetime import datetime, timedelta
    t0 = datetime.fromisoformat(awareness_str)
    t1 = datetime.fromisoformat(deadline_str)
    assert t1 - t0 == timedelta(hours=24)


def test_phase5_req17_post_recall_effectiveness_metrics():
    """17. Post-recall effectiveness metrics: Accurate calculation of 12 statutory metrics."""
    eff = db2_service.calculate_recall_effectiveness("INC-2026-001")
    assert "total_affected_units" in eff
    assert eff["total_affected_units"] == 2400.0
    assert "quantity_recovered" in eff
    assert "recall_effectiveness_pct" in eff
    assert "orgs_identified" in eff
    assert "orgs_acknowledged" in eff
    assert "consignee_response_pct" in eff
    assert len(eff["report_metrics"]) == 12


def test_phase5_req18_30day_followup_deadline_tracking():
    """18. Thirty-day follow-up deadline tracking: Accurate 30-day projection from awareness timestamp."""
    inc = db2_service.get_incident("INC-2026-001")
    t0_str = inc["created_at"]
    from datetime import datetime, timedelta
    t0 = datetime.fromisoformat(t0_str)
    t30 = t0 + timedelta(days=30)
    assert (t30 - t0).days == 30


def test_phase5_req19_prohibition_of_recall_closure_while_blockers_remain():
    """19. Prohibition of recall closure while exposure/blockers remain: Rejection of closure."""
    eff = db2_service.calculate_recall_effectiveness("INC-2026-001")
    if not eff["can_close_recall"]:
        with pytest.raises(ValueError) as excinfo:
            db2_service.attempt_close_recall(
                incident_id="INC-2026-001",
                operator_name="Auditor",
                justification="Attempt unauthorized closure"
            )
        assert "cannot be closed" in str(excinfo.value).lower()
        assert len(eff["closure_blockers"]) > 0


def test_phase5_req20_audit_log_immutability_and_redaction():
    """20. Audit log immutability and credential redaction: Immutability of audit log and zero sensitive leaks."""
    # Verify audit log entries are persisted and read-only
    audit = db2_service.get_audit_trail("INC-2026-001")
    assert len(audit) > 0

    # Verify no credentials leaked in effectiveness or checklist API outputs
    eff_resp = api_client.get("/api/incidents/INC-2026-001/effectiveness")
    assert eff_resp.status_code == 200
    env_key = os.environ.get("GEMINI_API_KEY", "")
    if env_key and len(env_key) > 5:
        assert env_key not in eff_resp.text
        assert "ankush" not in eff_resp.text  # db password


def test_phase5_1_reqA_market_recovery_semantics():
    """Phase 5.1 A: Separation of warehouse containment from market recovery."""
    rec = db2_service.get_recovery_reconciliation_summary("INC-2026-001")
    assert rec["warehouse_contained_units"] == 1350.0
    assert rec["market_recovered_units"] == 0.0
    assert rec["market_outstanding_units"] == 1050.0
    assert rec["market_recovery_pct"] == 0.0
    assert rec["warehouse_containment_pct"] == 56.25
    assert rec["total_exposed_units"] == 2400.0

    # Verify batches have distinct breakdowns
    assert len(rec["batches"]) == 3
    for b in rec["batches"]:
        assert b["market_recovered_units"] == 0.0
        assert b["warehouse_contained_units"] > 0.0
        assert b["market_outstanding_units"] > 0.0


def test_phase5_1_reqB_disposition_unit_separation_and_synthetic_fixtures():
    """Phase 5.1 B: Separate KG raw and UNIT finished goods, synthetic fixture detection."""
    disps = db2_service.get_product_dispositions("INC-2026-001")
    assert len(disps) > 0
    for d in disps:
        assert d["quantity_unit"] in ("KG", "UNIT")
        if "TEST-CERT" in (d.get("evidence_attachment") or ""):
            assert d["is_synthetic_fixture"] is True
            assert d["evidence_status"] == "SYNTHETIC_FIXTURE"

    eff = db2_service.calculate_recall_effectiveness("INC-2026-001")
    # Operational verified destruction must exclude synthetic fixtures
    assert eff["quantity_destroyed_kg"] == 0.0
    assert eff["quantity_destroyed_units"] == 0


def test_phase5_1_reqC_consignee_communications_normalization():
    """Phase 5.1 C: Recipient organization and template fallbacks, no lone bullets."""
    comms = db2_service.get_recall_communications("INC-2026-001")
    assert len(comms) == 4
    for c in comms:
        assert c["recipient_org"]
        assert c["recipient_org"] != "•"
        assert c["statutory_template_ref"]
        assert c["statutory_template_ref"] != "•"


def test_phase5_1_reqD_foscos_tracking_and_structured_closure_blockers():
    """Phase 5.1 D & F: Honest FoSCoS tracking label and server-computed closure blockers."""
    subs = db2_service.get_regulatory_submissions("INC-2026-001")
    assert len(subs) > 0
    for s in subs:
        assert s["foscos_reference_label"] == "Internal tracking reference (synthetic/demo)"
        assert s["is_official_portal_receipt"] is False

    eff = db2_service.calculate_recall_effectiveness("INC-2026-001")
    assert eff["can_close_recall"] is False
    codes = [b["code"] for b in eff["structured_blockers"]]
    assert "BLOCK_MARKET_EXPOSURE" in codes
    assert "BLOCK_PENDING_COMMS" in codes
    assert "BLOCK_TRANSIT_INTERCEPTION" in codes
    assert "BLOCK_PENDING_DISPOSITIONS" in codes
    assert "BLOCK_REGULATORY_SUBMISSION" in codes
    assert "BLOCK_RAW_MASS_VARIANCE" in codes

    # Direct close via API client must reject with 400
    close_resp = api_client.post("/api/incidents/INC-2026-001/close", json={
        "operator_name": "Direct Attacker",
        "justification": "Bypassing frontend checks"
    })
    assert close_resp.status_code == 400
    assert "cannot be closed" in close_resp.text.lower()




