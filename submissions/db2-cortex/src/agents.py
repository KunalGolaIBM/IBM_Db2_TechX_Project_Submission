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
import nlu


class S(TypedDict, total=False):
    question: str; role: str; session: str
    history: list; context: list; glossary: list
    sql: str; cached: bool; error: str; blocked: bool; fatal: bool; attempts: int
    cols: list; rows: list; chart: dict; insight: str
    trace: list; audit_hash: str; t0: float; oos: bool; followup: bool


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
    if s.get("followup"):
        return {"cached": False, "_detail": "Follow-up turn: cache bypassed (answer depends on previous turn)"}
    _, r = db.query(f"SELECT ID, SQL_TEXT, QUESTION, VECTOR_DISTANCE(EMB, {db.vlit(embed(s['question']))}, COSINE) AS D "
                    "FROM CORTEX.QUERY_CACHE WHERE ROLE = ? ORDER BY D FETCH FIRST 1 ROWS ONLY", (s.get("role", "analyst"),))
    if r and r[0][3] is not None and float(r[0][3]) < CACHE_THRESHOLD:
        sql2 = nlu.adapt(r[0][1], r[0][2], s["question"])
        if sql2:
            db.execute("UPDATE CORTEX.QUERY_CACHE SET HITS = HITS + 1 WHERE ID=?", (r[0][0],))
            note = " with constraints re-applied (slots)" if sql2 != r[0][1] else ""
            return {"sql": sql2, "cached": True, "_detail": f"Semantic cache HIT (cosine distance {float(r[0][3]):.3f}){note}"}
        return {"cached": False, "_detail": "Similar cached question rejected: its constraints (N / city / region) differ"}
    return {"cached": False, "_detail": "Semantic cache miss"}


def _where(*conds):
    return (" WHERE " + " AND ".join(conds)) if conds else ""


def b_fraud(sl, role):
    return ("SELECT CHANNEL, COUNT(*) AS TXNS, SUM(IS_FLAGGED) AS FLAGGED, ROUND(100.0*SUM(IS_FLAGGED)/COUNT(*),2) AS FRAUD_PCT "
            "FROM BANKING.TRANSACTIONS GROUP BY CHANNEL ORDER BY FRAUD_PCT DESC")


def b_default(sl, role):
    w = _where(*([f"B.CITY = '{c}'" for c in sl["cities"][:1]] + [f"B.REGION = '{r}'" for r in sl["regions"][:1]]))
    return ("SELECT B.NAME AS BRANCH, COUNT(*) AS LOANS, SUM(CASE WHEN L.STATUS='DEFAULTED' THEN 1 ELSE 0 END) AS DEFAULTED, "
            "ROUND(100.0*SUM(CASE WHEN L.STATUS='DEFAULTED' THEN 1 ELSE 0 END)/COUNT(*),2) AS DEFAULT_PCT "
            f"FROM BANKING.LOANS L JOIN BANKING.BRANCHES B ON L.BRANCH_ID=B.BRANCH_ID{w} GROUP BY B.NAME ORDER BY DEFAULT_PCT DESC")


def b_month(sl, role):
    return ("SELECT TO_CHAR(TXN_DATE,'YYYY-MM') AS MONTH, SUM(AMOUNT) AS VOLUME FROM BANKING.TRANSACTIONS "
            "GROUP BY TO_CHAR(TXN_DATE,'YYYY-MM') ORDER BY MONTH")


def b_top(sl, role):
    n = sl["n"] or 10
    w = _where(*[f"C.CITY = '{c}'" for c in sl["cities"][:1]])
    cols = "C.FULL_NAME, C.EMAIL, C.CITY" if role == "admin" else "C.CUSTOMER_ID, C.CITY, C.SEGMENT"
    return (f"SELECT {cols}, SUM(A.BALANCE) AS TOTAL_BALANCE FROM BANKING.CUSTOMERS C "
            f"JOIN BANKING.ACCOUNTS A ON A.CUSTOMER_ID=C.CUSTOMER_ID{w} GROUP BY {cols} ORDER BY TOTAL_BALANCE DESC FETCH FIRST {n} ROWS ONLY")


def b_region(sl, role):
    w = _where(*[f"B.REGION = '{r}'" for r in sl["regions"][:1]])
    return ("SELECT B.REGION, COUNT(DISTINCT A.ACCOUNT_ID) AS ACCOUNTS, SUM(A.BALANCE) AS TOTAL_BALANCE "
            f"FROM BANKING.ACCOUNTS A JOIN BANKING.BRANCHES B ON A.BRANCH_ID=B.BRANCH_ID{w} GROUP BY B.REGION ORDER BY TOTAL_BALANCE DESC")


