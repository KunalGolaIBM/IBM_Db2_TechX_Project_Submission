"""Phase 01A integration tests against a REAL IBM Db2 server (no database mocks).

The only test double is ScriptedChatModel, used to drive the LLM agent *loop* deterministically;
anything it produces is labelled ``test-double:scripted`` and is not evidence of a real provider.

Enable with:  CIVICLENS_DB2_TESTS=1 (and DB2_* variables).  Test rows use SOURCE='PYTEST' and
users named ``pytest-*``; they are removed after every test.
"""

import json
import secrets
import threading

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage

from civiclens.agent import investigate
from civiclens.agent.llm import LlmHandle
from civiclens.api.main import create_app
from civiclens.config import get_settings
from civiclens.db import investigation_repo as inv_repo
from civiclens.db import repository as repo
from civiclens.db.connection import session
from civiclens.db.migrate import apply_column_upgrades, migrate
from civiclens.domain.errors import (
    AgentError,
    AgentStepLimitError,
    ConflictError,
    ForbiddenError,
    InvalidEvidenceError,
    LlmNotConfiguredError,
)
from civiclens.domain.investigation_models import (
    GeneratorType,
    InvestigationStatus,
    RecommendationDraft,
    RecommendationStatus,
    RunRequest,
)
from civiclens.domain.models import Category, ComplaintCreate
from tests.conftest import db2_enabled
from tests.scripted_llm import ScriptedChatModel, ai_calls, tool_call

pytestmark = [
    pytest.mark.db2,
    pytest.mark.skipif(not db2_enabled(), reason="set CIVICLENS_DB2_TESTS=1 to run live Db2 tests"),
]

CREATOR, REV1, REV2 = "pytest-creator", "pytest-rev", "pytest-rev2"


@pytest.fixture()
def db():
    with session() as s:
        migrate(s)
        yield s
        ids = [r["investigation_id"] for r in s.fetch_all(
            "SELECT INVESTIGATION_ID FROM {schema}.INVESTIGATIONS WHERE CREATED_BY LIKE 'pytest-%'")]  # fmt: skip
        for i in ids:
            s.execute("DELETE FROM {schema}.AUDIT_LOG WHERE INVESTIGATION_ID = ?", (i,))
        s.execute("DELETE FROM {schema}.INVESTIGATIONS WHERE CREATED_BY LIKE 'pytest-%'")
        s.execute("DELETE FROM {schema}.COMPLAINTS WHERE SOURCE = 'PYTEST'")


def cluster(db, n=6, category=Category.TRAFFIC_SIGNAL, lat=12.0012, lon=70.0012):
    """n synthetic complaints in one geo-cell (far from the seeded demo area)."""
    return [
        repo.insert_complaint(
            db,
            ComplaintCreate(
                category=category, title=f"[SYNTHETIC] signal fault {i}", ward="Test",
                description="[SYNTHETIC] pytest cluster record", latitude=lat + i * 0.0001,
                longitude=lon, severity=4, source="PYTEST", is_synthetic=True,
            ),
        )
        for i in range(n)
    ]  # fmt: skip


def new_inv(db, created_by=CREATOR):
    return inv_repo.create_investigation(
        db, title="pytest inv", question="Where are signal faults?", created_by=created_by
    )


def draft(ids, **kw):
    base = dict(summary="Inspect signal cluster", rationale="Several complaints in one cell.", priority=2,
                confidence=0.6, evidence_ids=ids)  # fmt: skip
    return RecommendationDraft(**{**base, **kw})


def propose(db, inv_id, ids):
    inv_repo.add_evidence(db, inv_id, ids)
    rid = inv_repo.create_recommendation(
        db, inv_id, draft(ids), generator=GeneratorType.MANUAL, model_name=None, actor_id=CREATOR
    )
    inv_repo.transition_status(db, inv_id, from_statuses=[InvestigationStatus.OPEN],
                               to_status=InvestigationStatus.PENDING_REVIEW)  # fmt: skip
    return rid


