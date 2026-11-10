"""NEEDLE local HTTP API (FastAPI) for the React front end in needle/web/.

Run from the needle/ folder:   PYTHONPATH=src python -m needle.api   (serves the API and the built web/dist
                                                                      on http://127.0.0.1:8600)

Security model (same as the Streamlit app):
- Loopback only. ``main()`` refuses any host other than 127.0.0.1 / localhost, and a Host-header check blocks
  DNS rebinding.
- Sign-in uses the visitor's OWN Db2 user ID + password; RCAC binds to that identity. The password lives only in
  this process's memory for the session (never logged, never written, never echoed in a response). With
  NEEDLE_DEMO_SWITCHER=1 a demo identity can be picked without a password (read from needle/.env): that switch is
  NOT authentication and the UI says so.
- Every Db2 statement runs through ``service.do_run`` on the user's own connection. No SQL is built from request
  text; the memo's evidence comes only from the result the server itself fetched for this session.
"""
from __future__ import annotations

import datetime as dt
import decimal
import json
import os
import re
import secrets
import socket
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from needle import sbom, service
from needle.retriever import MODES

ROOT = Path(__file__).resolve().parents[2]          # needle/
load_dotenv(ROOT / ".env")
WEB_DIST = ROOT / "web" / "dist"
EVIDENCE_DIRS = {"evidence": (ROOT / "docs" / "evidence", (".md", ".txt")),
                 "results": (ROOT / "eval" / "results", (".json", ".png"))}

DEMO_USERS = ["NDL_SENIOR", "NDL_JUNIOR", "NDL_P10"]
DEMO_ROLES = {"NDL_SENIOR": "Senior analyst: all rows, sees embargoed advisories",
              "NDL_JUNIOR": "Junior analyst: embargoed advisories hidden by Db2",
              "NDL_P10": "Sweep identity: 10% of rows visible"}
LOOPBACK = {"127.0.0.1", "localhost"}
SESSION_IDLE_S = 4 * 3600
MAX_SESSIONS = 64


def demo_switcher_enabled() -> bool:
    return os.environ.get("NEEDLE_DEMO_SWITCHER") == "1"


# ------------------------------------------------------------------------------------------------
# Sessions (process memory only)
# ------------------------------------------------------------------------------------------------

@dataclass
class Session:
    user: str
    password: str | None = field(repr=False)        # None = demo identity (server reads needle/.env)
    demo: bool
    visible_docs: int | None = None
    last_used: float = field(default_factory=time.time)
    last_result: dict | None = field(default=None, repr=False)


_SESSIONS: dict[str, Session] = {}
_LOCK = threading.Lock()


def _new_session(s: Session) -> str:
    token = secrets.token_urlsafe(32)
    with _LOCK:
        now = time.time()
        for t in [t for t, v in _SESSIONS.items() if now - v.last_used > SESSION_IDLE_S]:
            _SESSIONS.pop(t, None)
        while len(_SESSIONS) >= MAX_SESSIONS:
            _SESSIONS.pop(min(_SESSIONS, key=lambda t: _SESSIONS[t].last_used))
        _SESSIONS[token] = s
    return token


def current_session(authorization: str | None = Header(default=None)) -> Session:
    token = (authorization or "").removeprefix("Bearer ").strip()
    with _LOCK:
        s = _SESSIONS.get(token) if token else None
        if s is None or time.time() - s.last_used > SESSION_IDLE_S:
            _SESSIONS.pop(token, None)
            raise HTTPException(401, {"kind": "login", "message": "Sign in with your Db2 user ID first."})
        s.last_used = time.time()
        return s


# ------------------------------------------------------------------------------------------------
# Serialisation (plain JSON, no live handles, never the password)
# ------------------------------------------------------------------------------------------------

def _j(v: Any) -> Any:
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    return v


