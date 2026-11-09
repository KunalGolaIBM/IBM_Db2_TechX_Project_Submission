"""Integration tests against a REAL IBM Db2 server. No mocks.

Enable with:  CIVICLENS_DB2_TESTS=1 DB2_PASSWORD=... pytest -m db2
Rows created here are marked IS_SYNTHETIC=1 / SOURCE='PYTEST' and deleted afterwards.
"""

import secrets
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from civiclens.agent.tools import CivicLensToolkit
from civiclens.api.main import create_app
from civiclens.config import get_settings
from civiclens.db import repository as repo
from civiclens.db.connection import session
from civiclens.db.migrate import migrate
from civiclens.domain.models import Category, ComplaintCreate
from tests.conftest import db2_enabled

pytestmark = [
    pytest.mark.db2,
    pytest.mark.skipif(not db2_enabled(), reason="set CIVICLENS_DB2_TESTS=1 to run live Db2 tests"),
]


@pytest.fixture()
def db():
    with session() as s:
        migrate(s)
        yield s
        s.execute("DELETE FROM {schema}.COMPLAINTS WHERE SOURCE = 'PYTEST'")


def _complaint(**kw):
    base = dict(
        category=Category.STREETLIGHT,
        title="Streetlight out near school",
        description="[SYNTHETIC] pytest record",
        latitude=27.4801,
        longitude=77.6601,
        ward="Test Ward",
        severity=3,
        source="PYTEST",
        is_synthetic=True,
    )
    return ComplaintCreate(**{**base, **kw})


def test_migration_is_idempotent(db):
    result = migrate(db)
    assert result["created"] == []
    assert "TABLE CIVICLENS.COMPLAINTS" in result["skipped"] or any(
        "COMPLAINTS" in x for x in result["skipped"]
    )


def test_insert_read_roundtrip(db):
    cid = repo.insert_complaint(db, _complaint())
    c = repo.get_complaint(db, cid)
    assert c is not None and c.category is Category.STREETLIGHT and c.is_synthetic
    assert c.latitude == pytest.approx(27.4801)


def test_injection_strings_are_stored_literally(db):
    evil = "x'); DROP TABLE CIVICLENS.COMPLAINTS; --"
    cid = repo.insert_complaint(db, _complaint(title=evil, ward="W' OR '1'='1"))
    assert repo.get_complaint(db, cid).title == evil
    assert repo.list_complaints(db, ward="W' OR '1'='1", limit=5)[0].complaint_id == cid
    assert (
        db.fetch_one(
            "SELECT COUNT(*) AS N FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = 'COMPLAINTS'",
            (db.schema,),
        )["n"]
        == 1
    )


def test_check_constraint_enforced_by_db2(db):
    with pytest.raises(Exception, match="SQL0545N"):
        db.execute(
            "INSERT INTO {schema}.COMPLAINTS (CATEGORY, TITLE, DESCRIPTION, LATITUDE, LONGITUDE, "
            "GEO_CELL, SEVERITY, SOURCE, TEXT_FINGERPRINT, REPORTED_AT) VALUES "
            "('POTHOLE','t','d',0,0,'C0_0',9,'PYTEST','f',CURRENT TIMESTAMP)"
        )


def test_duplicate_detection_uses_db2_distance(db):
    a = repo.insert_complaint(db, _complaint())
    near = _complaint(latitude=27.4802, longitude=77.6602, title="Streetlight not working near school")
    far = _complaint(latitude=27.5801, longitude=77.6601)
    b = repo.insert_complaint(db, near)
    repo.insert_complaint(db, far)
    cands = repo.find_duplicate_candidates(
        db,
        category=near.category,
        title=near.title,
        description=near.description,
        latitude=near.latitude,
        longitude=near.longitude,
        exclude_id=b,
    )
    ids = [c.complaint_id for c in cands]
    assert a in ids
    match = next(c for c in cands if c.complaint_id == a)
    assert 5 < match.distance_m < 30


def test_transaction_rollback(db):
    ref = f"TX-{uuid.uuid4().hex[:8]}"
    with pytest.raises(RuntimeError):
        with db.transaction():
            repo.insert_complaint(db, _complaint(external_ref=ref))
            raise RuntimeError("abort")
    assert db.fetch_one("SELECT 1 AS X FROM {schema}.COMPLAINTS WHERE EXTERNAL_REF = ?", (ref,)) is None


def test_agent_tools_hit_db2_and_write_audit_rows(db):
    inv = repo.create_investigation(
        db, title="pytest", question="Where are streetlight issues?", created_by="pytest"
    )
    cid = repo.insert_complaint(db, _complaint())
    tools = {t.name: t for t in CivicLensToolkit(db, investigation_id=inv).tools()}
    out = tools["get_complaint"].invoke({"complaint_id": cid})
    assert out["ok"] and out["data"]["complaint_id"] == cid
    out = tools["hotspot_summary"].invoke({"days": 1, "min_count": 2, "category": "STREETLIGHT"})
    assert out["ok"]
    audit = repo.list_audit(db, investigation_id=inv)
    assert [a["tool_name"] for a in audit] == ["get_complaint", "hotspot_summary"]
    assert (
        audit[0]["output_summary"] == f"complaint #{cid} (STREETLIGHT) returned"
    )  # readable, not a JSON dump
    # AUDIT_LOG has no foreign key to INVESTIGATIONS, so clean both (no orphaned audit rows)
    db.execute("DELETE FROM {schema}.AUDIT_LOG WHERE INVESTIGATION_ID = ?", (inv,))
    db.execute("DELETE FROM {schema}.INVESTIGATIONS WHERE INVESTIGATION_ID = ?", (inv,))


def test_api_end_to_end(db, monkeypatch):
    # Phase 01B: complaint intake requires an analyst token and /api/health/db reveals nothing.
    token = secrets.token_hex(16)
    monkeypatch.setenv("CIVICLENS_AUTH_TOKENS", f"pytest-ana:analyst:{token}")
    get_settings.cache_clear()  # the db fixture already cached settings
    auth = {"Authorization": f"Bearer {token}"}
    client = TestClient(create_app())
    h = client.get("/api/health/db")
    assert h.status_code == 200 and h.json() == {"status": "ok"}
    payload = _complaint().model_dump(mode="json")
    assert client.post("/api/complaints", json=payload).status_code == 401  # anonymous intake is refused
    r = client.post("/api/complaints", json=payload, headers=auth)
    assert r.status_code == 201
    cid = r.json()["complaint"]["complaint_id"]
    r2 = client.post("/api/complaints", json=payload, headers=auth)
    assert cid in [c["complaint_id"] for c in r2.json()["duplicate_candidates"]]
    assert client.get(f"/api/complaints/{cid}").json()["title"] == payload["title"]
    assert client.get("/api/complaints/999999999").status_code == 404
    assert client.get("/api/complaints", params={"category": "STREETLIGHT", "limit": 5}).status_code == 200
    # the audit trail attributes intake to the authenticated user, not a hardcoded "api"
    row = db.fetch_one(
        "SELECT ACTOR_ID FROM {schema}.AUDIT_LOG WHERE ACTION = 'COMPLAINT_CREATED' ORDER BY AUDIT_ID DESC"
    )
    assert row["actor_id"] == "pytest-ana"


def test_hotspots_over_seeded_synthetic_data(db):
    spots = repo.hotspots(db, since=repo.utcnow() - timedelta(days=30), min_count=3)
    if not spots:
        pytest.skip("synthetic data not seeded (run scripts/seed_synthetic.py)")
    assert spots[0].complaint_count >= spots[-1].complaint_count