# ------------------------------------------------------------------------------ evidence integrity
def test_fabricated_and_unattached_evidence_is_rejected(db):
    ids = cluster(db, 3)
    inv = new_inv(db)
    with pytest.raises(InvalidEvidenceError) as e1:
        inv_repo.add_evidence(db, inv.investigation_id, [ids[0], 999_999_999])
    assert e1.value.code == "UNKNOWN_COMPLAINT_IDS" and e1.value.details["unknown_ids"] == [999_999_999]
    with pytest.raises(InvalidEvidenceError) as e2:  # real complaints, but not attached yet
        inv_repo.create_recommendation(db, inv.investigation_id, draft(ids), generator=GeneratorType.MANUAL,
                                       model_name=None, actor_id=CREATOR)  # fmt: skip
    assert e2.value.code == "EVIDENCE_NOT_ATTACHED"
    with pytest.raises(InvalidEvidenceError) as e3:
        inv_repo.create_recommendation(db, inv.investigation_id, draft([ids[0], 999_999_999]),
                                       generator=GeneratorType.MANUAL, model_name=None, actor_id=CREATOR)  # fmt: skip
    assert e3.value.code == "UNKNOWN_COMPLAINT_IDS"
    assert inv_repo.list_recommendations(db, inv.investigation_id) == []


def test_db2_itself_rejects_evidence_bypassing_the_application(db):
    ids = cluster(db, 2)
    inv, inv2 = new_inv(db), new_inv(db)
    rid = propose(db, inv.investigation_id, [ids[0]])
    inv_repo.add_evidence(db, inv2.investigation_id, [ids[1]])
    # complaint exists and is attached to ANOTHER investigation -> composite FK must refuse it
    with pytest.raises(Exception, match="SQL0530N"):
        db.execute("INSERT INTO {schema}.RECOMMENDATION_EVIDENCE (RECOMMENDATION_ID, INVESTIGATION_ID, "
                   "COMPLAINT_ID) VALUES (?, ?, ?)", (rid, inv.investigation_id, ids[1]))  # fmt: skip
    with pytest.raises(Exception, match="SQL0545N"):  # CHECK list on GENERATOR_TYPE
        db.execute("INSERT INTO {schema}.RECOMMENDATIONS (INVESTIGATION_ID, SUMMARY, RATIONALE, PRIORITY, "
                   "CONFIDENCE, EVIDENCE_IDS, GENERATOR_TYPE, STATUS) VALUES (?, 's', 'r', 1, 0.5, '1', "
                   "'HUMAN', 'PROPOSED')", (inv.investigation_id,))  # fmt: skip


def test_recommendation_always_starts_proposed_with_linked_evidence(db):
    ids = cluster(db, 3)
    inv = new_inv(db)
    rid = propose(db, inv.investigation_id, ids)
    rec = inv_repo.get_recommendation(db, rid)
    assert rec.status is RecommendationStatus.PROPOSED and rec.evidence_ids == sorted(ids)
    assert rec.generator_type is GeneratorType.MANUAL and rec.review is None
    assert (
        inv_repo.require_investigation(db, inv.investigation_id).status is InvestigationStatus.PENDING_REVIEW
    )
    ev = inv_repo.list_evidence(db, inv.investigation_id)
    assert {e.complaint_id for e in ev} == set(ids) and all(e.is_synthetic for e in ev)


# ------------------------------------------------------------------------------ human review
def test_approval_is_atomic_audited_and_closes_the_investigation(db):
    inv = new_inv(db)
    rid = propose(db, inv.investigation_id, cluster(db, 3))
    rec = inv_repo.decide(db, rid, reviewer=REV1, decision="APPROVED", comment="Looks right")
    assert rec.status is RecommendationStatus.APPROVED and rec.review.reviewer == REV1
    assert inv_repo.require_investigation(db, inv.investigation_id).status is InvestigationStatus.CLOSED
    actions = [a.action for a in inv_repo.audit_history(db, inv.investigation_id)]
    assert "REVIEW_APPROVED" in actions and "RECOMMENDATION_PROPOSED" in actions


