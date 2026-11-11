"""
CivicConnect – Test Suite for IBM Db2 Integration
Tests the schema setup, complaint CRUD operations, and the LangChain AI
classifier using a live or mocked IBM Db2 connection.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Make src importable from tests/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ---------------------------------------------------------------------------
# Unit tests – AI Classifier (no Db2 needed)
# ---------------------------------------------------------------------------

class TestComplaintClassifier:
    """Tests for the heuristic + LangChain classifier."""

    def test_heuristic_pothole(self):
        from ai.classifier import classify_complaint, _heuristic_classify

        result = _heuristic_classify(
            title="Large pothole on main road",
            description="There is a huge pothole near the market that has caused two tire bursts.",
        )
        assert result["category"] == "Road Damage / Potholes"
        assert result["department"] == "Public Works Department"
        assert result["priority"] in ("medium", "high")
        assert result["ai_powered"] is False

    def test_heuristic_garbage(self):
        from ai.classifier import _heuristic_classify

        result = _heuristic_classify(
            title="Overflowing garbage dump",
            description="The dustbin near the hospital has been overflowing for 5 days.",
        )
        assert result["category"] == "Garbage Collection"
        assert result["department"] == "Sanitation Department"
        assert result["priority"] == "high"

    def test_heuristic_streetlight_urgent(self):
        from ai.classifier import _heuristic_classify

        result = _heuristic_classify(
            title="Exposed live wire sparking near school",
            description="A streetlight pole has a spark and exposed wire that is dangerous.",
        )
        assert result["category"] == "Streetlight Problems"
        assert result["priority"] == "urgent"

    def test_heuristic_water_leak(self):
        from ai.classifier import _heuristic_classify

        result = _heuristic_classify(
            title="Burst water pipe flooding street",
            description="Main pipeline near the park has burst and is flooding the entire road.",
        )
        assert result["category"] == "Water Leakage"
        assert result["priority"] == "high"

    def test_heuristic_fallback_to_other(self):
        from ai.classifier import _heuristic_classify

        result = _heuristic_classify(
            title="General city concern",
            description="Some unspecified issue in the neighbourhood.",
        )
        assert result["category"] == "Other Civic Issues"
        assert result["department"] == "Municipal Administration"

    def test_classify_returns_valid_keys(self):
        from ai.classifier import classify_complaint

        result = classify_complaint("Pothole on bridge", "Deep crack in bridge road.")
        required_keys = {"category", "department", "priority", "keywords", "summary", "ai_powered"}
        assert required_keys.issubset(result.keys())
        assert isinstance(result["keywords"], list)

    def test_category_department_mapping(self):
        from ai.classifier import CATEGORY_DEPARTMENT_MAP

        assert "Garbage Collection" in CATEGORY_DEPARTMENT_MAP
        assert CATEGORY_DEPARTMENT_MAP["Water Leakage"] == "Water Supply Department"
        assert CATEGORY_DEPARTMENT_MAP["Road Damage / Potholes"] == "Public Works Department"
        assert len(CATEGORY_DEPARTMENT_MAP) == 7


# ---------------------------------------------------------------------------
# Integration tests – IBM Db2 (require live DB2 connection)
# ---------------------------------------------------------------------------

class TestDb2Connection:
    """
    These tests require a running IBM Db2 instance.
    Set DB2_DATABASE, DB2_HOST, DB2_USER, DB2_PASSWORD env vars.
    Skip automatically when credentials are not available.
    """

    @pytest.fixture(autouse=True)
    def skip_without_db2(self):
        if not all(os.getenv(k) for k in ("DB2_DATABASE", "DB2_HOST", "DB2_USER", "DB2_PASSWORD")):
            pytest.skip("IBM Db2 credentials not configured — skipping integration tests.")

    def test_schema_setup(self):
        from db.db2_setup import setup_schema, get_ibm_db_connection
        import ibm_db

        setup_schema()
        conn = get_ibm_db_connection()
        stmt = ibm_db.exec_immediate(
            conn,
            "SELECT COUNT(*) AS CNT FROM SYSCAT.TABLES WHERE TABSCHEMA = 'CIVICCONNECT'"
        )
        row = ibm_db.fetch_assoc(stmt)
        ibm_db.close(conn)
        assert int(row["CNT"]) >= 5, "Expected at least 5 CivicConnect tables in Db2."

    def test_seed_and_fetch_departments(self):
        from db.db2_repository import seed_departments, fetch_all_departments

        seed_departments()
        depts = fetch_all_departments()
        assert len(depts) >= 6
        dept_names = [d["NAME"] for d in depts]
        assert "Sanitation Department" in dept_names
        assert "Public Works Department" in dept_names

    def test_insert_and_fetch_complaint(self):
        from db.db2_repository import insert_complaint, fetch_all_complaints
        import uuid

        unique_id = f"TEST-{uuid.uuid4().hex[:8].upper()}"
        sample = {
            "id": str(uuid.uuid4()),
            "complaint_id": unique_id,
            "user_id": "test-user-001",
            "citizen_name": "Test Citizen",
            "citizen_email": "test@civicconnect.local",
            "title": "Test pothole complaint",
            "description": "Integration test complaint entry.",
            "category": "Road Damage / Potholes",
            "department_id": "DEPT-PWD",
            "department_name": "Public Works Department",
            "location": "Test Lane, Block 5",
            "priority": "medium",
            "status": "Submitted",
            "ai_summary": "Test complaint for Db2 integration verification.",
            "ai_keywords": ["pothole", "road", "test"],
        }

        saved = insert_complaint(sample)
        assert saved["complaint_id"] == unique_id

        all_complaints = fetch_all_complaints()
        ids = [c["COMPLAINT_ID"] for c in all_complaints]
        assert unique_id in ids

    def test_update_complaint_status(self):
        from db.db2_repository import insert_complaint, update_complaint_status, fetch_all_complaints
        import uuid

        cid = f"STATUS-{uuid.uuid4().hex[:6].upper()}"
        insert_complaint({
            "id": str(uuid.uuid4()),
            "complaint_id": cid,
            "user_id": "test-staff-001",
            "citizen_name": "Status Test",
            "citizen_email": "status@civicconnect.local",
            "title": "Status update test",
            "description": "Testing status transitions.",
            "category": "Other Civic Issues",
            "location": "Test Block",
            "priority": "low",
            "status": "Submitted",
        })

        update_complaint_status(
            complaint_id=cid,
            new_status="Under Review",
            note="Admin reviewed the complaint.",
            updated_by="Admin Test",
            updated_by_uid="test-admin-001",
            role="admin",
        )

        complaints = fetch_all_complaints()
        found = next((c for c in complaints if c["COMPLAINT_ID"] == cid), None)
        assert found is not None
        assert found["STATUS"] == "Under Review"

    def test_category_analytics(self):
        from db.db2_repository import get_category_summary

        summary = get_category_summary()
        assert isinstance(summary, list)
        if summary:
            first = summary[0]
            assert "CATEGORY" in first
            assert "TOTAL" in first


# ---------------------------------------------------------------------------
# API integration tests (FastAPI TestClient – no live Db2 required)
# ---------------------------------------------------------------------------

class TestAPIEndpoints:
    """Tests the FastAPI routes using a mocked Db2 layer."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        with patch("backend.main.setup_schema"), \
             patch("backend.main.seed_departments"), \
             patch("backend.main.classify_complaint") as mock_classify, \
             patch("backend.main.insert_complaint") as mock_insert, \
             patch("backend.main.fetch_all_complaints") as mock_fetch, \
             patch("backend.main.fetch_all_departments") as mock_depts:

            mock_classify.return_value = {
                "category": "Garbage Collection",
                "department": "Sanitation Department",
                "priority": "medium",
                "keywords": ["garbage", "waste"],
                "summary": "Garbage overflow reported.",
                "ai_powered": False,
            }
            mock_insert.return_value = {"complaint_id": "CCMS-2026-TEST", "status": "Submitted"}
            mock_fetch.return_value = []
            mock_depts.return_value = [{"DEPARTMENT_ID": "DEPT-SAN", "NAME": "Sanitation Department"}]

            from backend.main import app
            yield TestClient(app)

    def test_health_endpoint(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_classify_endpoint(self, client):
        resp = client.post(
            "/api/ai/classify",
            json={"title": "Garbage overflow", "description": "Bins overflowing near park."},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["category"] == "Garbage Collection"
        assert body["department"] == "Sanitation Department"

    def test_classify_requires_title(self, client):
        resp = client.post("/api/ai/classify", json={"title": "", "description": "test"})
        assert resp.status_code in (400, 422)

    def test_list_departments(self, client):
        resp = client.get("/api/departments")
        assert resp.status_code == 200
        assert "departments" in resp.json()
