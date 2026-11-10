"""FastAPI backend: REST endpoints, a live Server-Sent-Events stream, and the web UI."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import __version__
from .config import Settings
from .graph import investigate, stream_investigation
from .llm import LLM
from .models import parse_ts, fmt_ts

STATIC = Path(__file__).parent / "static"
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _check_id(run_id: str) -> str:
    if not _ID.match(run_id):
        raise HTTPException(400, "invalid run id")
    return run_id


class InvestigateRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    hours: Optional[float] = Field(default=None, gt=0, le=24 * 30)
    since: Optional[str] = None
    until: Optional[str] = None


def create_app(repo=None, llm: Optional[LLM] = None, demo=None, settings: Optional[Settings] = None) -> FastAPI:
    """Create the app. Tests inject a repository/LLM; production wires Db2 lazily on first use."""
    settings = settings or Settings.from_env()
    holder = {"repo": repo, "llm": llm, "demo": demo}

    def get_repo():
        if holder["repo"] is None:
            from .db import Db2Gateway
            from .demo import DemoOps
            from .repository import Db2Repository

            gateway = Db2Gateway(settings)
            holder["repo"] = Db2Repository(gateway)
            holder["demo"] = DemoOps(gateway)
        return holder["repo"]

    def get_llm() -> LLM:
        if holder["llm"] is None:
            holder["llm"] = LLM.from_settings(settings)
        return holder["llm"]

    app = FastAPI(title="Db2 Time Machine", version=__version__)

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/health")
    def health():
        info = {"version": __version__, "llm": {"enabled": get_llm().enabled, "label": get_llm().label}}
        try:
            r = get_repo()
            info["db"] = {"ok": True, "now": fmt_ts(r.now()),
                          "temporal_tables": [t.get("tabname") for t in r.temporal_tables()]}
        except Exception as exc:
            info["db"] = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:240]}"}
        info["demo_controls"] = holder["demo"] is not None or repo is None
        return info

    @app.get("/api/products")
    def products():
        try:
            return get_repo().products()
        except Exception as exc:
            raise HTTPException(503, f"Db2 unavailable: {str(exc)[:200]}")

    @app.get("/api/investigate/stream")
    def stream(question: str = Query(min_length=3, max_length=500), hours: Optional[float] = Query(None, gt=0),
               since: Optional[str] = None, until: Optional[str] = None):
        r = get_repo()

        def sse():
            for event in stream_investigation(r, question, llm=get_llm(), settings=settings,
                                              hours=hours, since=since, until=until):
                yield f"data: {json.dumps(event, default=str)}\n\n"
            yield 'data: {"type": "done"}\n\n'

        return StreamingResponse(sse(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/investigate")
    def investigate_once(body: InvestigateRequest):
        try:
            return investigate(get_repo(), body.question, llm=get_llm(), settings=settings,
                               hours=body.hours, since=body.since, until=body.until)
        except Exception as exc:
            raise HTTPException(500, f"{type(exc).__name__}: {str(exc)[:300]}")

    @app.get("/api/reports")
    def reports(limit: int = Query(20, ge=1, le=100)):
        return get_repo().list_reports(limit)

    @app.get("/api/reports/{run_id}")
    def report(run_id: str):
        found = get_repo().get_report(_check_id(run_id))
        if not found:
            raise HTTPException(404, "report not found")
        return found

    @app.get("/api/audit/{run_id}")
    def audit(run_id: str):
        return get_repo().list_audit(_check_id(run_id))

    @app.get("/api/curve")
    def curve(product_id: Optional[int] = None, start: Optional[str] = None, end: Optional[str] = None,
              points: int = Query(18, ge=4, le=40)):
        """Revenue 'as of' evenly spaced moments: the time-travel chart (one FOR SYSTEM_TIME AS OF query each)."""
        r = get_repo()
        now = r.now()
        snap = r.last_snapshot(product_id)
        t1 = parse_ts(start) if start else (snap["ts"] if snap else now.replace(microsecond=0))
        t2 = parse_ts(end) if end else now
        return {"start": fmt_ts(t1), "end": fmt_ts(t2), "points": r.curve(product_id, t1, t2, points)}

    def need_demo():
        get_repo()
        if holder["demo"] is None:
            raise HTTPException(404, "demo controls are not available for this backend")
        return holder["demo"]

    @app.post("/api/demo/reset")
    def demo_reset():
        try:
            return need_demo().reset()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(500, f"{type(exc).__name__}: {str(exc)[:300]}")

    @app.post("/api/demo/inject/{fault}")
    def demo_inject(fault: str):
        try:
            return need_demo().inject(fault)
        except HTTPException:
            raise
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        except Exception as exc:
            raise HTTPException(500, f"{type(exc).__name__}: {str(exc)[:300]}")

    @app.exception_handler(Exception)
    async def unhandled(_, exc: Exception):
        return JSONResponse({"detail": f"{type(exc).__name__}: {str(exc)[:200]}"}, status_code=500)

    return app