def test_second_or_conflicting_decision_is_refused(db):
    rid = propose(db, new_inv(db).investigation_id, cluster(db, 3))
    inv_repo.decide(db, rid, reviewer=REV1, decision="APPROVED", comment=None)
    for reviewer, decision in ((REV1, "APPROVED"), (REV2, "REJECTED"), (REV2, "APPROVED")):
        with pytest.raises(ConflictError) as e:
            inv_repo.decide(db, rid, reviewer=reviewer, decision=decision, comment="second try")
        assert e.value.code in ("ALREADY_DECIDED", "INVESTIGATION_NOT_REVIEWABLE")
    n = db.fetch_one(
        "SELECT COUNT(*) AS N FROM {schema}.REVIEW_DECISIONS WHERE RECOMMENDATION_ID = ?", (rid,)
    )
    assert n["n"] == 1
    with pytest.raises(Exception, match="SQL0803N"):  # unique index backstop, bypassing app logic
        db.execute("INSERT INTO {schema}.REVIEW_DECISIONS (RECOMMENDATION_ID, REVIEWER, DECISION) "
                   "VALUES (?, 'x', 'REJECTED')", (rid,))  # fmt: skip


def test_creator_cannot_review_their_own_investigation(db):
    inv = new_inv(db, created_by=REV1)
    rid = propose(db, inv.investigation_id, cluster(db, 3))
    with pytest.raises(ForbiddenError) as e:
        inv_repo.decide(db, rid, reviewer=REV1, decision="APPROVED", comment=None)
    assert e.value.code == "SELF_REVIEW_FORBIDDEN"
    assert inv_repo.get_recommendation(db, rid).status is RecommendationStatus.PROPOSED


def test_failure_mid_decision_rolls_everything_back(db, monkeypatch):
    rid = propose(db, new_inv(db).investigation_id, cluster(db, 3))

    def boom(*a, **k):
        raise RuntimeError("audit write failed")

    monkeypatch.setattr(repo, "write_audit", boom)  # fails AFTER the status UPDATE and decision INSERT
    with pytest.raises(RuntimeError):
        inv_repo.decide(db, rid, reviewer=REV1, decision="APPROVED", comment=None)
    monkeypatch.undo()
    with session() as other:  # a separate connection sees only committed state
        row = other.fetch_one(
            "SELECT STATUS FROM {schema}.RECOMMENDATIONS WHERE RECOMMENDATION_ID = ?", (rid,)
        )
        n = other.fetch_one(
            "SELECT COUNT(*) AS N FROM {schema}.REVIEW_DECISIONS WHERE RECOMMENDATION_ID = ?", (rid,)
        )
    assert row["status"] == "PROPOSED" and n["n"] == 0


def test_the_unique_index_is_a_database_backstop_and_rolls_back_the_status_flip(db):
    """Simulates an application bypass: a decision row already exists for a PROPOSED recommendation. The
    compare-and-set update passes, so only the unique index on REVIEW_DECISIONS stops the second decision; the
    whole transaction, including the status flip, must roll back and leave no audit row."""
    inv = new_inv(db)
    rid = propose(db, inv.investigation_id, cluster(db, 3))
    db.execute(
        "INSERT INTO {schema}.REVIEW_DECISIONS (RECOMMENDATION_ID, REVIEWER, DECISION, COMMENT) "
        "VALUES (?, ?, 'APPROVED', 'planted outside the application')",
        (rid, REV2),
    )
    with pytest.raises(ConflictError) as exc:
        inv_repo.decide(db, rid, reviewer=REV1, decision="REJECTED", comment="must not be stored")
    assert exc.value.code == "ALREADY_DECIDED"
    status = db.fetch_one("SELECT STATUS FROM {schema}.RECOMMENDATIONS WHERE RECOMMENDATION_ID = ?", (rid,))
    assert status["status"] == "PROPOSED"  # the flip to REJECTED was rolled back with the failed insert
    decisions = db.fetch_all(
        "SELECT REVIEWER FROM {schema}.REVIEW_DECISIONS WHERE RECOMMENDATION_ID = ?", (rid,)
    )
    assert [d["reviewer"] for d in decisions] == [REV2]  # only the planted row
    audit = inv_repo.audit_history(db, inv.investigation_id)
    assert not [a for a in audit if a.action.startswith("REVIEW_")]  # the refused decision left no trace