def b_merchant(sl, role):
    lim = f" FETCH FIRST {sl['n']} ROWS ONLY" if sl["n"] else ""
    return f"SELECT MERCHANT_CAT, SUM(AMOUNT) AS SPEND FROM BANKING.TRANSACTIONS GROUP BY MERCHANT_CAT ORDER BY SPEND DESC{lim}"


DEMO = [  # (topic pattern, builder, constraints the template can apply)
    (r"fraud|flag|suspic", b_fraud, set()),
    (r"default|npa|bad loan", b_default, {"cities", "regions"}),
    (r"month|trend|volume", b_month, set()),
    (r"\btop\b|customer|balance|rich|wealth", b_top, {"n", "cities"}),
    (r"region|branch", b_region, {"regions"}),
    (r"merchant|categor|spend", b_merchant, {"n"}),
]


def plan_demo(q, role, history):
    """Offline planner: returns (sql, detail) or (None, reason). Handles N / city / region constraints and follow-ups."""
    ql, sl = q.lower(), nlu.extract(q)
    for pat, build, _ in DEMO:
        if re.search(pat, ql):
            return build(sl, role), "Demo planner (offline mode, 6 built-in topics)"
    if history:
        prev_q = history[0][0]
        psl = nlu.extract(prev_q)
        merged = {k: (sl[k] or psl[k]) for k in sl}
        asked = {k for k in sl if sl[k]}
        for pat, build, supports in DEMO:
            if re.search(pat, prev_q.lower()):
                if asked and not asked <= supports:
                    return None, "The offline planner cannot apply that filter to the previous topic; live LLM mode can."
                return build(merged, role), f"Follow-up on previous turn ({prev_q[:40]}...) with the new constraint"
    return None, ""


OOS_MSG = ("I am an enterprise banking assistant connected to Db2. I can only help with customer, account, transaction, "
           "loan and branch data. Try: \"Which branches have the highest loan default rate?\"")

PII_MSG = ("Customer names and emails are personal data, so the analyst role cannot see them. "
           "Switch to the admin role, or ask for the same result using CUSTOMER_ID.")

SCHEMA_DDL = """BANKING.CUSTOMERS(CUSTOMER_ID INT PK, FULL_NAME VARCHAR [PII], EMAIL VARCHAR [PII], CITY VARCHAR, SEGMENT VARCHAR {RETAIL,SME,PREMIUM}, JOINED_ON DATE)
BANKING.ACCOUNTS(ACCOUNT_ID INT PK, CUSTOMER_ID INT, BRANCH_ID INT, TYPE VARCHAR {SAVINGS,CURRENT,SALARY}, BALANCE DECIMAL, OPENED_ON DATE)
BANKING.TRANSACTIONS(TXN_ID BIGINT PK, ACCOUNT_ID INT, TXN_DATE DATE, AMOUNT DECIMAL, CHANNEL VARCHAR {UPI,CARD,NETBANK,ATM}, MERCHANT_CAT VARCHAR, IS_FLAGGED SMALLINT 1=suspected fraud)
BANKING.LOANS(LOAN_ID INT PK, CUSTOMER_ID INT, BRANCH_ID INT, PRINCIPAL DECIMAL, STATUS VARCHAR {ACTIVE,CLOSED,DEFAULTED}, ISSUED_ON DATE)
BANKING.BRANCHES(BRANCH_ID INT PK, NAME VARCHAR, CITY VARCHAR, REGION VARCHAR {NORTH,SOUTH,EAST,WEST})"""