def _embargoed(until: Any) -> bool:
    if isinstance(until, str):
        try:
            until = dt.datetime.fromisoformat(until)
        except ValueError:
            return False
    if isinstance(until, dt.date) and not isinstance(until, dt.datetime):
        until = dt.datetime.combine(until, dt.time())
    return isinstance(until, dt.datetime) and until.replace(tzinfo=None) > dt.datetime.now()


def doc_json(adv_id: str, d: dict) -> dict:
    return {"id": adv_id, "title": service.title_of(d, 220), "kind": d.get("KIND"),
            "packages": list(d.get("PACKAGES_LIST") or [])[:8], "aliases": list(d.get("ALIASES") or [])[:8],
            "published": str(d.get("PUBLISHED") or "")[:10] or None, "cvss": d.get("CVSS"),
            "embargoed": _embargoed(d.get("EMBARGO_UNTIL")), "embargo_until": _j(d.get("EMBARGO_UNTIL")),
            "details": (d.get("DETAILS") or "")[:1500], "osv": service.osv_link(adv_id)}


def router_json(run) -> dict:
    c = run.depth_choice or {}
    return {"line": service.depth_line(run), "depth": run.depth, "chosen_depth": c.get("chosen_depth"),
            "reason": c.get("reason"), "how": service.ROUTER_HOW.get(c.get("reason"), c.get("reason") or "fixed"),
            "visible_rows": c.get("visible_rows"), "total_rows": c.get("total_rows")}


def result_json(res: dict) -> dict:
    out = {"user": res["user"], "query": res["query"], "k": res["k"], "ts": res["ts"]}
    if res.get("fatal"):
        kind, msg = res["fatal"]
        out["fatal"] = {"kind": kind, "message": msg}
        return out
    run = res["run"]
    ids = res.get("exposure_ids") or []
    err = res.get("exposure_error")
    out.update({
        "rankings": {m: [{"rank": i, "id": c["ADV_ID"], "rrf": _j(c.get("RRF")), "kw_rank": c.get("KW_RANK"),
                          "vec_rank": c.get("VEC_RANK"), "vec_dist": _j(c.get("VEC_DIST"))}
                         for i, c in enumerate(run.ranked(m), 1)] for m in MODES},
        "docs": {a: doc_json(a, d) for a, d in run.docs.items()},
        "router": router_json(run),
        "timings_ms": dict(run.timings_ms),
        "visible_docs": res.get("visible_docs"),
        "dropped_invisible": run.dropped_invisible,
        "exposure": [{k: _j(v) for k, v in r.items()} for r in res.get("exposure") or []],
        "exposure_error": None if not err else {"kind": "no_grant" if "SQL0551N" in err else "error", "message": err},
        "sql": {"path": run.path, "call": run.call_text, "params": run.params_display, "procedure": run.sql_text,
                "exposure": sbom.exposure_sql(max(1, len(ids))), "exposure_params": ids},
    })
    return out


# ------------------------------------------------------------------------------------------------
# App
# ------------------------------------------------------------------------------------------------

app = FastAPI(title="NEEDLE local API", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=sorted(LOOPBACK))


@app.middleware("http")
async def _headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.exception_handler(RequestValidationError)
async def _invalid(_: Request, exc: RequestValidationError):
    # Never echo the request body back (it may hold a password): field names and messages only.
    fields = [{"field": ".".join(str(p) for p in e.get("loc", ())[1:]), "message": e.get("msg", "")}
              for e in exc.errors()]
    return JSONResponse({"detail": {"kind": "input", "message": "Invalid request", "fields": fields}}, 422)


class LoginIn(BaseModel):
    user: str = Field(min_length=1, max_length=30)
    password: str | None = Field(default=None, max_length=256)


class TriageIn(BaseModel):
    query: str = Field(min_length=3, max_length=4000)
    k: int = Field(default=10, ge=5, le=20)


class MemoIn(BaseModel):
    mode: str = Field(default="hybrid", pattern="^(keyword|vector|hybrid)$")