def test_concurrent_decisions_exactly_one_wins(db):
    rid = propose(db, new_inv(db).investigation_id, cluster(db, 3))
    barrier, outcomes = threading.Barrier(2), []

    def attempt(reviewer, decision):
        with session() as conn:  # own Db2 connection per thread
            barrier.wait()
            try:
                inv_repo.decide(conn, rid, reviewer=reviewer, decision=decision, comment="concurrent")
                outcomes.append((reviewer, "won"))
            except ConflictError as exc:
                outcomes.append((reviewer, exc.code))

    ts = [threading.Thread(target=attempt, args=a) for a in ((REV1, "APPROVED"), (REV2, "REJECTED"))]
    [t.start() for t in ts]
    [t.join(timeout=60) for t in ts]
    assert sorted(o for _, o in outcomes).count("won") == 1, outcomes
    assert len(outcomes) == 2
    n = db.fetch_one(
        "SELECT COUNT(*) AS N FROM {schema}.REVIEW_DECISIONS WHERE RECOMMENDATION_ID = ?", (rid,)
    )
    assert n["n"] == 1


# ------------------------------------------------------------------------------ rule-based engine
def test_fallback_run_is_labelled_grounded_and_audited(db):
    ids = cluster(db, 6)
    inv = new_inv(db)
    req = RunRequest(mode="fallback", category=Category.TRAFFIC_SIGNAL, max_hotspots=1)
    res = investigate.run_investigation(db, inv.investigation_id, requested_by=CREATOR, request=req,
                                        settings=get_settings())  # fmt: skip
    assert res.generator is GeneratorType.DETERMINISTIC_FALLBACK and "NO LLM" in res.notice
    assert res.status is InvestigationStatus.PENDING_REVIEW and len(res.recommendation_ids) == 1
    rec = inv_repo.get_recommendation(db, res.recommendation_ids[0])
    assert rec.status is RecommendationStatus.PROPOSED and set(rec.evidence_ids) <= set(ids)
    assert (
        rec.generator_type is GeneratorType.DETERMINISTIC_FALLBACK and "[RULE-BASED, NO LLM]" in rec.rationale
    )
    assert 1 <= rec.priority <= 5
    audit = inv_repo.audit_history(db, inv.investigation_id)
    tools = [a.tool_name for a in audit if a.action == "TOOL_CALL"]
    assert tools == ["hotspot_summary", "search_complaints"]
    assert {"AGENT_RUN_STARTED", "RECOMMENDATION_PROPOSED", "AGENT_RUN_COMPLETED"} <= {
        a.action for a in audit
    }
    with pytest.raises(ConflictError) as e:  # cannot be run twice
        investigate.run_investigation(db, inv.investigation_id, requested_by=CREATOR, request=req,
                                      settings=get_settings())  # fmt: skip
    assert e.value.code == "INVESTIGATION_NOT_RUNNABLE"


def test_llm_mode_without_a_provider_is_a_structured_error_not_a_silent_fallback(db):
    inv = new_inv(db)
    with pytest.raises(LlmNotConfiguredError):
        investigate.run_investigation(db, inv.investigation_id, requested_by=CREATOR,
                                     request=RunRequest(mode="llm"), settings=get_settings())  # fmt: skip
    assert inv_repo.require_investigation(db, inv.investigation_id).status is InvestigationStatus.OPEN


def test_auto_mode_reports_why_it_used_the_fallback(db):
    cluster(db, 6)
    inv = new_inv(db)
    res = investigate.run_investigation(
        db, inv.investigation_id, requested_by=CREATOR, settings=get_settings(),
        request=RunRequest(mode="auto", category=Category.TRAFFIC_SIGNAL, max_hotspots=1))  # fmt: skip
    assert res.generator is GeneratorType.DETERMINISTIC_FALLBACK and res.llm_configured is False
    assert "No LLM provider configured" in res.fallback_reason


# ------------------------------------------------------------------------------ LLM agent loop (test double)
def handle_for(responder):
    return LlmHandle(
        model=ScriptedChatModel(responder=responder), provider="test-double", model_name="scripted"
    )


def seen_ids(msgs):
    ids = set()
    for m in msgs:
        if isinstance(m, ToolMessage):
            ids |= {d["complaint_id"] for d in json.loads(m.content)["data"]}
    return sorted(ids)