PROMPT = """You are the SQL Writer agent for IBM Db2 LUW in an enterprise banking assistant.
SCHEMA (the only tables you may use):
{ddl}
Retrieved context (Db2 vector search):
{ctx}
Business rules:
{gl}
User role: {role}. If role is analyst, NEVER select FULL_NAME or EMAIL (use CUSTOMER_ID).
Rules: Db2 dialect only; qualify tables as BANKING.<TABLE>; SELECT or WITH only; use FETCH FIRST n ROWS ONLY (never LIMIT); month bucket = TO_CHAR(col,'YYYY-MM'); date arithmetic like CURRENT DATE - 90 DAYS; honour any number N in the question (top N, first N).
If the question is NOT about this banking data (weather, general knowledge, chit-chat), answer exactly: OUT_OF_SCOPE
If the role is analyst and the question asks for personal data (customer names, emails, contact details), answer exactly: PII_DENIED
If the question is a follow-up (them, those, filter, only), rewrite the previous SQL with the new constraint and keep the same intent.

EXAMPLES
Q: Top 5 customers by total balance
SQL: SELECT C.CUSTOMER_ID, C.CITY, SUM(A.BALANCE) AS TOTAL_BALANCE FROM BANKING.CUSTOMERS C JOIN BANKING.ACCOUNTS A ON A.CUSTOMER_ID = C.CUSTOMER_ID GROUP BY C.CUSTOMER_ID, C.CITY ORDER BY TOTAL_BALANCE DESC FETCH FIRST 5 ROWS ONLY
Q: Loan default rate by branch
SQL: SELECT B.NAME AS BRANCH, ROUND(100.0*SUM(CASE WHEN L.STATUS='DEFAULTED' THEN 1 ELSE 0 END)/COUNT(*),2) AS DEFAULT_PCT FROM BANKING.LOANS L JOIN BANKING.BRANCHES B ON L.BRANCH_ID = B.BRANCH_ID GROUP BY B.NAME ORDER BY DEFAULT_PCT DESC
Q: Monthly transaction volume in 2026
SQL: SELECT TO_CHAR(TXN_DATE,'YYYY-MM') AS MONTH, SUM(AMOUNT) AS VOLUME FROM BANKING.TRANSACTIONS WHERE YEAR(TXN_DATE) = 2026 GROUP BY TO_CHAR(TXN_DATE,'YYYY-MM') ORDER BY MONTH
Q: Which branches have a default rate above the average branch?
SQL: WITH R AS (SELECT B.NAME AS BRANCH, 100.0*SUM(CASE WHEN L.STATUS='DEFAULTED' THEN 1 ELSE 0 END)/COUNT(*) AS DEFAULT_PCT FROM BANKING.LOANS L JOIN BANKING.BRANCHES B ON L.BRANCH_ID = B.BRANCH_ID GROUP BY B.NAME) SELECT BRANCH, ROUND(DEFAULT_PCT,2) AS DEFAULT_PCT FROM R WHERE DEFAULT_PCT > (SELECT AVG(DEFAULT_PCT) FROM R) ORDER BY DEFAULT_PCT DESC
Q: Flagged transactions by channel in the last 90 days
SQL: SELECT CHANNEL, COUNT(*) AS FLAGGED FROM BANKING.TRANSACTIONS WHERE IS_FLAGGED = 1 AND TXN_DATE >= CURRENT DATE - 90 DAYS GROUP BY CHANNEL ORDER BY FLAGGED DESC
Previous question: Top 10 customers by balance
Previous SQL: SELECT C.CUSTOMER_ID, C.CITY, SUM(A.BALANCE) AS TOTAL_BALANCE FROM BANKING.CUSTOMERS C JOIN BANKING.ACCOUNTS A ON A.CUSTOMER_ID = C.CUSTOMER_ID GROUP BY C.CUSTOMER_ID, C.CITY ORDER BY TOTAL_BALANCE DESC FETCH FIRST 10 ROWS ONLY
Q: Filter them by Jaipur
SQL: SELECT C.CUSTOMER_ID, C.CITY, SUM(A.BALANCE) AS TOTAL_BALANCE FROM BANKING.CUSTOMERS C JOIN BANKING.ACCOUNTS A ON A.CUSTOMER_ID = C.CUSTOMER_ID WHERE C.CITY = 'Jaipur' GROUP BY C.CUSTOMER_ID, C.CITY ORDER BY TOTAL_BALANCE DESC FETCH FIRST 10 ROWS ONLY
Q: What is the weather in Delhi?
SQL: OUT_OF_SCOPE

NOW ANSWER
{hist}{err}Q: {q}
SQL:"""


@traced("Intent")
def intent(s):
    hist = bool(s.get("history"))
    if nlu.in_domain(s["question"], hist):
        fu = nlu.is_followup(s["question"], hist)
        return {"followup": fu, "_detail": "Follow-up: uses the previous turn" if fu else "In-domain banking data question"}
    if LLM is not None:  # live mode: no banking keyword, so let the LLM decide scope (it answers OUT_OF_SCOPE if unrelated)
        return {"_detail": "No banking keyword matched: the LLM will classify scope (OUT_OF_SCOPE if unrelated)"}
    return {"oos": True, "fatal": True, "error": OOS_MSG, "_detail": "Out of domain: no banking data entity found, no SQL attempted"}


