"""Db2Repository against the live IBM Db2 test schema."""

import time
import uuid

import pytest

from shipsafe.db2.repository import Db2Repository, _safe_err, connect_db2
from shipsafe.models import Assessment, Finding, ToolRun


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _assessment(project_id: str, status: str = "BLOCKED", started: int = None, crit: int = 1, high: int = 0) -> Assessment:
    now = started or int(time.time() * 1000)
    return Assessment(assessment_id=_uid("asm"), project_id=project_id, commit_sha="abc123", base_sha=None,
                      profile="pre-pr", status=status, gate_reason="test", started_at=now, finished_at=now + 10,
                      findings_count=crit + high, critical_count=crit, high_count=high)


def test_schema_objects_exist(repo):
    st = repo.check_connection()
    assert st["engine"] == "IBM Db2" and st["connected"]
    assert st["schema"] == repo.schema
    assert st["tables_in_schema"] >= 11
    assert st["views_in_schema"] == 2
    for proc in ("SP_PROJECT_RISK", "SP_PURGE_HISTORY", "SP_GUARD_SUMMARY"):
        assert repo._procedure_exists(proc)


def test_initialize_schema_is_idempotent(repo):
    assert repo.initialize_schema() == []
    replaced = repo.initialize_schema(replace_views=True)
    assert {"V_RISK_TREND", "V_PROJECT_POSTURE", "SP_PROJECT_RISK"} <= set(replaced)


def test_invalid_schema_identifier_is_rejected(config):
    from dataclasses import replace

    with pytest.raises(ValueError):
        Db2Repository(replace(config.db2, schema="BAD;DROP"), init_schema=False)


def test_connect_failure_is_reported_without_password(config):
    from dataclasses import replace

    bad = replace(config.db2, port=1, password="s3cret-value")
    with pytest.raises(ConnectionError) as err:
        connect_db2(bad, retries=1)
    assert "s3cret-value" not in str(err.value)
    assert _safe_err(Exception("x PWD=abc; y")) == "x PWD=***; y"


def test_bundle_roundtrip_and_queries(repo):
    pid = _uid("prj")
    a = _assessment(pid)
    f = Finding.create(a.assessment_id, "shipsafe_secrets_scanner", "SEC-001", "secrets", "critical", "high",
                       "AWS Access Key ID Detected", "desc", file_path="src/api.py", line_start=7,
                       evidence={"snippet": "[REDACTED_AWS_KEY]"})
    tr = ToolRun(f"{a.assessment_id}_secrets", a.assessment_id, "secrets", "1", 1, 5, "failed", "1 issue")
    repo.save_assessment_bundle(project={"project_id": pid, "repo_root_hash": "h", "name": "Demo"},
                                dependencies=[{"name": "pyyaml", "version": "5.3", "manifest": "requirements.txt"}],
                                assessment=a, tool_runs=[tr], findings=[f])
    got = repo.get_assessment(a.assessment_id)
    assert got["STATUS"] == "BLOCKED" and got["PROJECT_NAME"] == "Demo"
    assert repo.get_finding(f.finding_id)["EVIDENCE"]["snippet"] == "[REDACTED_AWS_KEY]"
    assert repo.get_finding("missing") is None
    assert repo.get_assessment("missing") is None
    assert repo.get_findings(a.assessment_id)[0]["RULE_ID"] == "SEC-001"
    assert repo.get_tool_runs(a.assessment_id)[0]["TOOL_NAME"] == "secrets"
    assert repo.get_dependencies(pid)[0]["PACKAGE_NAME"] == "pyyaml"
    assert any(r["ASSESSMENT_ID"] == a.assessment_id for r in repo.list_assessments(project_id=pid))
    assert len(repo.list_assessments(limit=1, offset=0)) == 1
    assert repo.get_assessment_history(project_id=pid)[0]["RISK_SCORE"] == 10
    assert any(p["PROJECT_ID"] == pid for p in repo.project_posture())
    assert any(r["CATEGORY"] == "secrets" for r in repo.severity_breakdown())
    stats = repo.overview_stats()
    assert stats["assessments"] >= 1 and stats["open_critical"] >= 1


def test_bundle_is_atomic(repo):
    pid = _uid("prj")
    a = _assessment(pid)
    bad = Finding.create(a.assessment_id, "t", "R", "security", "critical", "high", "x", "d")
    bad.severity = "x" * 100  # longer than VARCHAR(16): Db2 rejects the insert
    with pytest.raises(Exception):
        repo.save_assessment_bundle(project={"project_id": pid, "repo_root_hash": "h", "name": "Atomic"},
                                    dependencies=[], assessment=a, tool_runs=[], findings=[bad])
    assert repo.get_assessment(a.assessment_id) is None
    assert not repo.list_assessments(project_id=pid)


def test_compare_assessments_persists_diff(repo):
    pid = _uid("prj")
    a1, a2 = _assessment(pid), _assessment(pid)
    repo.save_project(pid, "h", "Diff")
    repo.save_assessment(a1)
    repo.save_assessment(a2)
    fa = Finding.create(a1.assessment_id, "bandit", "B608", "security", "critical", "high", "Issue A", "d")
    fb = Finding.create(a1.assessment_id, "bandit", "B602", "security", "high", "high", "Issue B", "d")
    fb2 = Finding.create(a2.assessment_id, "bandit", "B602", "security", "high", "high", "Issue B", "d")
    fc = Finding.create(a2.assessment_id, "bandit", "B307", "security", "critical", "high", "Issue C", "d")
    repo.save_findings([fa, fb, fb2, fc])
    diff = repo.compare_assessments(a1.assessment_id, a2.assessment_id)
    assert (diff["new_count"], diff["resolved_count"], diff["unchanged_count"]) == (1, 1, 1)
    rows = repo._query("SELECT CHANGE_TYPE FROM ASSESSMENT_DIFFS WHERE CURRENT_ID = ?", (a2.assessment_id,))
    assert sorted(r["CHANGE_TYPE"] for r in rows) == ["new", "resolved", "unchanged"]