def good_responder(msgs, n):
    if n == 1:
        return ai_calls(
            tool_call("search_complaints", {"category": "TRAFFIC_SIGNAL", "days": 30, "limit": 10})
        )
    cited = seen_ids(msgs)
    out = {"recommendations": [{"summary": "Dispatch signal crew", "rationale": "Complaints show repeat faults.",
                                "priority": 1, "confidence": 0.7, "evidence_ids": cited[:5],
                                "status": "APPROVED"}]}  # fmt: skip
    return AIMessage(content=json.dumps(out))


def test_llm_loop_persists_grounded_proposals_and_ignores_model_supplied_status(db):
    cluster(db, 6)
    inv = new_inv(db)
    res = investigate.run_investigation(db, inv.investigation_id, requested_by=CREATOR, settings=get_settings(),
                                        request=RunRequest(mode="llm"), llm=handle_for(good_responder))  # fmt: skip
    assert res.generator is GeneratorType.LLM and res.model_name == "test-double:scripted"
    rec = inv_repo.get_recommendation(db, res.recommendation_ids[0])
    assert rec.status is RecommendationStatus.PROPOSED  # model asked for APPROVED; ignored
    assert rec.generator_type is GeneratorType.LLM and rec.evidence_ids


def test_llm_fabricated_evidence_is_rejected_in_llm_mode(db):
    cluster(db, 6)

    def lying(msgs, n):
        if n == 1:
            return ai_calls(tool_call("search_complaints", {"category": "TRAFFIC_SIGNAL"}))
        real = seen_ids(msgs)[0]
        out = {"recommendations": [{"summary": "Fabricated evidence", "rationale": "Cites ids never retrieved.",
                                    "priority": 1, "confidence": 0.9, "evidence_ids": [real, 999999999]}]}  # fmt: skip
        return AIMessage(content=json.dumps(out))

    inv = new_inv(db)
    with pytest.raises(AgentError) as e:
        investigate.run_investigation(db, inv.investigation_id, requested_by=CREATOR, settings=get_settings(),
                                      request=RunRequest(mode="llm"), llm=handle_for(lying))  # fmt: skip
    assert e.value.code == "EVIDENCE_REJECTED"
    assert inv_repo.require_investigation(db, inv.investigation_id).status is InvestigationStatus.FAILED
    assert inv_repo.list_recommendations(db, inv.investigation_id) == []
    audit = inv_repo.audit_history(db, inv.investigation_id)
    rejected = [a for a in audit if a.action == "EVIDENCE_REJECTED"]
    assert rejected and "999999999" in rejected[0].input_json and not rejected[0].success


def test_auto_mode_degrades_to_labelled_fallback_when_llm_fails(db):
    cluster(db, 6)
    inv = new_inv(db)
    res = investigate.run_investigation(
        db, inv.investigation_id, requested_by=CREATOR, settings=get_settings(),
        request=RunRequest(mode="auto", category=Category.TRAFFIC_SIGNAL, max_hotspots=1),
        llm=handle_for(lambda m, n: AIMessage(content="I refuse to answer in JSON")))  # fmt: skip
    assert res.generator is GeneratorType.DETERMINISTIC_FALLBACK and res.llm_configured is True
    assert "INVALID_MODEL_OUTPUT" in res.fallback_reason and "NO LLM" in res.notice


def _provider_down(msgs, n):
    raise RuntimeError("Incorrect API key provided: sk-FAKE-0123456789")  # what a real SDK might say


def test_auto_mode_degrades_to_labelled_fallback_when_the_provider_call_itself_fails(db):
    """Wrong key / unknown model / rate limit / network errors come from the provider SDK, not from our validation.
    Auto mode must still end in the labelled fallback, say why, and keep the SDK's text out of Db2."""
    cluster(db, 6)
    inv = new_inv(db)
    res = investigate.run_investigation(
        db, inv.investigation_id, requested_by=CREATOR, settings=get_settings(),
        request=RunRequest(mode="auto", category=Category.TRAFFIC_SIGNAL, max_hotspots=1),
        llm=handle_for(_provider_down))  # fmt: skip
    assert res.generator is GeneratorType.DETERMINISTIC_FALLBACK and res.llm_configured is True
    assert "LLM_PROVIDER_ERROR" in res.fallback_reason and "RuntimeError" in res.fallback_reason
    assert "NO LLM" in res.notice
    assert (
        inv_repo.require_investigation(db, inv.investigation_id).status is InvestigationStatus.PENDING_REVIEW
    )
    audit = inv_repo.audit_history(db, inv.investigation_id)
    failed = [a for a in audit if a.action == "LLM_RUN_FAILED"]
    assert len(failed) == 1 and failed[0].success is False and "RuntimeError" in (failed[0].input_json or "")
    assert not any("sk-FAKE" in f"{a.input_json} {a.output_summary} {res.fallback_reason}" for a in audit)
    assert all(
        r.generator_type is GeneratorType.DETERMINISTIC_FALLBACK
        for r in inv_repo.list_recommendations(db, inv.investigation_id)
    )  # nothing is claimed to be an LLM's


