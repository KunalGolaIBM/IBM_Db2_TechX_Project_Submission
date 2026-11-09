import os
import decimal
import datetime as dt
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import db
from agents import GRAPH, chain_hash
from config import LLM_PROVIDER
from embeddings import EMB_NAME

app = FastAPI(title="Db2 Cortex")
HERE = os.path.dirname(__file__)


class Ask(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    role: Literal["analyst", "admin"] = "analyst"
    session: str = Field("default", max_length=40, pattern=r"^[A-Za-z0-9_-]+$")


def js(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    return v


@app.post("/api/ask")
def ask(a: Ask):
    try:
        out = GRAPH.invoke({"question": a.question.strip(), "role": a.role, "session": a.session})
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Backend error (is Db2 running and seeded?): {str(e)[:200]}")
    return {"sql": out.get("sql", ""), "cols": out.get("cols", []), "rows": [[js(x) for x in r] for r in out.get("rows", [])],
            "chart": out.get("chart", {}), "insight": out.get("insight", ""), "error": out.get("error", ""),
            "cached": out.get("cached", False), "out_of_scope": out.get("oos", False), "trace": out.get("trace", []), "audit_hash": out.get("audit_hash", "")}


@app.get("/api/audit")
def audit():
    cols, rows = db.query("SELECT ID,TS,ROLE,QUESTION,SUBSTR(SQL_TEXT,1,110) AS SQL_TEXT,STATUS,ROWS_RETURNED,LATENCY_MS,HASH FROM CORTEX.AUDIT_LOG ORDER BY ID DESC FETCH FIRST 50 ROWS ONLY")
    return {"cols": cols, "rows": [[js(x) for x in r] for r in rows]}


@app.get("/api/audit/verify")
def verify():
    _, rows = db.query("SELECT ID,TS,ROLE,QUESTION,SQL_TEXT,STATUS,PREV_HASH,HASH FROM CORTEX.AUDIT_LOG ORDER BY ID")
    prev = "0" * 64
    for r in rows:
        if r[6].strip() != prev or chain_hash(prev, r[1], r[2], r[3], r[4], r[5]) != r[7].strip():
            return {"valid": False, "broken_at": r[0], "checked": len(rows)}
        prev = r[7].strip()
    return {"valid": True, "checked": len(rows)}


@app.post("/api/audit/tamper-demo")
def tamper_demo():
    """Simulates tampering inside a transaction that is ALWAYS rolled back, then shows the chain detecting it."""
    with db._lock:
        before = verify()
        if not before["checked"]:
            return {"before": before, "after": before, "note": "Ask a question first so there is something to tamper with."}
        cur = db.conn().cursor()
        try:
            cur.execute("UPDATE CORTEX.AUDIT_LOG SET QUESTION='(tampered)' WHERE ID=(SELECT MIN(ID) FROM CORTEX.AUDIT_LOG)")
            after = verify()
        finally:
            db.conn().rollback()
            cur.close()
        return {"before": before, "after": after, "note": "Simulated edit of audit row #1 (rolled back, nothing was changed)."}


@app.get("/api/db2/inspect")
def inspect():
    def one(sql):
        try:
            return db.query(sql)[1][0][0]
        except Exception:
            return 0
    return {"version": db.version(),
            "customers": one("SELECT COUNT(*) FROM BANKING.CUSTOMERS"), "accounts": one("SELECT COUNT(*) FROM BANKING.ACCOUNTS"),
            "transactions": one("SELECT COUNT(*) FROM BANKING.TRANSACTIONS"), "loans": one("SELECT COUNT(*) FROM BANKING.LOANS"),
            "semantic_layer": one("SELECT COUNT(*) FROM CORTEX.SEMANTIC_LAYER"), "glossary": one("SELECT COUNT(*) FROM CORTEX_GLOSSARY"),
            "cache_entries": one("SELECT COUNT(*) FROM CORTEX.QUERY_CACHE"), "cache_hits": one("SELECT COALESCE(SUM(HITS),0) FROM CORTEX.QUERY_CACHE"),
            "memory_turns": one("SELECT COUNT(*) FROM CORTEX.SESSION_MEMORY"), "audit_blocks": one("SELECT COUNT(*) FROM CORTEX.AUDIT_LOG"),
            "audit_blocked": one("SELECT COUNT(*) FROM CORTEX.AUDIT_LOG WHERE STATUS <> 'OK'")}


@app.get("/api/health")
def health():
    try:
        cached = db.query("SELECT COUNT(*) FROM CORTEX.QUERY_CACHE")[1][0][0]
        return {"db2": db.version(), "llm": LLM_PROVIDER, "embeddings": EMB_NAME, "cache_entries": cached}
    except Exception as e:
        return {"db2": "unreachable", "llm": LLM_PROVIDER, "embeddings": EMB_NAME, "cache_entries": 0, "error": str(e)[:120]}


@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"))


app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
