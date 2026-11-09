"""Phase 01B dashboard endpoints against a REAL IBM Db2 (no database mocks).

`/api/overview` is compared with independent SQL executed by the test itself, so the figures the
UI shows are proven to come from Db2 rather than from application constants.
"""

import json
from datetime import timedelta

import pytest

from civiclens.agent.tools import TOOL_NAMES
from civiclens.api import deps
from civiclens.db import repository as repo
from tests.conftest import db2_enabled
from tests.integration.test_investigations_live import (  # noqa: F401  (fixtures are imported)
    CREATOR,
    REV1,
    REV2,
    api,
    cluster,
    db,
    new_inv,
    propose,
)

pytestmark = [
    pytest.mark.db2,
    pytest.mark.skipif(not db2_enabled(), reason="set CIVICLENS_DB2_TESTS=1 to run live Db2 tests"),
]


def scalar(conn, sql, params=()):
    return int(conn.fetch_one(sql, params)["n"])


def grouped(conn, sql):
    return {r["k"]: int(r["n"]) for r in conn.fetch_all(sql)}


def test_me_reports_each_callers_role(api):  # noqa: F811
    client, hdr = api
    assert client.get("/api/me", headers=hdr["pytest-ana"]).json()["role"] == "analyst"
    me = client.get("/api/me", headers=hdr[REV1]).json()
    assert (
        me["user_id"] == REV1 and me["role"] == "reviewer" and "recommendation:decide" in me["capabilities"]
    )


def test_health_endpoints_reveal_nothing_about_the_server(api):  # noqa: F811
    client, _ = api
    for path in ("/api/health", "/api/health/db"):
        r = client.get(path)
        assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_overview_matches_independent_sql(api, db):  # noqa: F811
    client, hdr = api
    cluster(db, 4)  # make sure there is something besides the seeded demo data
    o = client.get("/api/overview", headers=hdr[REV1]).json()

    c = o["complaints"]
    assert c["total"] == scalar(db, "SELECT COUNT(*) AS N FROM {schema}.COMPLAINTS")
    assert c["synthetic"] == scalar(
        db, "SELECT COUNT(*) AS N FROM {schema}.COMPLAINTS WHERE IS_SYNTHETIC = 1"
    )
    assert c["real"] == c["total"] - c["synthetic"]
    sql_cat = grouped(db, "SELECT CATEGORY AS K, COUNT(*) AS N FROM {schema}.COMPLAINTS GROUP BY CATEGORY")
    assert {x["category"]: x["count"] for x in c["by_category"]} == sql_cat
    assert [x["count"] for x in c["by_category"]] == sorted(
        (x["count"] for x in c["by_category"]), reverse=True
    )
    sql_sev = grouped(db, "SELECT SEVERITY AS K, COUNT(*) AS N FROM {schema}.COMPLAINTS GROUP BY SEVERITY")
    assert {x["severity"]: x["count"] for x in c["by_severity"]} == {
        s: sql_sev.get(s, 0) for s in range(1, 6)
    }
    assert sum(x["count"] for x in c["by_status"]) == c["total"]

    # trend: 30 consecutive UTC days ending today; the sum equals what Db2 counts for that window
    assert len(c["trend"]) == c["trend_days"] == 30
    today = repo.utcnow().date()
    assert c["trend"][-1]["date"] == today.isoformat()
    assert c["trend"][0]["date"] == (today - timedelta(days=29)).isoformat()
    first = f"{c['trend'][0]['date']} 00:00:00"
    in_window = scalar(
        db,
        "SELECT COUNT(*) AS N FROM {schema}.COMPLAINTS WHERE REPORTED_AT >= CAST(? AS TIMESTAMP)",
        (first,),
    )
    assert sum(p["count"] for p in c["trend"]) == in_window

    inv = o["investigations"]
    sql_inv = grouped(db, "SELECT STATUS AS K, COUNT(*) AS N FROM {schema}.INVESTIGATIONS GROUP BY STATUS")
    assert {k: v for k, v in inv["by_status"].items() if v} == sql_inv
    assert inv["total"] == sum(sql_inv.values())
    assert inv["active"] == sum(sql_inv.get(s, 0) for s in ("OPEN", "RUNNING", "PENDING_REVIEW"))

    rec = o["recommendations"]
    sql_rs = grouped(db, "SELECT STATUS AS K, COUNT(*) AS N FROM {schema}.RECOMMENDATIONS GROUP BY STATUS")
    sql_rg = grouped(
        db, "SELECT GENERATOR_TYPE AS K, COUNT(*) AS N FROM {schema}.RECOMMENDATIONS GROUP BY GENERATOR_TYPE"
    )
    assert {k: v for k, v in rec["by_status"].items() if v} == sql_rs
    assert {k: v for k, v in rec["by_generator"].items() if v} == sql_rg
    assert rec["pending_review"] == sql_rs.get("PROPOSED", 0) and rec["total"] == sum(sql_rs.values())

    now = repo.utcnow()
    everything = repo.hotspots(db, since=now - timedelta(days=30), until=now, min_count=3, limit=100)
    got = o["hotspots"]
    assert (got["window_days"], got["min_count"]) == (30, 3)
    assert got["total"] == len(everything)  # the true count, not just the 5 listed
    assert len(got["items"]) == min(5, len(everything))
    assert [(h["geo_cell"], h["category"], h["complaint_count"]) for h in got["items"]] == [
        (h.geo_cell, h.category.value, h.complaint_count) for h in everything[:5]
    ]

    sysinfo = o["system"]
    assert sysinfo["database"]["product"].startswith("DB2") and sysinfo["database"]["version"]
    assert sysinfo["database"]["schema_name"] == db.schema
    assert sysinfo["llm"] == {"configured": False, "provider": "none", "model": None, "problem": None}
    assert sysinfo["agent"]["tools"] == list(TOOL_NAMES)
    blob = json.dumps(o)  # nothing that could identify or unlock the server is serialised
    for secret in ("db2inst1", "localhost", "50000", "PWD="):
        assert secret not in blob


