"""Investigation pipeline: 5 agents, shared context, per-agent persistence in Db2.

Each agent's status, structured output and execution log is written to
AGENT_INVESTIGATIONS as it runs, so the UI shows real progress.
"""
from __future__ import annotations

import datetime as dt
import logging
import secrets
import threading
import traceback
from typing import Any

from app.core.config import get_settings
from app.database import Database
from app.services.common import audit, dumps, loads, ts
from app.services.incidents import get_incident, transition

from . import deterministic as det
from .schemas import AGENT_TITLES, AGENTS, InvestigationFindings, RecallPlan, RiskAssessment, SupplyChainFindings, VerificationReport

log = logging.getLogger("recallguard.orchestrator")

MODE_LLM = "CREWAI_LLM"
MODE_FALLBACK = "DETERMINISTIC_FALLBACK"
_running: dict[str, threading.Thread] = {}


def new_run_id() -> str:
    return f"RUN-{dt.datetime.now():%Y%m%d%H%M%S}-{secrets.token_hex(2).upper()}"


def _queue(db: Database, run_id: str, incident_id: str, mode: str) -> None:
    with db.transaction():
        for n, a in enumerate(AGENTS, start=1):
            db.execute("INSERT INTO agent_investigations (run_id, incident_id, agent_name, step_no, execution_mode, run_status, created_at) "
                       "VALUES (?,?,?,?,?,?,?)", (run_id, incident_id, a, n, mode, "QUEUED", ts()))


def _update(db: Database, run_id: str, agent: str, **cols: Any) -> None:
    sets = ", ".join(f"{k} = ?" for k in cols)
    db.execute(f"UPDATE agent_investigations SET {sets} WHERE run_id = ? AND agent_name = ?", (*cols.values(), run_id, agent))


def start_investigation(db: Database, incident_id: str, actor: str, role: str, background: bool = True) -> dict[str, Any]:
    inc = get_incident(db, incident_id)
    if incident_id in _running and _running[incident_id].is_alive():
        raise RuntimeError(f"An investigation is already running for {incident_id}")
    if inc["incident_status"] not in ("REPORTED", "INVESTIGATING"):
        # re-investigation request: allowed from review/approval/rejected states
        transition(db, incident_id, "INVESTIGATING", actor, role, "Re-investigation requested")
    else:
        transition(db, incident_id, "INVESTIGATING", actor, role, "Investigation started")
    settings = get_settings()
    mode = MODE_LLM if settings.llm_configured else MODE_FALLBACK
    run_id = new_run_id()
    _queue(db, run_id, incident_id, mode)
    audit(db, actor, role, "INVESTIGATION_STARTED", "INCIDENT", incident_id, {"run_id": run_id, "mode": mode})
    if background:
        t = threading.Thread(target=run_pipeline, args=(db, run_id, incident_id, actor, role, mode), daemon=True,
                             name=f"investigation-{incident_id}")
        _running[incident_id] = t
        t.start()
    else:
        run_pipeline(db, run_id, incident_id, actor, role, mode)
    return {"run_id": run_id, "incident_id": incident_id, "mode": mode}


def run_pipeline(db: Database, run_id: str, incident_id: str, actor: str, role: str, mode: str) -> dict[str, Any]:
    ctx: dict[str, Any] = {"incident": get_incident(db, incident_id), "run_id": run_id}
    runner = None
    if mode == MODE_LLM:
        try:
            from .crew import CrewRunner

            runner = CrewRunner(db, get_settings())
        except Exception as exc:  # e.g. provider package missing
            log.warning("CrewAI unavailable (%s); falling back", exc)
            mode = MODE_FALLBACK

    steps = [
        ("investigation", lambda lg: det.investigation_agent(db, ctx, lg)),
        ("supply_chain", lambda lg: det.supply_chain_agent(db, ctx, lg)),
        ("risk_assessment", lambda lg: det.risk_agent(db, ctx, lg)),
        ("recall_planning", lambda lg: det.recall_planning_agent(db, ctx, lg)),
        ("verification", lambda lg: det.verification_agent(db, ctx, lg)),
    ]
    key = {"investigation": "investigation", "supply_chain": "supply_chain", "risk_assessment": "risk",
           "recall_planning": "recall_plan", "verification": "verification"}
    try:
        for agent, fn in steps:
            lines: list[str] = []

            def lg(msg: str, _l=lines) -> None:
                _l.append(f"{dt.datetime.now():%H:%M:%S} {msg}")

            step_mode = mode
            _update(db, run_id, agent, run_status="RUNNING", started_at=ts())
            lg(f"{AGENT_TITLES[agent]} started ({'CrewAI + LLM' if mode == MODE_LLM else 'deterministic fallback — no LLM configured'}).")
            result = fn(lg)
            if runner is not None:
                try:
                    lg("Requesting CrewAI narrative grounded in the Db2 facts above…")
                    shared = "\n".join(f"- {k}: {getattr(v, 'summary', '')}" for k, v in ctx.items() if hasattr(v, "summary"))
                    nar = runner.run_step(agent, result.model_dump(mode="json"), shared)
                    result = _merge(agent, result, nar)
                    lg("CrewAI narrative merged (facts unchanged).")
                except Exception as exc:
                    step_mode = MODE_FALLBACK
                    lg(f"LLM step failed ({type(exc).__name__}: {str(exc)[:200]}); deterministic output retained and labelled as fallback.")
            ctx[key[agent]] = result
            _update(db, run_id, agent, run_status="COMPLETED", completed_at=ts(), execution_mode=step_mode,
                    output_json=result.model_dump_json(), log_text="\n".join(lines)[:100000])
            if agent == "investigation":
                transition(db, incident_id, "EVIDENCE_REVIEW", "agent.investigation", "system", "Evidence assembled")
            if agent == "supply_chain":
                _persist_affected(db, incident_id, ctx)
            if agent == "recall_planning":
                transition(db, incident_id, "RECALL_RECOMMENDED", "agent.recall_planning", "system", "Recall plan drafted")
        audit(db, "agent.orchestrator", "system", "INVESTIGATION_COMPLETED", "INCIDENT", incident_id,
              {"run_id": run_id, "verdict": ctx["verification"].verdict, "risk": ctx["risk"].score})
        return {"run_id": run_id, "status": "COMPLETED"}
    except Exception as exc:
        log.error("investigation %s failed: %s", run_id, traceback.format_exc())
        db.execute("UPDATE agent_investigations SET run_status = 'FAILED', log_text = ?, completed_at = ? "
                   "WHERE run_id = ? AND run_status IN ('RUNNING','QUEUED')", (f"FAILED: {exc}"[:4000], ts(), run_id))
        audit(db, "agent.orchestrator", "system", "INVESTIGATION_FAILED", "INCIDENT", incident_id, {"run_id": run_id, "error": str(exc)[:500]})
        return {"run_id": run_id, "status": "FAILED", "error": str(exc)}
    finally:
        _running.pop(incident_id, None)


