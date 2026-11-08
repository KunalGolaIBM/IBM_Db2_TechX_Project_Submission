"""LangGraph multi-agent pipeline. Every stateful component lives in IBM Db2."""
import re
import time
import json
import hashlib
import datetime as dt
from typing import TypedDict
from langgraph.graph import StateGraph, END
import db
from config import CACHE_THRESHOLD, EMBED_DIM, PII_COLUMNS
from embeddings import embed, EMB
from llm import LLM
import guard


class S(TypedDict, total=False):
    question: str; role: str; session: str
    history: list; context: list; glossary: list
    sql: str; cached: bool; error: str; blocked: bool; fatal: bool; attempts: int
    cols: list; rows: list; chart: dict; insight: str
    trace: list; audit_hash: str; t0: float


def traced(name):
    def deco(fn):
        def run(s):
            t = time.time()
            out = fn(s) or {}
            detail = out.pop("_detail", "")
            tr = list(s.get("trace", [])) + [{"agent": name, "ms": int((time.time() - t) * 1000), "detail": detail}]
            out["trace"] = tr
            return out
        return run
    return deco


@traced("Memory")
def recall(s):
    _, r = db.query("SELECT QUESTION, SQL_TEXT FROM CORTEX.SESSION_MEMORY WHERE SESSION_ID=? ORDER BY ID DESC FETCH FIRST 3 ROWS ONLY", (s["session"],))
    return {"history": r, "attempts": 0, "t0": time.time(), "_detail": f"{len(r)} prior turns loaded from Db2"}


@traced("Retriever")
def retrieve(s):
    _, r = db.query(f"SELECT KIND, NAME, DESCRIPTION, VECTOR_DISTANCE(EMB, {db.vlit(embed(s['question']))}, COSINE) AS D "
                    "FROM CORTEX.SEMANTIC_LAYER ORDER BY D FETCH FIRST 6 ROWS ONLY")
    gl = []
    try:
        from langchain_db2 import DB2VS
        from langchain_community.vectorstores.utils import DistanceStrategy
        store = DB2VS(embedding_function=EMB, table_name="CORTEX_GLOSSARY", client=db.conn(), distance_strategy=DistanceStrategy.COSINE)
        gl = [d.page_content for d in store.similarity_search(s["question"], k=3)]
    except Exception:
        pass
    return {"context": [f"{a} {b}: {c}" for a, b, c, _ in r], "glossary": gl,
            "_detail": "Db2 VECTOR_DISTANCE top-6: " + ", ".join(x[1] for x in r)}


@traced("Cache")
def cache(s):
    _, r = db.query(f"SELECT ID, SQL_TEXT, VECTOR_DISTANCE(EMB, {db.vlit(embed(s['question']))}, COSINE) AS D "
                    "FROM CORTEX.QUERY_CACHE ORDER BY D FETCH FIRST 1 ROWS ONLY")
    if r and r[0][2] is not None and float(r[0][2]) < CACHE_THRESHOLD:
        db.execute("UPDATE CORTEX.QUERY_CACHE SET HITS = HITS + 1 WHERE ID=?", (r[0][0],))
        return {"sql": r[0][1], "cached": True, "_detail": f"Semantic cache HIT (cosine distance {float(r[0][2]):.3f})"}
    return {"cached": False, "_detail": "Semantic cache miss"}


DEMO = [
    (r"fraud|flag|suspic", "SELECT CHANNEL, COUNT(*) AS TXNS, SUM(IS_FLAGGED) AS FLAGGED, ROUND(100.0*SUM(IS_FLAGGED)/COUNT(*),2) AS FRAUD_PCT FROM BANKING.TRANSACTIONS GROUP BY CHANNEL ORDER BY FRAUD_PCT DESC"),
    (r"default|npa|bad loan", "SELECT B.NAME AS BRANCH, COUNT(*) AS LOANS, SUM(CASE WHEN L.STATUS='DEFAULTED' THEN 1 ELSE 0 END) AS DEFAULTED, ROUND(100.0*SUM(CASE WHEN L.STATUS='DEFAULTED' THEN 1 ELSE 0 END)/COUNT(*),2) AS DEFAULT_PCT FROM BANKING.LOANS L JOIN BANKING.BRANCHES B ON L.BRANCH_ID=B.BRANCH_ID GROUP BY B.NAME ORDER BY DEFAULT_PCT DESC"),
    (r"month|trend|volume", "SELECT TO_CHAR(TXN_DATE,'YYYY-MM') AS MONTH, SUM(AMOUNT) AS VOLUME FROM BANKING.TRANSACTIONS GROUP BY TO_CHAR(TXN_DATE,'YYYY-MM') ORDER BY MONTH"),
    (r"top|customer|balance|rich|wealth", "SELECT C.FULL_NAME, C.EMAIL, C.CITY, SUM(A.BALANCE) AS TOTAL_BALANCE FROM BANKING.CUSTOMERS C JOIN BANKING.ACCOUNTS A ON A.CUSTOMER_ID=C.CUSTOMER_ID GROUP BY C.FULL_NAME, C.EMAIL, C.CITY ORDER BY TOTAL_BALANCE DESC FETCH FIRST 10 ROWS ONLY"),
    (r"region|branch", "SELECT B.REGION, COUNT(DISTINCT A.ACCOUNT_ID) AS ACCOUNTS, SUM(A.BALANCE) AS TOTAL_BALANCE FROM BANKING.ACCOUNTS A JOIN BANKING.BRANCHES B ON A.BRANCH_ID=B.BRANCH_ID GROUP BY B.REGION ORDER BY TOTAL_BALANCE DESC"),
    (r"merchant|categor|spend", "SELECT MERCHANT_CAT, SUM(AMOUNT) AS SPEND FROM BANKING.TRANSACTIONS GROUP BY MERCHANT_CAT ORDER BY SPEND DESC"),
]

