"""API endpoint, approval-workflow, security and evidence tests."""
from app.services.bootstrap import SAMPLE_LAB_REPORT

from .conftest import ANALYST, MANAGER, VIEWER

P = "/api/v1"


def test_health_labels_engine(client):
    r = client.get(f"{P}/health")
    assert r.status_code == 200
    body = r.json()
    assert body["database"]["connected"] is True
    assert body["ai"]["mode"] == "DETERMINISTIC_FALLBACK"
    assert r.headers["X-Data-Engine"] in ("IBM-Db2", "DEV-MODE-NOT-DB2")


def test_dashboard_summary(client):
    k = client.get(f"{P}/dashboard/summary", headers=VIEWER).json()["kpis"]
    assert k["total_incidents"] >= 2 and k["completed_recalls"] >= 1


def test_incident_validation_and_errors(client):
    assert client.post(f"{P}/incidents", json={"title": "x"}, headers=ANALYST).status_code == 422
    bad = {"title": "Unknown lot test", "source_ref": "NOP-2026-999", "contaminant": "Salmonella", "contamination_category": "MICROBIAL", "severity": "HIGH"}
    assert client.post(f"{P}/incidents", json=bad, headers=ANALYST).status_code == 404
    bad["source_ref"] = "TOM'; DROP TABLE x;--"
    assert client.post(f"{P}/incidents", json=bad, headers=ANALYST).status_code == 422
    assert client.get(f"{P}/incidents/INC-NOPE", headers=VIEWER).status_code == 404


def test_rbac(client):
    body = {"title": "Viewer cannot create", "source_ref": "TOM-2026-042", "contaminant": "Salmonella", "contamination_category": "MICROBIAL", "severity": "LOW"}
    assert client.post(f"{P}/incidents", json=body, headers=VIEWER).status_code == 403
    assert client.get(f"{P}/incidents", headers={"X-User-Id": "x", "X-User-Role": "hacker"}).status_code == 403


def test_supplier_contacts_redacted_for_viewer(client):
    v = client.get(f"{P}/supply-chain/catalog", headers=VIEWER).json()["suppliers"][0]
    m = client.get(f"{P}/supply-chain/catalog", headers=MANAGER).json()["suppliers"][0]
    assert v["contact_email"] == "[restricted]" and "@" in m["contact_email"]


def test_trace_and_impact_endpoints(client):
    imp = client.get(f"{P}/supply-chain/impact/TOM-2026-041", headers=VIEWER).json()
    assert imp["summary"]["retailers"] == 19
    g = client.get(f"{P}/supply-chain/trace/PB-2026-1007", headers=VIEWER).json()
    assert g["root"]["ref"] == "PB-2026-1007" and len(g["nodes"]) > 5
    assert client.get(f"{P}/supply-chain/trace/NOPE-1", headers=VIEWER).status_code == 404


def test_upload_validation(client):
    r = client.post(f"{P}/evidence/upload", files={"file": ("evil.exe", b"MZ...", "application/octet-stream")}, headers=ANALYST)
    assert r.status_code == 422
    r = client.post(f"{P}/evidence/upload", files={"file": ("fake.pdf", b"not a pdf", "application/pdf")}, headers=ANALYST)
    assert r.status_code == 422
    assert client.post(f"{P}/evidence/upload", files={"file": ("x.txt", b"hello lab", "text/plain")}, headers=VIEWER).status_code == 403