def test_tokens_and_audit(repo):
    tid = _uid("tok")[:32]
    digest = uuid.uuid4().hex + uuid.uuid4().hex
    repo.create_token(tid, "tester", "operator", digest)
    assert repo.find_token(digest)["ROLE"] == "operator"
    repo.touch_token(tid)
    assert any(t["TOKEN_ID"] == tid for t in repo.list_tokens())
    assert repo.revoke_token(tid) is True
    assert repo.revoke_token("nope") is False
    assert repo.find_token("0" * 64) is None
    assert repo.count_active_admins() >= 0
    repo.audit("tester", "test.event", "success", role="operator", target="t", detail="d", client_ip="127.0.0.1")
    repo.audit("x" * 500, "y" * 500, "z" * 500)  # truncated, never raises
    assert repo.list_audit(action="test.event")[0]["ACTOR"] == "tester"


def test_knowledge_docs(repo):
    repo.save_knowledge_doc("DOC-T", "Title", "policies/t.md", "security", "1.0.0", "content", 2)
    repo.save_knowledge_doc("DOC-T", "Title 2", "policies/t.md", "security", "1.0.1", "content", 3)
    docs = {d["DOC_ID"]: d for d in repo.list_knowledge_docs()}
    assert docs["DOC-T"]["TITLE"] == "Title 2"


def test_guard_events_fix_attempts_and_summary_procedure(repo):
    since = int(time.time() * 1000) - 1000
    client = _uid("ide")[:32]
    repo.record_guard_event(client=client, tool="check_code", verdict="block", findings_count=3, duration_ms=12,
                            project="p", file_path="a.py", language="python", max_severity="critical",
                            rule_ids=["SQLI-DYNAMIC", "SEC-001", "SEC-001"])
    repo.record_guard_event(client=client, tool="check_code", verdict="clean", findings_count=0, duration_ms=5)
    repo.record_fix_attempt(model="granite4:micro", iterations=1, verified=True, issues_before=2, issues_after=0,
                            duration_ms=900, patch="--- a\n+++ b\n", file_path="a.py", language="python",
                            rule_ids=["SQLI-DYNAMIC"])
    events = repo.list_guard_events(limit=5)
    assert events[0]["TS"] >= since
    assert any(e["RULE_IDS"] == "SEC-001,SQLI-DYNAMIC" for e in events)
    assert repo.list_fix_attempts(limit=1)[0]["VERIFIED"] == 1
    summary = {r["CLIENT"]: r for r in repo.guard_summary(since)}
    assert summary[client]["CHECKS"] == 2
    assert summary[client]["BLOCKED"] == 1
    assert summary[client]["ISSUES_CAUGHT"] == 3
    assert summary[client]["VERIFIED_FIXES"] >= 1


def test_guard_event_verdict_is_constrained(repo):
    with pytest.raises(Exception):
        repo.record_guard_event(client="c", tool="t", verdict="maybe", findings_count=0, duration_ms=1)
    repo.rollback()


def test_project_risk_procedure_trend(repo):
    pid = _uid("prj")
    assert repo.project_risk(pid) == {"project_id": pid, "risk_score": 0, "risk_delta": 0, "trend": "unknown", "runs": 0}
    repo.save_project(pid, "h", "Risk")
    t = int(time.time() * 1000)
    repo.save_assessment(_assessment(pid, started=t - 2000, crit=2))   # score 20
    assert repo.project_risk(pid)["trend"] == "new"
    repo.save_assessment(_assessment(pid, started=t - 1000, crit=1))   # score 10
    risk = repo.project_risk(pid)
    assert (risk["risk_score"], risk["risk_delta"], risk["trend"], risk["runs"]) == (10, -10, "improving", 2)
    repo.save_assessment(_assessment(pid, started=t, crit=1, high=1))  # score 15
    assert repo.project_risk(pid)["trend"] == "worsening"
    repo.save_assessment(_assessment(pid, started=t + 1, crit=1, high=1))
    assert repo.project_risk(pid)["trend"] == "steady"


def test_purge_history_procedure(repo):
    pid = _uid("prj")
    repo.save_project(pid, "h", "Old")
    old = _assessment(pid, started=int(time.time() * 1000) - 400 * 86_400_000)
    repo.save_assessment(old)
    repo.save_findings([Finding.create(old.assessment_id, "t", "R1", "security", "low", "low", "x", "d")])
    out = repo.purge_history(365)
    assert out["assessments_deleted"] >= 1
    assert repo.get_assessment(old.assessment_id) is None
    assert repo.get_findings(old.assessment_id) == []  # ON DELETE CASCADE
    with pytest.raises(Exception, match="P_KEEP_DAYS"):
        repo.purge_history(0)


def test_ping_and_close(repo):
    assert repo.ping() >= 0
    repo.close()
    repo.close()  # second close is harmless