@traced("SQL Writer")
def write_sql(s):
    n = s.get("attempts", 0)
    if LLM is None:
        q = s["question"]
        if re.search(r"\b(delete|drop|truncate|update|insert|alter)\b", q.lower()):
            return {"sql": "DELETE FROM BANKING.CUSTOMERS", "attempts": n + 1, "error": "", "cached": False,
                    "_detail": "Demo planner simulates an unsafe LLM output so the Guardrail can be shown"}
        sql, detail = plan_demo(q, s.get("role", "analyst"), s.get("history") or [])
        if sql:
            return {"sql": sql, "attempts": n + 1, "error": "", "cached": False, "_detail": detail}
        return {"sql": "", "attempts": n + 1, "fatal": True, "cached": False,
                "error": detail or "Demo mode understands: fraud, loan defaults, monthly volume, top customers, regions, merchant spend. Set LLM_PROVIDER in .env for free-form questions.",
                "_detail": "No demo template matched"}
    err = f"Previous attempt failed with: {s['error']}\nPrevious SQL: {s.get('sql','')}\nFix it.\n" if s.get("error") else ""
    hist = "".join(f"Previous question: {h[0]}\nPrevious SQL: {h[1]}\n" for h in reversed((s.get("history") or [])[:2]))
    msg = PROMPT.format(ddl=SCHEMA_DDL, ctx="\n".join(s["context"]), gl="\n".join(s.get("glossary", [])),
                        role=s.get("role", "analyst"), hist=hist, err=err, q=s["question"])
    try:
        out = LLM.invoke(msg).content
    except Exception as e:
        return {"sql": "", "attempts": n + 1, "fatal": True, "cached": False,
                "error": f"The language model is unavailable right now ({type(e).__name__}). Retry in a few seconds or set LLM_PROVIDER=demo.",
                "_detail": "LLM call failed: " + str(e)[:80]}
    if isinstance(out, list):
        out = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in out)
    out = re.sub(r"<think>.*?</think>", "", out, flags=re.S)  # some models emit reasoning tags
    out = re.sub(r"```(?:sql)?|```", "", out).strip()
    if out.upper().startswith("OUT_OF_SCOPE"):
        return {"sql": "", "attempts": n + 1, "oos": True, "fatal": True, "cached": False, "error": OOS_MSG, "_detail": "LLM classified the question as out of domain"}
    if out.upper().startswith("PII_DENIED"):
        return {"sql": "", "attempts": n + 1, "blocked": True, "fatal": True, "cached": False, "error": PII_MSG,
                "_detail": "Blocked: personal data requested by the analyst role"}
    m = re.search(r"\b(WITH|SELECT|DELETE|DROP|UPDATE|INSERT)\b", out, re.I)
    sql = out[m.start():].strip().rstrip(";") if m else out
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
    keep = [k for k, c in enumerate(cols) if c.upper() not in PII_COLUMNS]  # PII never leaves Db2 toward the LLM
    sample = json.dumps([[cols[k] for k in keep]] + [[r[k] for k in keep] for r in rows[:15]], default=str)
    try:
        ins = LLM.invoke(f"You are a banking analyst. In at most 2 sentences, state the key insight with concrete numbers for the question: {s['question']}\nData (first rows, JSON): {sample}").content
        if isinstance(ins, list):
            ins = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in ins)
    except Exception as e:
        top = f" Top: {rows[0][0]} ({rows[0][1]})." if len(cols) > 1 else ""
        return {"chart": chart, "insight": f"Returned {len(rows)} rows.{top}", "_detail": "Insight LLM unavailable, used summary: " + str(e)[:60]}
    return {"chart": chart, "insight": ins, "_detail": "LLM insight + chart spec (PII columns excluded from the prompt)"}


@traced("Auditor")
def persist(s):
    ok = not s.get("error")
    if ok and not s.get("cached") and not s.get("followup"):
        db.execute(f"INSERT INTO CORTEX.QUERY_CACHE (QUESTION, SQL_TEXT, ROLE, EMB) VALUES (?,?,?,{db.vlit(embed(s['question']))})",
                   (s["question"][:500], s["sql"], s.get("role", "analyst")))
    if ok:
        db.execute("INSERT INTO CORTEX.SESSION_MEMORY (SESSION_ID, TS, QUESTION, SQL_TEXT) VALUES (?,?,?,?)",
                   (s["session"], dt.datetime.now(dt.timezone.utc).isoformat(), s["question"][:500], s["sql"]))
    status = "OK" if ok else ("OUT_OF_SCOPE" if s.get("oos") else ("BLOCKED" if s.get("blocked") else "ERROR"))
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


def after_intent(s):
    return "persist" if s.get("oos") else "retrieve"


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
for n, f in [("recall", recall), ("intent", intent), ("retrieve", retrieve), ("cache", cache), ("write", write_sql), ("guard", guard_node),
             ("exec", execute), ("analyze", analyze), ("persist", persist)]:
    g.add_node(n, f)
g.set_entry_point("recall")
g.add_edge("recall", "intent")
g.add_conditional_edges("intent", after_intent, {"retrieve": "retrieve", "persist": "persist"})
g.add_edge("retrieve", "cache")
g.add_conditional_edges("cache", after_cache, {"guard": "guard", "write": "write"})
g.add_conditional_edges("write", after_write, {"guard": "guard", "persist": "persist"})
g.add_conditional_edges("guard", after_guard, {"exec": "exec", "write": "write", "persist": "persist"})
g.add_conditional_edges("exec", after_exec, {"analyze": "analyze", "write": "write", "persist": "persist"})
g.add_edge("analyze", "persist"); g.add_edge("persist", END)
GRAPH = g.compile()