def test_full_human_in_the_loop_workflow(client):
    body = {"title": "API workflow test on TOM-2026-041", "source_ref": "tom-2026-041", "contaminant": "Salmonella Typhimurium",
            "contamination_category": "MICROBIAL", "severity": "CRITICAL", "is_demo": True}
    inc = client.post(f"{P}/incidents", json=body, headers=ANALYST)
    assert inc.status_code == 201
    iid = inc.json()["incident_id"]
    assert inc.json()["source_ref"] == "TOM-2026-041" and inc.json()["incident_status"] == "REPORTED"

    up = client.post(f"{P}/evidence/upload", data={"incident_id": iid, "doc_type": "LAB_REPORT"},
                     files={"file": ("api_" + SAMPLE_LAB_REPORT.name, SAMPLE_LAB_REPORT.read_bytes() + b"\n%api", "application/pdf")}, headers=ANALYST)
    assert up.status_code == 201
    assert "TOM-2026-041" in up.json()["extracted"]["summary"]["lot_ids"]

    # recall cannot be generated before investigation
    assert client.post(f"{P}/recalls/generate", json={"incident_id": iid}, headers=ANALYST).status_code == 409

    run = client.post(f"{P}/incidents/{iid}/investigate?background=false", headers=ANALYST)
    assert run.status_code == 202
    inv = client.get(f"{P}/incidents/{iid}/investigation", headers=VIEWER).json()
    assert inv["status"] == "COMPLETED" and len(inv["agents"]) == 5
    assert inv["mode"] == "DETERMINISTIC_FALLBACK" and "NOT an LLM" in inv["mode_note"]
    assert all(a["log"] for a in inv["agents"])

    rc = client.post(f"{P}/recalls/generate", json={"incident_id": iid}, headers=ANALYST)
    assert rc.status_code == 201
    rid = rc.json()["recall_id"]
    assert rc.json()["recall_status"] == "PENDING_APPROVAL"
    assert client.get(f"{P}/incidents/{iid}", headers=VIEWER).json()["incident_status"] == "PENDING_APPROVAL"

    # analysts cannot approve; rejection needs a comment
    assert client.post(f"{P}/recalls/{rid}/approve", json={"comment": "ok"}, headers=ANALYST).status_code == 403
    assert client.post(f"{P}/recalls/{rid}/reject", json={"comment": ""}, headers=MANAGER).status_code == 409

    ok = client.post(f"{P}/recalls/{rid}/approve", json={"comment": "Approved after evidence review"}, headers=MANAGER)
    assert ok.status_code == 200
    data = ok.json()
    assert data["recall_status"] == "EXECUTING" and data["decided_by"] == "manager@test"
    assert data["actions"] and all(a["channel"] == "SIMULATED" for a in data["actions"])
    assert client.post(f"{P}/recalls/{rid}/approve", json={"comment": "again"}, headers=MANAGER).status_code == 409

    sim = client.post(f"{P}/recalls/{rid}/simulate-acknowledgements", headers=MANAGER).json()
    assert sim["progress"]["acknowledged"] > 0
    # cannot complete while actions are open
    assert client.post(f"{P}/recalls/{rid}/complete", json={"comment": ""}, headers=MANAGER).status_code == 409

    logs = client.get(f"{P}/audit-logs", params={"entity_ref": iid}, headers=VIEWER).json()
    actions = {l["action_name"] for l in logs}
    assert {"INCIDENT_CREATED", "INVESTIGATION_STARTED", "INCIDENT_STATUS_CHANGED"} <= actions
    rlogs = {l["action_name"] for l in client.get(f"{P}/audit-logs", params={"entity_ref": rid}, headers=VIEWER).json()}
    assert {"RECALL_GENERATED", "RECALL_APPROVED", "RECALL_NOTIFICATIONS_SENT"} <= rlogs


def test_reject_and_reinvestigate(client):
    body = {"title": "Reject path test", "source_ref": "PB-2026-1031", "contaminant": "Metal fragments",
            "contamination_category": "PHYSICAL", "severity": "MEDIUM", "is_demo": True}
    iid = client.post(f"{P}/incidents", json=body, headers=ANALYST).json()["incident_id"]
    client.post(f"{P}/incidents/{iid}/investigate?background=false", headers=ANALYST)
    rid = client.post(f"{P}/recalls/generate", json={"incident_id": iid}, headers=ANALYST).json()["recall_id"]
    r = client.post(f"{P}/recalls/{rid}/reject", json={"comment": "No lab confirmation; gather evidence"}, headers=MANAGER)
    assert r.status_code == 200 and r.json()["recall_status"] == "REJECTED"
    assert client.get(f"{P}/incidents/{iid}", headers=VIEWER).json()["incident_status"] == "REJECTED"
    re = client.post(f"{P}/incidents/{iid}/reinvestigate", json={"reason": "new samples"}, headers=ANALYST)
    assert re.status_code == 202


def test_evidence_search_returns_citations(client):
    r = client.get(f"{P}/evidence/search", params={"q": "Salmonella detected tomato puree"}, headers=VIEWER).json()
    assert r["results"] and "p." in r["results"][0]["citation"]
    assert r["engine"]


def test_demo_endpoint_and_reset(client):
    d = client.post(f"{P}/demo/tomato", headers=ANALYST)
    assert d.status_code == 201
    out = d.json()
    assert [s["step"] for s in out["steps"]] == ["incident_registered", "lab_report_uploaded", "investigation_completed", "recall_generated"]
    rc = client.get(f"{P}/recalls/{out['recall_id']}", headers=VIEWER).json()
    assert rc["verification"]["verdict"] in ("PASS", "PASS_WITH_WARNINGS")
    reset = client.post(f"{P}/demo/reset", headers=MANAGER).json()
    assert out["incident_id"] in reset["removed_incidents"]
    assert client.get(f"{P}/incidents/{out['incident_id']}", headers=VIEWER).status_code == 404