def test_llm_only_mode_reports_a_provider_failure_and_the_investigation_can_be_retried(db):
    inv = new_inv(db)
    with pytest.raises(AgentError) as exc:
        investigate.run_investigation(
            db, inv.investigation_id, requested_by=CREATOR, settings=get_settings(),
            request=RunRequest(mode="llm"), llm=handle_for(_provider_down))  # fmt: skip
    assert exc.value.code == "LLM_PROVIDER_ERROR" and exc.value.status_code == 502
    assert "sk-FAKE" not in exc.value.message and "sk-FAKE" not in json.dumps(exc.value.to_detail())
    assert inv_repo.require_investigation(db, inv.investigation_id).status is InvestigationStatus.FAILED
    assert inv_repo.list_recommendations(db, inv.investigation_id) == []  # nothing was stored
    assert inv_repo.transition_status(db, inv.investigation_id, from_statuses=[InvestigationStatus.FAILED],
                                      to_status=InvestigationStatus.OPEN)  # fmt: skip


def test_runaway_agent_hits_step_limit_and_investigation_can_be_retried(db):
    inv = new_inv(db)
    loop = handle_for(lambda m, n: ai_calls(tool_call("hotspot_summary", {"days": 7}, f"c{n}")))
    with pytest.raises(AgentStepLimitError):
        investigate.run_investigation(db, inv.investigation_id, requested_by=CREATOR, settings=get_settings(),
                                      request=RunRequest(mode="llm"), llm=loop)  # fmt: skip
    assert inv_repo.require_investigation(db, inv.investigation_id).status is InvestigationStatus.FAILED
    assert inv_repo.transition_status(db, inv.investigation_id, from_statuses=[InvestigationStatus.FAILED],
                                      to_status=InvestigationStatus.OPEN)  # fmt: skip
    calls = [a for a in inv_repo.audit_history(db, inv.investigation_id) if a.action == "TOOL_CALL"]
    assert len(calls) == get_settings().agent_max_steps  # bounded: one tool call per step


def test_model_cannot_call_a_sql_tool(db):
    inv = new_inv(db)

    def sneaky(msgs, n):
        if n == 1:
            return ai_calls(tool_call("run_sql", {"query": "DELETE FROM CIVICLENS.COMPLAINTS"}))
        return AIMessage(content='{"recommendations": []}')

    res = investigate.run_investigation(db, inv.investigation_id, requested_by=CREATOR, settings=get_settings(),
                                        request=RunRequest(mode="llm"), llm=handle_for(sneaky))  # fmt: skip
    audit = inv_repo.audit_history(db, inv.investigation_id)
    assert any(a.action == "TOOL_REFUSED" and not a.success for a in audit)
    assert res.status is InvestigationStatus.CLOSED and res.recommendation_ids == []
    assert db.fetch_one("SELECT COUNT(*) AS N FROM {schema}.COMPLAINTS")["n"] > 0


# ------------------------------------------------------------------------------ migration upgrade
def test_column_upgrade_adds_generator_type_to_a_phase00_table(db):
    schema = "CIVTEST_UPGRADE"
    old_schema, db.schema = db.schema, schema
    try:
        db.execute_raw_ddl(f"CREATE SCHEMA {schema}")
        db.execute_raw_ddl(
            f"CREATE TABLE {schema}.RECOMMENDATIONS (RECOMMENDATION_ID BIGINT NOT NULL PRIMARY KEY)"
        )
        _, added = apply_column_upgrades(db)
        assert added == [f"COLUMN {schema}.RECOMMENDATIONS.GENERATOR_TYPE"]
        assert apply_column_upgrades(db) == ([f"COLUMN {schema}.RECOMMENDATIONS.GENERATOR_TYPE"], [])
    finally:
        db.execute_raw_ddl(f"DROP TABLE {schema}.RECOMMENDATIONS")
        db.execute_raw_ddl(f"DROP SCHEMA {schema} RESTRICT")
        db.schema = old_schema