def _tcp_ok(host: str, port: int) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True, f"{host}:{port} reachable"
    except OSError as e:
        return False, f"{host}:{port} not reachable ({e.__class__.__name__})"


@app.get("/api/health")
def health() -> dict:
    env = sbom._env()
    db_ok, db_detail = _tcp_ok(env.get("DB2_HOST", "localhost"), int(env.get("DB2_PORT", "50000")))
    url = env.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    embed, llm = env.get("EMBED_MODEL", "nomic-embed-text"), env.get("LLM_MODEL", "qwen3:14b")
    try:
        import requests

        names = {m.get("name", "") for m in requests.get(f"{url}/api/tags", timeout=1.5).json().get("models", [])}
        have = lambda m: m in names or f"{m}:latest" in names  # noqa: E731
        ollama = {"ok": have(embed), "embed_model": embed, "embed_ok": have(embed), "llm_model": llm,
                  "llm_ok": have(llm), "detail": "running"}
    except Exception as e:  # noqa: BLE001
        ollama = {"ok": False, "embed_model": embed, "embed_ok": False, "llm_model": llm, "llm_ok": False,
                  "detail": f"not reachable at {url} ({e.__class__.__name__})"}
    return {"db": {"ok": db_ok, "detail": db_detail, "database": env.get("DB2_DATABASE", "VECDB")},
            "ollama": ollama, "demo_switcher": demo_switcher_enabled()}


@app.get("/api/config")
def config() -> dict:
    demo = demo_switcher_enabled()
    return {"demo_switcher": demo, "modes": list(MODES), "status_help": sbom.STATUS_HELP,
            "demo_users": [{"user": u, "role": DEMO_ROLES[u]} for u in DEMO_USERS] if demo else []}


@app.get("/api/demo-users")
def demo_users() -> list[dict]:
    if not demo_switcher_enabled():
        raise HTTPException(404, {"kind": "input", "message": "Demo identity switcher is off"})
    return [{"user": u, "role": DEMO_ROLES[u]} for u in DEMO_USERS]


def _count_visible(user: str, password: str | None) -> int | None:
    import ibm_db

    conn = sbom.connect_as(user, timeout_s=8, password=password)
    try:
        r = ibm_db.fetch_tuple(ibm_db.exec_immediate(conn, "SELECT COUNT(*) FROM NEEDLE.ADV_DOC"))
        return int(r[0])
    except Exception:  # noqa: BLE001  (sign-in worked; the count is informational)
        return None
    finally:
        ibm_db.close(conn)


@app.post("/api/login")
def login(body: LoginIn) -> dict:
    user = body.user.strip().upper()
    demo = demo_switcher_enabled() and not body.password
    if demo and user not in DEMO_USERS:
        raise HTTPException(400, {"kind": "login", "message": f"{user} is not a demo identity"})
    if not demo and not body.password:
        raise HTTPException(400, {"kind": "login", "message": "Enter your Db2 user ID and password."})
    password = None if demo else body.password
    try:
        visible = _count_visible(user, password)
    except ValueError as e:
        raise HTTPException(400, {"kind": "login", "message": str(e)}) from None
    except Exception as e:  # noqa: BLE001
        msg = service._short_error(e)
        if "SQL30082N" in msg or "no password" in str(e):
            raise HTTPException(401, {"kind": "login", "message": f"Sign-in failed for {user}: {msg}"}) from None
        raise HTTPException(503, {"kind": "db", "message": f"Db2 unavailable: {msg}"}) from None
    token = _new_session(Session(user=user, password=password, demo=demo, visible_docs=visible))
    return {"token": token, "user": user, "demo": demo, "visible_docs": visible}


