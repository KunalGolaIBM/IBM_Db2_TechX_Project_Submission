"""Analytics, semantic search and schema checks.

All tests run against a real IBM Db2 database; vector tests also need the local Ollama server.
"""
import datetime
import uuid

import pytest
from sqlalchemy import text

from backend.app.ai.haystack.rag_pipeline import retrieve_safety_guidance
from backend.app.ai.semantic.db2_vector_store import vector_store
from backend.app.analytics import insights as analytics
from backend.app.core.config import settings
from backend.app.database import base as db_base
from backend.app.models.entities import Incident, IncidentStatusHistory

from conftest import auth_headers

API = "/api/v1"


def _create(client, headers, **kw):
    body = {"title": "Streetlight out", "description": "Dark lane after sunset near the park.",
            "incident_type": "hazard", "priority": "P3_MODERATE", **kw}
    res = client.post(f"{API}/incidents", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _shift_times(incident_id: int, created_minutes_ago: float, ack_after_minutes=None):
    """Backdate an incident (and its acknowledgement) to build a deterministic timeline."""
    db = db_base.SessionLocal()
    try:
        inc = db.get(Incident, incident_id)
        created = datetime.datetime.utcnow() - datetime.timedelta(minutes=created_minutes_ago)
        inc.created_at = created
        for h in db.query(IncidentStatusHistory).filter(IncidentStatusHistory.incident_id == incident_id):
            if h.status == "reported":
                h.created_at = created
            elif h.status == "acknowledged" and ack_after_minutes is not None:
                h.created_at = created + datetime.timedelta(minutes=ack_after_minutes)
        db.commit()
    finally:
        db.close()


# --- Analytics --------------------------------------------------------------------------------

def test_insights_report_measured_response_times(client, resident, responder):
    inc = _create(client, resident, priority="P2_HIGH", location_address="Gate 3, Lotus Towers")
    assert client.post(f"{API}/incidents/{inc['id']}/acknowledge", headers=responder).status_code == 200
    _shift_times(inc["id"], created_minutes_ago=30, ack_after_minutes=6)

    data = client.get(f"{API}/community/insights", headers=resident).json()
    p2 = next(r for r in data["response_times"] if r["priority"] == "P2_HIGH")
    assert p2["acknowledged"] >= 1 and p2["avg_ack_minutes"] is not None
    assert data["average_response_time_minutes"] is not None
    assert p2["ack_target_minutes"] == 15
    assert data["analytics_engine"]


def test_hotspots_rank_repeated_locations_first(client, resident):
    # Works on a shared, persistent database too: out-report whatever currently ranks first.
    current = client.get(f"{API}/community/insights", headers=resident).json()["hotspots"]
    needed = (current[0]["incidents"] if current else 0) + 1
    spot = f"Underpass {uuid.uuid4().hex[:6]}"
    for _ in range(needed):
        _create(client, resident, location_address=spot)
    hotspots = client.get(f"{API}/community/insights", headers=resident).json()["hotspots"]
    assert hotspots[0]["location"] == spot and hotspots[0]["rank"] == 1 and hotspots[0]["incidents"] == needed


def test_unacknowledged_critical_incident_counts_as_sla_breach(client, resident):
    before = client.get(f"{API}/community/insights", headers=resident).json()["sla_breaches"]
    inc = _create(client, resident, priority="P1_CRITICAL", incident_type="medical", title="Collapsed in lobby")
    _shift_times(inc["id"], created_minutes_ago=10)
    after = client.get(f"{API}/community/insights", headers=resident).json()["sla_breaches"]
    assert after == before + 1


def test_db2_sql_analytics_compute_exact_median_and_p90(client, resident, responder):
    """Known timeline: 4 P4 incidents, 3 acknowledged after 2, 7 and 11 minutes, 1 unacknowledged.
    Db2 must return median 7, PERCENTILE_CONT(0.9) = 7 + 0.8 * (11 - 7) = 10.2, average 6.67."""
    for minutes_ago, ack_after in ((50, 2), (40, 7), (35, 11), (20, None)):
        inc = _create(client, resident, priority="P4_ADVISORY", location_address="Parity Lane")
        if ack_after is not None:
            client.post(f"{API}/incidents/{inc['id']}/acknowledge", headers=responder)
        _shift_times(inc["id"], minutes_ago, ack_after)

    now = datetime.datetime.utcnow()
    db = db_base.SessionLocal()
    try:
        m = analytics._db2_metrics(db, now - datetime.timedelta(days=analytics.WINDOW_DAYS), now)
    finally:
        db.close()
    p4 = next(p for p in m["priorities"] if p.priority == "P4_ADVISORY")
    assert (p4.incidents, p4.acknowledged) == (4, 3)
    assert p4.median_ack_minutes == 7.0
    assert abs(p4.p90_ack_minutes - 10.2) < 0.01
    assert abs(p4.avg_ack_minutes - 6.67) < 0.01


# --- Db2 schema -------------------------------------------------------------------------------

def test_db2_catalog_contains_schema_and_vector_columns():
    expected = {"USERS", "TRUSTED_CONTACTS", "RESPONDERS", "INCIDENTS", "INCIDENT_STATUS_HISTORY",
                "LOCATION_EVENTS", "CHILD_JOURNEYS", "ELDER_CHECKINS", "ASSISTANCE_REQUESTS",
                "COMMUNITY_HAZARDS", "AI_ANALYSIS_RECORDS", "AUDIT_EVENTS"}
    with db_base.engine.connect() as conn:
        tables = {r[0] for r in conn.execute(text(
            "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = CURRENT SCHEMA AND TYPE = 'T'"))}
        assert expected <= tables
        if vector_store.enabled:
            vectors = {(r[0], r[1]) for r in conn.execute(text(
                "SELECT TABNAME, COLNAME FROM SYSCAT.COLUMNS WHERE TABSCHEMA = CURRENT SCHEMA AND TYPENAME = 'VECTOR'"))}
            assert {("NSIN_PROTOCOL_PASSAGES", "EMBEDDING"), ("INCIDENT_EMBEDDINGS", "EMBEDDING")} <= vectors


def test_health_reports_live_db2_connection(client):
    db = client.get("/health").json()["database"]
    assert db["mode"] == "db2" and db["connected"] is True and db["details"]["server_time"]


# --- Semantic search with Db2 VECTOR_DISTANCE ---------------------------------------------------

def test_semantic_retrieval_finds_protocols_without_shared_keywords():
    assert vector_store.enabled, vector_store.error
    res = retrieve_safety_guidance("my grandmother is not answering her phone")
    assert res["found"] and res["retrieval_mode"].startswith("hybrid")
    assert res["results"][0]["document_id"] == "DOC-ELDER-003"
    assert "vector" in res["results"][0]["matched_by"]


def test_semantic_retrieval_rejects_off_topic_queries():
    assert not retrieve_safety_guidance("quantum astrophysics spaceship orbit")["found"]
    assert not retrieve_safety_guidance("what is the recipe for pasta")["found"]


def test_similar_incidents_link_duplicate_reports(client, resident, responder):
    tag = uuid.uuid4().hex[:5]
    place = f"Lane {tag}, Green Glen"
    a = _create(client, resident, title=f"Streetlight broken on Lane {tag}", location_address=place,
                description="The streetlight on our lane has stopped working and the road is completely dark at night.")
    b = _create(client, auth_headers(client, "maya.sen@neighbourhood.org"), title=f"Lane {tag} lamp not working",
                location_address=place,
                description="Street lamp on the lane is not working, the whole road is pitch dark after sunset.")
    unrelated = _create(client, resident, incident_type="medical", title="Neighbour fainted",
                        description="An elderly neighbour fainted in the lift and needs a doctor.")

    similar = client.get(f"{API}/incidents/{a['id']}/similar", headers=responder)
    assert similar.status_code == 200
    ids = [s["id"] for s in similar.json()]
    assert ids[0] == b["id"] and similar.json()[0]["same_location"] is True   # same address ranks first
    assert unrelated["id"] not in ids
    assert client.get(f"{API}/incidents/{a['id']}/similar", headers=resident).status_code == 403


least_privilege_only = pytest.mark.skipif(
    not settings.DB2_SCHEMA or settings.DB2_SCHEMA.upper() == settings.DB2_USER.upper(),
    reason="requires the least-privilege Db2 login (DB2_USER=nsinapp, DB2_SCHEMA=DB2INST1)",
)


@least_privilege_only
@pytest.mark.parametrize("statement", [
    "CREATE TABLE nsin_probe (id INTEGER)",
    "DROP TABLE incidents",
    "ALTER TABLE incidents ADD COLUMN probe INTEGER",
    "UPDATE audit_events SET action = 'tampered'",
    "DELETE FROM audit_events",
])
def test_least_privilege_login_is_denied_ddl_and_audit_tampering(statement):
    from sqlalchemy.exc import DBAPIError
    with db_base.engine.connect() as conn:
        with pytest.raises(DBAPIError) as err:
            conn.execute(text(statement))
            conn.commit()
        conn.rollback()
    assert "SQL0551N" in str(err.value) or "SQL0552N" in str(err.value), str(err.value)[:300]