PROMPT = """You are the SQL Writer agent for IBM Db2 (LUW). Use ONLY these governed objects:
{ctx}
Business rules:
{gl}
Prior turns (for follow-ups): {hist}
Rules: Db2 dialect; fully qualify tables as BANKING.<TABLE>; SELECT only; use FETCH FIRST n ROWS ONLY (never LIMIT); month bucket = TO_CHAR(col,'YYYY-MM').
{err}
Question: {q}
Return ONLY the SQL, no markdown."""


@traced("SQL Writer")
def write_sql(s):
    n = s.get("attempts", 0)
    if LLM is None:
        q = s["question"].lower()
        if re.search(r"\b(delete|drop|truncate|update|insert|alter)\b", q):
            return {"sql": "DELETE FROM BANKING.CUSTOMERS", "attempts": n + 1, "error": "", "cached": False,
                    "_detail": "Demo planner simulates an unsafe LLM output so the Guardrail can be shown"}
        for pat, sql in DEMO:
            if re.search(pat, q):
                if s.get("role") != "admin" and "FULL_NAME" in sql:
                    sql = ("SELECT C.CUSTOMER_ID, C.CITY, C.SEGMENT, SUM(A.BALANCE) AS TOTAL_BALANCE FROM BANKING.CUSTOMERS C "
                           "JOIN BANKING.ACCOUNTS A ON A.CUSTOMER_ID=C.CUSTOMER_ID GROUP BY C.CUSTOMER_ID, C.CITY, C.SEGMENT "
                           "ORDER BY TOTAL_BALANCE DESC FETCH FIRST 10 ROWS ONLY")
                return {"sql": sql, "attempts": n + 1, "error": "", "cached": False, "_detail": "Demo planner (offline mode, 6 built-in topics)"}
        return {"sql": "", "attempts": n + 1, "fatal": True, "cached": False,
                "error": "Demo mode understands: fraud, loan defaults, monthly volume, top customers, regions, merchant spend. Set LLM_PROVIDER in .env for free-form questions.",
                "_detail": "No demo template matched"}
    err = f"Previous attempt failed with: {s['error']}\nPrevious SQL: {s.get('sql','')}\nFix it." if s.get("error") else ""
    msg = PROMPT.format(ctx="\n".join(s["context"]), gl="\n".join(s.get("glossary", [])), hist=json.dumps(s.get("history", []), default=str),
                        err=err, q=s["question"])
    out = LLM.invoke(msg).content
    sql = re.sub(r"```(?:sql)?|```", "", out).strip()
    return {"sql": sql, "attempts": n + 1, "error": "", "cached": False, "_detail": f"LLM draft (attempt {n + 1})"}


@traced("Guardrail")
def guard_node(s):
    ok, res = guard.validate(s["sql"], s.get("role", "analyst"))
    if ok:
        return {"sql": res, "error": "", "blocked": False, "fatal": False, "_detail": "AST + allow-list + PII policy + Db2 PREPARE passed"}
    return {"error": res, "blocked": True, "fatal": guard.is_fatal(res), "_detail": "BLOCKED: " + res}


@traced("Executor")
def execute(s):
    try:
        cols, rows = db.query(s["sql"])
    except Exception as e:
        return {"error": str(e)[:300], "blocked": False, "_detail": "Db2 error -> self-repair"}
    if s.get("role") != "admin":
        idx = [i for i, c in enumerate(cols) if c.upper() in PII_COLUMNS]
        for r in rows:
            for i in idx:
                r[i] = "••••••"
    return {"cols": cols, "rows": rows, "error": "", "_detail": f"{len(rows)} rows" + (" (PII masked)" if s.get("role") != "admin" else "")}