def _merge(agent: str, result, nar):
    if agent == "investigation":
        return result.model_copy(update={"summary": nar.summary, "hypothesis": nar.hypothesis,
                                         "missing_evidence": result.missing_evidence + list(nar.open_questions)})
    if agent == "supply_chain":
        return result.model_copy(update={"summary": nar.summary})
    if agent == "risk_assessment":
        return result.model_copy(update={"narrative": nar.narrative})
    if agent == "recall_planning":
        notes = [n.model_copy(update={"instruction": f"{nar.retailer_instruction_preamble.strip()} {n.instruction}"}) for n in result.notifications]
        return result.model_copy(update={"summary": nar.summary, "notifications": notes})
    if agent == "verification":
        return result.model_copy(update={"summary": nar.summary,
                                         "human_review_reasons": result.human_review_reasons + list(nar.additional_concerns)})
    return result


def _persist_affected(db: Database, incident_id: str, ctx: dict[str, Any]) -> None:
    imp = ctx["impact"]
    db.execute("DELETE FROM incident_affected_lots WHERE incident_id = ?", (incident_id,))
    rows = [(incident_id, imp["source"]["kind"], imp["source"]["ref"], "SOURCE", 0, "agent.supply_chain", ts())]
    for b in imp["batches"]:
        if b["batch_id"] != imp["source"]["ref"]:
            rows.append((incident_id, "BATCH", b["batch_id"], b["relation"], int(b["depth"]), "agent.supply_chain", ts()))
    db.executemany("INSERT INTO incident_affected_lots (incident_id, node_kind, node_ref, relation, depth, identified_by, created_at) "
                   "VALUES (?,?,?,?,?,?,?)", rows)


# ------------------------------------------------------------------ reads
OUTPUT_MODELS = {"investigation": InvestigationFindings, "supply_chain": SupplyChainFindings, "risk_assessment": RiskAssessment,
                 "recall_planning": RecallPlan, "verification": VerificationReport}


def latest_run(db: Database, incident_id: str) -> dict[str, Any] | None:
    row = db.query_one("SELECT run_id FROM agent_investigations WHERE incident_id = ? ORDER BY created_at DESC, run_id DESC "
                       "FETCH FIRST 1 ROWS ONLY" if db.mode == "db2" else
                       "SELECT run_id FROM agent_investigations WHERE incident_id = ? ORDER BY created_at DESC, run_id DESC LIMIT 1",
                       (incident_id,))
    return get_run(db, row["run_id"]) if row else None


def get_run(db: Database, run_id: str) -> dict[str, Any]:
    rows = db.query("SELECT run_id, incident_id, agent_name, step_no, execution_mode, run_status, output_json, log_text, started_at, completed_at "
                    "FROM agent_investigations WHERE run_id = ? ORDER BY step_no", (run_id,))
    agents = []
    for r in rows:
        r["title"] = AGENT_TITLES.get(r["agent_name"], r["agent_name"])
        r["output"] = loads(r.pop("output_json"), None)
        r["log"] = (r.pop("log_text") or "").splitlines()
        agents.append(r)
    statuses = {a["run_status"] for a in agents}
    status = "FAILED" if "FAILED" in statuses else "COMPLETED" if statuses == {"COMPLETED"} else "RUNNING" if statuses & {"RUNNING", "COMPLETED"} else "QUEUED"
    modes = {a["execution_mode"] for a in agents}
    return {"run_id": run_id, "incident_id": agents[0]["incident_id"] if agents else None, "status": status,
            "mode": MODE_LLM if modes == {MODE_LLM} else MODE_FALLBACK if modes == {MODE_FALLBACK} else "MIXED",
            "mode_note": ("Outputs produced by deterministic Db2-backed agents — NOT an LLM response." if MODE_FALLBACK in modes else
                          "Narratives produced by CrewAI LLM agents; all facts from Db2."),
            "progress": sum(1 for a in agents if a["run_status"] == "COMPLETED") / max(1, len(agents)),
            "agents": agents}


def run_outputs(db: Database, run_id: str) -> dict[str, Any]:
    run = get_run(db, run_id)
    out = {}
    for a in run["agents"]:
        if a["output"] is not None:
            out[a["agent_name"]] = OUTPUT_MODELS[a["agent_name"]].model_validate(a["output"])
    return out