def test_overview_reflects_the_workflow_as_it_happens(api, db):  # noqa: F811
    client, hdr = api
    ana, rev = hdr["pytest-ana"], hdr[REV1]

    def snap():
        o = client.get("/api/overview", headers=ana).json()
        return o["complaints"], o["investigations"], o["recommendations"]

    c0, i0, r0 = snap()
    made = client.post(
        "/api/complaints",
        headers=ana,
        json={"category": "DRAINAGE", "title": "[SYNTHETIC] drain overflow", "description": "[SYNTHETIC] pytest",
              "latitude": 12.5, "longitude": 70.5, "severity": 5, "source": "PYTEST", "is_synthetic": True},
    )  # fmt: skip
    assert made.status_code == 201
    cid = made.json()["complaint"]["complaint_id"]
    c1, _, _ = snap()
    assert (c1["total"], c1["synthetic"]) == (c0["total"] + 1, c0["synthetic"] + 1)
    assert c1["by_severity"][4]["count"] == c0["by_severity"][4]["count"] + 1
    assert c1["trend"][-1]["count"] == c0["trend"][-1]["count"] + 1

    inv_id = client.post(
        "/api/investigations",
        headers=ana,
        json={"title": "Overview flow", "question": "Does the overview move?"},
    ).json()["investigation_id"]
    _, i1, _ = snap()
    assert (i1["total"], i1["active"], i1["by_status"]["OPEN"]) == (
        i0["total"] + 1,
        i0["active"] + 1,
        i0["by_status"]["OPEN"] + 1,
    )

    assert (
        client.post(
            f"/api/investigations/{inv_id}/evidence", headers=ana, json={"complaint_ids": [cid]}
        ).status_code
        == 200
    )
    made_rec = client.post(
        f"/api/investigations/{inv_id}/recommendations",
        headers=ana,
        json={"summary": "Clear the drain", "rationale": "One severe overflow reported.", "priority": 2,
              "confidence": 0.5, "evidence_ids": [cid]},
    )  # fmt: skip
    assert made_rec.status_code == 201
    _, i2, r2 = snap()
    assert i2["by_status"]["PENDING_REVIEW"] == i1["by_status"]["PENDING_REVIEW"] + 1
    assert (r2["total"], r2["pending_review"], r2["by_generator"]["MANUAL"]) == (
        r0["total"] + 1, r0["pending_review"] + 1, r0["by_generator"]["MANUAL"] + 1)  # fmt: skip

    rec_id = made_rec.json()["recommendation_id"]
    assert (
        client.post(
            f"/api/recommendations/{rec_id}/decision", headers=rev, json={"decision": "APPROVED"}
        ).status_code
        == 200
    )
    _, i3, r3 = snap()
    assert (r3["pending_review"], r3["by_status"]["APPROVED"]) == (
        r0["pending_review"],
        r0["by_status"]["APPROVED"] + 1,
    )
    assert i3["active"] == i0["active"] and i3["by_status"]["CLOSED"] == i0["by_status"]["CLOSED"] + 1