# ------------------------------------------------------------------------------ API end to end
@pytest.fixture()
def api(monkeypatch, db):
    tokens = {"pytest-ana": ("analyst", secrets.token_hex(16)), REV1: ("reviewer", secrets.token_hex(16)),
              REV2: ("reviewer", secrets.token_hex(16))}  # fmt: skip
    monkeypatch.setenv("CIVICLENS_AUTH_TOKENS", ",".join(f"{u}:{r}:{t}" for u, (r, t) in tokens.items()))
    monkeypatch.setenv("LLM_PROVIDER", "none")
    get_settings.cache_clear()  # the db fixture already cached settings from the local .env
    client = TestClient(create_app())
    hdr = {u: {"Authorization": f"Bearer {t}"} for u, (_, t) in tokens.items()}
    return client, hdr


def test_api_full_workflow(api, db):
    client, hdr = api
    ana, rev, rev2 = hdr["pytest-ana"], hdr[REV1], hdr[REV2]
    ids = cluster(db, 6)

    assert client.post("/api/investigations", json={"title": "Signals", "question": "q?"}).status_code == 401
    assert (
        client.post(
            "/api/investigations", json={"title": "Signals", "question": "Where?"}, headers=rev
        ).status_code
        == 403
    )
    r = client.post(
        "/api/investigations",
        json={"title": "Signal faults", "question": "Where are signal faults?"},
        headers=ana,
    )
    assert r.status_code == 201 and r.json()["created_by"] == "pytest-ana" and r.json()["status"] == "OPEN"
    inv_id = r.json()["investigation_id"]
    assert client.get(f"/api/investigations/{inv_id}", headers=rev).json()["title"] == "Signal faults"
    assert (
        client.get("/api/investigations/999999999", headers=ana).json()["detail"]["code"]
        == "INVESTIGATION_NOT_FOUND"
    )

    # run (LLM_PROVIDER=none) -> labelled fallback
    run = client.post(f"/api/investigations/{inv_id}/run", headers=ana,
                      json={"mode": "auto", "category": "TRAFFIC_SIGNAL", "max_hotspots": 1})  # fmt: skip
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["generator"] == "DETERMINISTIC_FALLBACK" and body["llm_configured"] is False
    assert "NO LLM" in body["notice"] and body["status"] == "PENDING_REVIEW"
    assert client.post(f"/api/investigations/{inv_id}/run", headers=ana).status_code == 409
    llm_only = client.post(f"/api/investigations/{inv_id}/run", json={"mode": "llm"}, headers=ana)
    assert llm_only.status_code == 409 and llm_only.json()["detail"]["code"] == "LLM_NOT_CONFIGURED"

    evidence = client.get(f"/api/investigations/{inv_id}/evidence", headers=rev).json()
    assert (
        evidence
        and {e["complaint_id"] for e in evidence} <= set(ids)
        and all(e["is_synthetic"] for e in evidence)
    )
    recs = client.get(f"/api/investigations/{inv_id}/recommendations", headers=rev).json()
    assert len(recs) == 1 and recs[0]["status"] == "PROPOSED" and recs[0]["review"] is None
    rec_id = recs[0]["recommendation_id"]
    assert set(recs[0]["evidence_ids"]) <= set(ids)

    # authorization on the decision
    assert (
        client.post(
            f"/api/recommendations/{rec_id}/decision", json={"decision": "APPROVED"}, headers=ana
        ).status_code
        == 403
    )
    assert (
        client.post(f"/api/recommendations/{rec_id}/decision", json={"decision": "APPROVED"}).status_code
        == 401
    )
    assert client.get(f"/api/recommendations/{rec_id}", headers=rev).json()["status"] == "PROPOSED"

    ok = client.post(f"/api/recommendations/{rec_id}/decision", headers=rev,
                     json={"decision": "APPROVED", "comment": "Crew dispatched"})  # fmt: skip
    assert (
        ok.status_code == 200
        and ok.json()["status"] == "APPROVED"
        and ok.json()["review"]["reviewer"] == REV1
    )
    for who in (rev, rev2):  # duplicate and conflicting decisions
        again = client.post(f"/api/recommendations/{rec_id}/decision", headers=who,
                            json={"decision": "REJECTED", "comment": "changed my mind"})  # fmt: skip
        assert again.status_code == 409
    assert client.get(f"/api/investigations/{inv_id}", headers=ana).json()["status"] == "CLOSED"

    audit = client.get(f"/api/investigations/{inv_id}/audit", headers=rev).json()
    actions = [a["action"] for a in audit]
    for expected in ("INVESTIGATION_CREATED", "AGENT_RUN_STARTED", "TOOL_CALL", "RECOMMENDATION_PROPOSED",
                     "AGENT_RUN_COMPLETED", "REVIEW_APPROVED"):  # fmt: skip
        assert expected in actions, actions
    assert [a["audit_id"] for a in audit] == sorted(a["audit_id"] for a in audit)