def _num(x):
    try:
        float(x)
        return not isinstance(x, bool)
    except Exception:
        return False


@traced("Analyst")
def analyze(s):
    cols, rows = s.get("cols", []), s.get("rows", [])
    chart = {}
    if rows and len(cols) >= 2 and _num(rows[0][1]):
        kind = "line" if re.search(r"MONTH|DATE|YEAR", cols[0], re.I) else "bar"
        chart = {"type": kind, "labels": [str(r[0]) for r in rows[:30]], "label": cols[1], "data": [float(r[1]) for r in rows[:30]]}
    if LLM is None or not rows:
        top = f" Top: {rows[0][0]} ({rows[0][1]})." if rows and len(cols) > 1 else ""
        return {"chart": chart, "insight": f"Returned {len(rows)} rows.{top}", "_detail": "Chart spec + summary"}
    sample = json.dumps([cols] + rows[:15], default=str)
    ins = LLM.invoke(f"In 2 sentences, give a business insight for: {s['question']}\nData: {sample}").content
    return {"chart": chart, "insight": ins, "_detail": "LLM insight + chart spec"}


@traced("Auditor")
def persist(s):
    ok = not s.get("error")
    if ok and not s.get("cached"):
        db.execute(f"INSERT INTO CORTEX.QUERY_CACHE (QUESTION, SQL_TEXT, EMB) VALUES (?,?,{db.vlit(embed(s['question']))})",
                   (s["question"][:500], s["sql"]))
    if ok:
        db.execute("INSERT INTO CORTEX.SESSION_MEMORY (SESSION_ID, TS, QUESTION, SQL_TEXT) VALUES (?,?,?,?)",
                   (s["session"], dt.datetime.now(dt.timezone.utc).isoformat(), s["question"][:500], s["sql"]))
    status = "OK" if ok else ("BLOCKED" if s.get("blocked") else "ERROR")
    ts = dt.datetime.now(dt.timezone.utc).isoformat()
    with db._lock:  # serialise chain appends so concurrent requests cannot fork the chain
        _, r = db.query("SELECT HASH FROM CORTEX.AUDIT_LOG ORDER BY ID DESC FETCH FIRST 1 ROWS ONLY")
        prev = r[0][0].strip() if r else "0" * 64
        h = chain_hash(prev, ts, s["role"], s["question"][:500], s.get("sql", "")[:4000], status)
        db.execute("INSERT INTO CORTEX.AUDIT_LOG (TS,ROLE,QUESTION,SQL_TEXT,STATUS,ROWS_RETURNED,LATENCY_MS,PREV_HASH,HASH) VALUES (?,?,?,?,?,?,?,?,?)",
                   (ts, s["role"], s["question"][:500], s.get("sql", "")[:4000], status, len(s.get("rows", [])), int((time.time() - s["t0"]) * 1000), prev, h))
    return {"audit_hash": h, "_detail": f"Hash-chained audit row {h[:10]}… written to Db2"}


def chain_hash(prev, ts, role, q, sql, status):
    return hashlib.sha256("|".join([prev, ts, role, q, sql, status]).encode()).hexdigest()


def after_cache(s):
    return "guard" if s.get("cached") else "write"


def after_write(s):
    return "persist" if s.get("fatal") else "guard"


def after_guard(s):
    if not s.get("error"):
        return "exec"
    return "write" if (s.get("attempts", 0) < 3 and not s.get("fatal")) else "persist"


def after_exec(s):
    if not s.get("error"):
        return "analyze"
    return "write" if s.get("attempts", 0) < 3 else "persist"


g = StateGraph(S)
for n, f in [("recall", recall), ("retrieve", retrieve), ("cache", cache), ("write", write_sql), ("guard", guard_node),
             ("exec", execute), ("analyze", analyze), ("persist", persist)]:
    g.add_node(n, f)
g.set_entry_point("recall")
g.add_edge("recall", "retrieve"); g.add_edge("retrieve", "cache")
g.add_conditional_edges("cache", after_cache, {"guard": "guard", "write": "write"})
g.add_conditional_edges("write", after_write, {"guard": "guard", "persist": "persist"})
g.add_conditional_edges("guard", after_guard, {"exec": "exec", "write": "write", "persist": "persist"})
g.add_conditional_edges("exec", after_exec, {"analyze": "analyze", "write": "write", "persist": "persist"})
g.add_edge("analyze", "persist"); g.add_edge("persist", END)
GRAPH = g.compile()