@app.post("/api/logout")
def logout(authorization: str | None = Header(default=None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    with _LOCK:
        _SESSIONS.pop(token, None)
    return {"ok": True}


@app.get("/api/me")
def me(s: Session = Depends(current_session)) -> dict:
    return {"user": s.user, "demo": s.demo, "visible_docs": s.visible_docs}


@app.post("/api/triage")
def triage(body: TriageIn, s: Session = Depends(current_session)) -> dict:
    res = service.do_run(s.user, body.query.strip(), int(body.k), None, password=s.password)
    s.last_result = None if res.get("fatal") else res
    if res.get("visible_docs") is not None:
        s.visible_docs = res["visible_docs"]
    return result_json(res)


@app.post("/api/memo")
def memo(body: MemoIn, s: Session = Depends(current_session)) -> dict:
    res = s.last_result
    if not res or "run" not in res:
        raise HTTPException(409, {"kind": "input", "message": "Run triage first; the memo uses those SQL rows."})
    from needle.llm_summary import MAX_ADVISORIES, generate_memo

    run = res["run"]
    advs = [{"adv_id": c["ADV_ID"], "summary": run.docs[c["ADV_ID"]].get("SUMMARY"),
             "details": run.docs[c["ADV_ID"]].get("DETAILS"),
             "packages": run.docs[c["ADV_ID"]].get("PACKAGES_LIST", []),
             "aliases": run.docs[c["ADV_ID"]].get("ALIASES", [])} for c in run.ranked(body.mode)][:MAX_ADVISORIES]
    ids = {a["adv_id"] for a in advs}
    rows = [r for r in res.get("exposure", []) if r["ADV_ID"] in ids]
    try:
        result = generate_memo(advs, rows)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, {"kind": "ollama", "message": f"Local LLM unavailable: {service._short_error(e)}"}) \
            from None
    v = result.verified
    return {"mode": body.mode, "model": result.model, "elapsed_s": round(result.elapsed_s, 2), "text": v.text,
            "kept": v.kept, "removed": [{"text": r.text, "reasons": list(r.reasons)} for r in v.removed],
            "raw_unverified": result.raw or "", "advisories": sorted(ids)}


@app.post("/api/compare")
def compare(body: TriageIn, _: Session = Depends(current_session)) -> dict:
    """Same query as each demo identity, side by side (demo switcher only: passwords come from needle/.env)."""
    if not demo_switcher_enabled():
        raise HTTPException(403, {"kind": "input", "message": "Compare identities needs NEEDLE_DEMO_SWITCHER=1 "
                                                              "(it signs in as three demo identities)."})
    out = []
    for u in DEMO_USERS:
        res = service.do_run(u, body.query.strip(), int(body.k), None, password=None)
        r = result_json(res)
        if not r.get("fatal"):
            r["embargoed_ids"] = sorted(a for a, d in r["docs"].items() if d["embargoed"])
            r.pop("sql", None)
        out.append({"role": DEMO_ROLES[u], **r})
    return {"query": body.query.strip(), "k": body.k, "identities": out}


def _read_json(name: str) -> Any:
    return json.loads((ROOT / "eval" / "results" / name).read_text(encoding="utf-8"))


@app.get("/api/finding")
def finding() -> dict:
    sel = _read_json("rcac_recall_vs_selectivity.json")
    corr = _read_json("rcac_correlated.json")
    ff = _read_json("rcac_ffsource.json")
    pc = _read_json("rcac_plancache.json")
    lit = _read_json("rcac_litcopy.json")["B_literal"]["approx10"]
    p10 = corr["measure"]["NDL_P10"]
    first = ff["steps"][0]
    fwd = next(r for r in pc["runs"] if r["order"] == "forward")
    plan_cache = {"statement": pc["statement"], "order": "forward", "steps": [
        {"user": st["user"], "cache_entries": len(st["cache_entries"]),
         "executable_id": st["cache_entries"][0]["executable_id"], "executions": st["cache_entries"][0]["num_executions"],
         "rows_read": st["cache_entries"][0]["delta_rows_read"], "rows_returned": st["cache_entries"][0]["delta_rows_returned"],
         "queries": len(st.get("rows_returned_per_query") or [])} for st in fwd["steps"]],
        "distinct_executable_ids": len({e["executable_id"] for st in fwd["steps"] for e in st["cache_entries"]})}
    return {
        "selectivity": sel,
        "estimate": {"permission_ff": first["permission_ff"][0], "vector_ixscan_est_rows": first["vector_ixscan_est_rows"],
                     "srchlsiz": first["srchlsiz"], "steps": [s["label"] for s in ff["steps"]],
                     "same_estimate_every_step": len({(s["permission_ff"][0], s["vector_ixscan_est_rows"])
                                                      for s in ff["steps"]}) == 1},
        "correlated": {"queries": p10["approx10"]["all"]["n"],
                       "p10_zero_rows": p10["approx10_rows_histogram"]["0_rows"],
                       "p10_recall_zero": p10["approx10_recall_histogram"]["recall_0"],
                       "coverage_by_p": corr["build"]["coverage_by_p"]},
        "plan_cache": plan_cache,
        "literal_control": {"heldout_recall": lit["heldout"]["recall_mean"], "all_recall": lit["all"]["recall_mean"],
                            "all_returned": lit["all"]["returned_mean"]},
        "sources": {"selectivity": "eval/results/rcac_recall_vs_selectivity.json",
                    "plan_cache": "eval/results/rcac_plancache.json",
                    "literal_control": "eval/results/rcac_litcopy.json",
                    "correlated": "eval/results/rcac_correlated.json",
                    "estimate": "eval/results/rcac_ffsource.json", "write_up": "docs/evidence/rcac_real.md"},
    }


def _canonical_eval() -> tuple[str, dict]:
    runs = sorted((ROOT / "eval" / "results").glob("2026*.json"))
    for p in reversed(runs):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("canonical"):
            return p.name, d
    raise HTTPException(404, {"kind": "input", "message": "No canonical evaluation run in eval/results"})


@app.get("/api/stats")
def stats() -> dict:
    """Measured numbers for the How-it-works page; each comes from a file in eval/results or docs/evidence."""
    name, ev = _canonical_eval()
    rel, fid = ev["relevance"], ev["ann_fidelity"]["approx_vs_exact"]["all"]
    out = {
        "eval_run": {"file": f"eval/results/{name}", "run_id": ev["run_id"], "session_user": ev["db"]["session_user"],
                     "queries": rel["triage"]["all"]["n"], "per_slice": rel["triage"]["paraphrase"]["n"]},
        "recall10": {s: {r: rel[r][s]["recall@10"] for r in ("triage", "approx", "bm25", "exact")}
                     for s in ("named", "masked", "paraphrase")},
        "latency_ms": {"triage_p50": rel["triage"]["all"]["latency_p50_ms"], "triage_p95": rel["triage"]["all"]["latency_p95_ms"],
                       "approx_p50": rel["approx"]["all"]["latency_p50_ms"], "exact_p50": rel["exact"]["all"]["latency_p50_ms"],
                       "embed_p50": ev["embedding"]["latency_p50_ms"]},
        "ann_overlap10": fid["overlap@10_mean"],
        "embargoed_rows": ev["embargo"]["embargoed_rows_visible_to_session_user"],
        "posting_fix": None, "tests": None,
    }
    m = re.search(r"^\| NDL_SENIOR \| BM25_SEARCH top 10 \| ([\d.]+) / [\d.]+ \| ([\d.]+) / [\d.]+ \|",
                  (ROOT / "docs" / "evidence" / "rcac_posting_overhead.md").read_text(encoding="utf-8"), re.M)
    if m:
        out["posting_fix"] = {"before_ms": float(m.group(1)), "after_ms": float(m.group(2)),
                              "file": "docs/evidence/rcac_posting_overhead.md"}
    t = re.search(r"(\d+) passed(?:, (\d+) skipped)?", (ROOT / "docs" / "evidence" / "pytest.txt").read_text(encoding="utf-8"))
    if t:
        out["tests"] = {"passed": int(t.group(1)), "skipped": int(t.group(2) or 0), "file": "docs/evidence/pytest.txt"}
    return out


_EXPLAIN_SECTIONS = ("APPROX_bound", "APPROX_k_param")


@app.get("/api/explain")
def explain() -> dict:
    """Captured db2exfmt plans from docs/evidence/g1_vector_index.md (no live EXPLAIN privilege needed)."""
    text = (ROOT / "docs" / "evidence" / "g1_vector_index.md").read_text(encoding="utf-8")
    out = []
    for name in _EXPLAIN_SECTIONS:
        m = re.search(rf"^### {name}\n(.*?)(?=^### |\Z)", text, re.S | re.M)
        if not m:
            continue
        body = m.group(1)
        sql = re.search(r"```sql\n(.*?)\n```", body, re.S)
        meta = re.search(r"EXPLAIN_TIME (\S+ \S+)\s+total cost ([\d.]+)\s+\*\*uses ADV_DOC_VIX: (\w+)\*\*", body)
        plan = re.search(r"db2exfmt access plan:\s*```\n(.*?)```", body, re.S)
        plan_text = plan.group(1) if plan else ""
        plan_text = plan_text.split("Extended Diagnostic Information")[0].rstrip()
        out.append({"name": name, "sql": sql.group(1).strip() if sql else "",
                    "explain_time": meta.group(1) if meta else None,
                    "total_cost": float(meta.group(2)) if meta else None,
                    "uses_vector_index": (meta.group(3) == "True") if meta else None, "plan": plan_text})
    return {"source": "docs/evidence/g1_vector_index.md", "plans": out}


_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")


@app.get("/api/evidence/{kind}/{name}")
def evidence(kind: str, name: str):
    if kind not in EVIDENCE_DIRS or not _SAFE_NAME.match(name):
        raise HTTPException(404, {"kind": "input", "message": "Not an evidence file"})
    folder, exts = EVIDENCE_DIRS[kind]
    allowed = {p.name: p for p in folder.iterdir() if p.is_file() and p.suffix in exts}
    if name not in allowed:
        raise HTTPException(404, {"kind": "input", "message": "Not an evidence file"})
    path = allowed[name]
    if path.suffix == ".png":
        return FileResponse(path, media_type="image/png")
    if path.suffix == ".json":
        return FileResponse(path, media_type="application/json")
    return PlainTextResponse(path.read_text(encoding="utf-8"))


# Built front end (npm run build in needle/web). Unknown paths fall back to index.html (single-page app).
@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, {"kind": "input", "message": "Unknown API path"})
    if not (WEB_DIST / "index.html").exists():
        return PlainTextResponse("NEEDLE API is running. Build the front end: cd web && npm ci && npm run build "
                                 "(or run the dev server: npm run dev, then open http://127.0.0.1:5173).", 200)
    target = (WEB_DIST / path).resolve()
    if path and target.is_file() and WEB_DIST.resolve() in target.parents:
        return FileResponse(target)
    return FileResponse(WEB_DIST / "index.html")


def main(argv: list[str] | None = None) -> int:
    import argparse

    import uvicorn

    ap = argparse.ArgumentParser(description="NEEDLE local API + web UI (loopback only)")
    ap.add_argument("--host", default=os.environ.get("NEEDLE_API_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("NEEDLE_API_PORT", "8600")))
    a = ap.parse_args(argv)
    if a.host not in LOOPBACK:
        print(f"refusing to bind {a.host}: NEEDLE serves 127.0.0.1 only", file=sys.stderr)
        return 2
    print(f"NEEDLE on http://127.0.0.1:{a.port}  (demo identity switcher: "
          f"{'ON - not authentication' if demo_switcher_enabled() else 'off'})")
    uvicorn.run(app, host=a.host, port=a.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