def test_api_manual_proposal_validation_and_self_review_denial(api, db):
    client, hdr = api
    ana, rev = hdr["pytest-ana"], hdr[REV1]
    ids = cluster(db, 3)
    inv_id = client.post("/api/investigations", json={"title": "Manual", "question": "Manual question"},
                         headers=ana).json()["investigation_id"]  # fmt: skip
    base = {
        "summary": "Inspect signal",
        "rationale": "Complaints show faults.",
        "priority": 2,
        "confidence": 0.5,
    }
    url = f"/api/investigations/{inv_id}/recommendations"
    fab = client.post(url, json={**base, "evidence_ids": [999999999]}, headers=ana)
    assert fab.status_code == 422 and fab.json()["detail"]["code"] == "UNKNOWN_COMPLAINT_IDS"
    detached = client.post(url, json={**base, "evidence_ids": ids}, headers=ana)
    assert detached.status_code == 422 and detached.json()["detail"]["code"] == "EVIDENCE_NOT_ATTACHED"
    assert (
        client.post(url, json={**base, "evidence_ids": ids, "status": "APPROVED"}, headers=ana).status_code
        == 422
    )
    bad_ev = client.post(
        f"/api/investigations/{inv_id}/evidence", json={"complaint_ids": [999999999]}, headers=ana
    )
    assert bad_ev.status_code == 422
    assert (
        client.post(
            f"/api/investigations/{inv_id}/evidence", json={"complaint_ids": ids}, headers=ana
        ).status_code
        == 200
    )
    made = client.post(url, json={**base, "evidence_ids": ids}, headers=ana)
    assert (
        made.status_code == 201
        and made.json()["status"] == "PROPOSED"
        and made.json()["generator_type"] == "MANUAL"
    )

    # an investigation created by a reviewer-id user cannot be reviewed by that same user
    own = new_inv(db, created_by=REV1)
    rid = propose(db, own.investigation_id, ids)
    denied = client.post(f"/api/recommendations/{rid}/decision", json={"decision": "APPROVED"}, headers=rev)
    assert denied.status_code == 403 and denied.json()["detail"]["code"] == "SELF_REVIEW_FORBIDDEN"
    assert inv_repo.get_recommendation(db, rid).status is RecommendationStatus.PROPOSED
    audit = inv_repo.audit_history(db, own.investigation_id)
    assert any(a.action == "REVIEW_DENIED" and a.actor_id == REV1 and not a.success for a in audit)
    # another reviewer may decide it; rejection requires a comment
    r2 = client.post(f"/api/recommendations/{rid}/decision", json={"decision": "REJECTED"}, headers=hdr[REV2])
    assert r2.status_code == 422
    r3 = client.post(f"/api/recommendations/{rid}/decision", json={"decision": "REJECTED", "comment": "Insufficient"},
                     headers=hdr[REV2])  # fmt: skip
    assert r3.status_code == 200 and r3.json()["status"] == "REJECTED"
    assert (
        client.post(
            "/api/recommendations/999999999/decision", json={"decision": "APPROVED"}, headers=rev
        ).status_code
        == 404
    )