def test_recommendation_list_filters_context_and_ordering(api, db):  # noqa: F811
    client, hdr = api
    rev = hdr[REV1]
    inv_a, inv_b = new_inv(db), new_inv(db)
    pending = propose(db, inv_a.investigation_id, cluster(db, 3))
    decided = propose(db, inv_b.investigation_id, cluster(db, 3, lat=12.3012))
    assert (
        client.post(
            f"/api/recommendations/{decided}/decision",
            headers=rev,
            json={"decision": "REJECTED", "comment": "Duplicate work"},
        ).status_code
        == 200
    )

    def ids(**params):
        r = client.get("/api/recommendations", headers=rev, params=params)
        assert r.status_code == 200, r.text
        return [x["recommendation_id"] for x in r.json()], r.json()

    queue, items = ids(status="PROPOSED", limit=100)
    assert pending in queue and decided not in queue
    item = next(x for x in items if x["recommendation_id"] == pending)
    assert item["investigation_title"] == "pytest inv" and item["investigation_created_by"] == CREATOR
    assert (
        item["investigation_status"] == "PENDING_REVIEW"
        and item["generator_type"] == "MANUAL"
        and item["evidence_ids"]
    )

    rejected, rej_items = ids(status="REJECTED", limit=100)
    assert decided in rejected
    assert next(x for x in rej_items if x["recommendation_id"] == decided)["review"]["reviewer"] == REV1

    assert {pending, decided} <= set(ids(generator="MANUAL", limit=100)[0])
    assert not {pending, decided} & set(ids(generator="LLM", limit=100)[0])
    assert ids(investigation_id=inv_a.investigation_id)[0] == [pending]

    everything, _ = ids(limit=100)  # pending always sorts ahead of decided
    assert everything.index(pending) < everything.index(decided)

    assert client.get("/api/recommendations", headers=rev, params={"limit": 0}).status_code == 422
    assert client.get("/api/recommendations", headers=rev, params={"limit": 101}).status_code == 422
    assert client.get("/api/recommendations", headers=rev, params={"status": "NOPE"}).status_code == 422
    assert client.get("/api/recommendations").status_code == 401


def test_intake_is_analyst_only_and_the_synthetic_flag_round_trips(api, db):  # noqa: F811
    client, hdr = api
    body = {"category": "SEWAGE", "title": "[SYNTHETIC] overflow", "description": "[SYNTHETIC] pytest",
            "latitude": 12.7, "longitude": 70.7, "source": "PYTEST", "is_synthetic": True}  # fmt: skip
    assert client.post("/api/complaints", json=body, headers=hdr[REV1]).status_code == 403
    ok = client.post("/api/complaints", json=body, headers=hdr["pytest-ana"])
    assert ok.status_code == 201 and ok.json()["complaint"]["is_synthetic"] is True
    listed = client.get(
        "/api/complaints", params={"synthetic": "true", "category": "SEWAGE", "limit": 200}
    ).json()
    assert ok.json()["complaint"]["complaint_id"] in [x["complaint_id"] for x in listed]


def test_authentication_happens_before_any_database_connection(api, monkeypatch):  # noqa: F811
    client, hdr = api
    calls = []
    real_connect = deps.connect

    def counting_connect(*a, **k):
        calls.append(1)
        return real_connect(*a, **k)

    monkeypatch.setattr(deps, "connect", counting_connect)
    assert client.get("/api/overview").status_code == 401
    assert client.get("/api/overview", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.post("/api/complaints", json={}, headers=hdr[REV1]).status_code == 403
    assert calls == [], "an unauthenticated or unauthorised request opened a Db2 connection"
    assert client.get("/api/overview", headers=hdr["pytest-ana"]).status_code == 200
    assert calls == [1]
