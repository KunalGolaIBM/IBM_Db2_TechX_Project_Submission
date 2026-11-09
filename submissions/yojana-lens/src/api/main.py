"""FastAPI surface.

The API deliberately exposes the audit trail as a first-class resource:
every decision the agent makes can be fetched back, with the rule rows,
the clause that grounds each one, and the log of what happened.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import db
from ..agent import has_langgraph, run as run_agent
from ..config import STATIC_DIR, settings
from ..models import AskRequest

app = FastAPI(
    title="YojanaLens",
    version="1.0.0",
    description="Auditable scheme-eligibility agent on IBM Db2.",
)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _db_error(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "error": "database_unavailable",
            "message": "IBM Db2 is not reachable. Start it with `docker compose up -d db2` "
                       "and wait for the first-boot initialisation to finish.",
            "hint": str(exc).splitlines()[0][:300],
        },
    )


@app.exception_handler(db.Db2Error)
async def _handle_db2_error(_request, exc: db.Db2Error):
    return JSONResponse(status_code=503, content=_db_error(exc).detail)


@app.get("/", include_in_schema=False)
def index():
    target = STATIC_DIR / "index.html"
    if not target.is_file():
        raise HTTPException(status_code=500, detail="UI asset missing")
    return FileResponse(target)


@app.get("/api/health")
def health() -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "status": "ok",
        "db": "unknown",
        "engine": "langgraph" if has_langgraph() else "sequential",
        "llm_mode": "mock" if settings.llm_is_mock else "live",
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
        "embedding_dim": settings.embedding_dim,
    }
    try:
        with db.connect() as conn:
            row = db.fetch_one(conn, "SELECT CURRENT SERVER AS server FROM SYSIBM.SYSDUMMY1")
            payload["db"] = "connected"
            payload["db_name"] = row["server"] if row else settings.db_name
    except Exception as exc:
        payload["db"] = "unreachable"
        payload["db_error"] = str(exc).splitlines()[0][:200]
        payload["status"] = "degraded"
    return payload


@app.get("/api/stats")
def stats() -> Dict[str, Any]:
    try:
        with db.connect() as conn:
            row = db.fetch_named_one(conn, "corpus_stats", {})
            return row or {}
    except Exception as exc:
        raise _db_error(exc)


@app.get("/api/schemes")
def schemes() -> Dict[str, Any]:
    try:
        with db.connect() as conn:
            rows = db.fetch_all(
                conn,
                "SELECT s.scheme_id, s.name, s.gov_level, s.state_code, s.category, "
                "s.benefit_summary, s.source_url, "
                "(SELECT COUNT(*) FROM scheme_rules r WHERE r.scheme_id = s.scheme_id) AS rule_count, "
                "(SELECT COUNT(*) FROM scheme_chunks c WHERE c.scheme_id = s.scheme_id) AS clause_count "
                "FROM schemes s WHERE s.status = 'ACTIVE' ORDER BY s.name",
            )
        return {"schemes": rows}
    except Exception as exc:
        raise _db_error(exc)


@app.get("/api/runs")
def recent_runs() -> Dict[str, Any]:
    try:
        with db.connect() as conn:
            return {"runs": db.fetch_named(conn, "recent_runs", {})}
    except Exception as exc:
        raise _db_error(exc)


@app.post("/api/ask")
def ask(request: AskRequest) -> Dict[str, Any]:
    try:
        state = run_agent(request.text, category=request.category or None)
    except db.Db2Error as exc:
        raise _db_error(exc)
    except Exception as exc:  # model/transport failures are reported, not hidden
        raise HTTPException(status_code=500, detail={
            "error": "agent_failed",
            "message": str(exc).splitlines()[0][:300],
        })

    return {
        "run_id": state.get("run_id"),
        "status": state.get("status"),
        "engine": state.get("engine"),
        "message": state.get("message"),
        "facts": state.get("facts", {}),
        "notes": state.get("notes", []),
        "counts": state.get("counts", {}),
        "filtered_by_residency": state.get("filtered_by_residency", 0),
        "duration_ms": state.get("duration_ms", 0),
        "results": state.get("results", []),
        "retrieved_clauses": len(state.get("retrieved", [])),
        "llm_mode": "mock" if settings.llm_is_mock else "live",
    }


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> Dict[str, Any]:
    try:
        with db.connect() as conn:
            overview = db.fetch_named_one(conn, "run_overview", {"run_id": run_id})
            if not overview:
                raise HTTPException(status_code=404, detail="run not found")
            if isinstance(overview.get("summary_json"), str):
                try:
                    overview["summary"] = json.loads(overview["summary_json"])
                except json.JSONDecodeError:
                    overview["summary"] = None
                overview.pop("summary_json", None)
            events = db.fetch_named(conn, "audit_events", {"run_id": run_id})
            trace = db.fetch_named(conn, "scheme_trace", {"run_id": run_id})
    except HTTPException:
        raise
    except Exception as exc:
        raise _db_error(exc)

    return {"run": overview, "audit_events": events, "trace": trace}


@app.get("/api/runs/{run_id}/trace")
def run_trace(run_id: str) -> Dict[str, Any]:
    try:
        with db.connect() as conn:
            return {"trace": db.fetch_named(conn, "scheme_trace", {"run_id": run_id})}
    except Exception as exc:
        raise _db_error(exc)
