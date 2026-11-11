"""Brain: Gemini via LangChain structured output, with deterministic offline fallbacks."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from .config import Settings, get_settings
from .memory import hash_embed, l2_normalize

log = logging.getLogger("redb.llm")


class Diagnosis(BaseModel):
    headline: str = Field(description="One-line summary of why the query is slow")
    plain_english: str = Field(description="2-4 sentences a developer can understand")
    root_causes: list[str] = Field(default_factory=list)
    severity: Literal["low", "medium", "high"] = "medium"


class Rewrite(BaseModel):
    should_rewrite: bool = False
    sql: str = Field(default="", description="Complete semantically equivalent Db2 SELECT, no trailing semicolon")
    rationale: str = ""


class Answer(BaseModel):
    sql: str = Field(description="One read-only Db2 SELECT that answers the question, no trailing semicolon")
    explanation: str = Field(description="One sentence saying what the query shows")


class Narrative(BaseModel):
    summary: str


DIAGNOSE_PROMPT = """You are a senior IBM Db2 performance engineer. Diagnose why this statement is expensive.
Use ONLY the evidence given (access plan, MON_GET metrics, catalog). Be specific and concise.

SQL:
{sql}

Access plan (from Db2 EXPLAIN tables):
{plan}

Runtime metrics (MON_GET_PKG_CACHE_STMT):
{metrics}

Catalog (SYSCAT.COLUMNS / SYSCAT.INDEXES):
{catalog}"""

REWRITE_PROMPT = """You are a senior IBM Db2 SQL engineer. If, and only if, the statement can be rewritten into a
SEMANTICALLY EQUIVALENT Db2 SELECT that the optimizer can execute more cheaply, return it.
Typical wins: sargable date ranges instead of YEAR()/MONTH() on a column; NOT EXISTS instead of NOT IN
(only equivalent when the subquery column cannot be NULL - check the catalog); a UNION of two selects over the
same table that differ in one literal -> one SELECT DISTINCT with an IN list.
Keep the same output columns, column order, ordering and row limits. Return should_rewrite=false if unsure.
Never write DML or DDL.

SQL:
{sql}

Access plan:
{plan}

Catalog:
{catalog}"""


ASK_PROMPT = """You answer questions about an IBM Db2 database and its tuning history by writing ONE read-only
Db2 SELECT statement. Never write DML, DDL or CALL. Never select the EMBEDDING column. Available objects:

REDB.CHANGES (temporal change ledger; add FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-31' for full history):
  CHANGE_ID, KIND (INDEX|DROP_INDEX|REWRITE|RUNSTATS), TITLE, STMT_TEXT, DDL, UNDO_DDL,
  STATUS (PROPOSED|APPLIED|ADOPTED|ROLLED_BACK|FAILED), COST_BEFORE, COST_AFTER, MS_BEFORE, MS_AFTER,
  RATIONALE, APPROVED_BY, SYS_START, SYS_END
REDB.TUNING_MEMORY: CASE_ID, CREATED_AT, SIGNATURE, FIX_KIND, FIX_DETAIL, GAIN_PCT
RETAIL.CUSTOMERS(CUSTOMER_ID, FULL_NAME, EMAIL, COUNTRY, SEGMENT, SIGNUP_DATE)
RETAIL.PRODUCTS(PRODUCT_ID, SKU, PRODUCT_NAME, CATEGORY, UNIT_PRICE)
RETAIL.ORDERS(ORDER_ID, CUSTOMER_ID, ORDER_DATE, STATUS, CHANNEL, TOTAL_AMOUNT)
RETAIL.ORDER_ITEMS(ORDER_ID, LINE_NO, PRODUCT_ID, QUANTITY, UNIT_PRICE)
SYSCAT.TABLES(TABSCHEMA, TABNAME, CARD, STATS_TIME), SYSCAT.INDEXES(TABSCHEMA, TABNAME, INDNAME, COLNAMES, UNIQUERULE)
TABLE(MON_GET_PKG_CACHE_STMT('D', NULL, NULL, -2)): NUM_EXECUTIONS, STMT_EXEC_TIME (ms), ROWS_READ, ROWS_RETURNED, STMT_TEXT (CLOB: use CAST(SUBSTR(STMT_TEXT,1,300) AS VARCHAR(300)))
TABLE(MON_GET_TABLE('RETAIL', '', -2)): TABNAME, TABLE_SCANS, ROWS_READ, ROWS_INSERTED, ROWS_UPDATED, ROWS_DELETED
TABLE(MON_GET_INDEX('RETAIL', '', -2)): TABNAME, IID, INDEX_SCANS, INDEX_ONLY_SCANS

Question: {question}"""

# offline mode: keyword -> canned query (first match wins)
CANNED = [
    (("history", "timeline", "when", "time"),
     "SELECT CHANGE_ID, KIND, STATUS, TITLE, SYS_START, SYS_END FROM REDB.CHANGES "
     "FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-31' ORDER BY CHANGE_ID, SYS_START",
     "Every version of every ledger row (system-period temporal history)."),
    (("roll", "undo"),
     "SELECT CHANGE_ID, KIND, TITLE, UNDO_DDL FROM REDB.CHANGES WHERE STATUS = 'ROLLED_BACK' ORDER BY CHANGE_ID DESC",
     "Changes that were rolled back."),
    (("change", "ledger", "applied", "fix", "gain", "improve"),
     "SELECT CHANGE_ID, KIND, STATUS, TITLE, MS_BEFORE, MS_AFTER, DECIMAL(100 * (MS_BEFORE - MS_AFTER) / "
     "NULLIF(MS_BEFORE, 0), 5, 1) AS GAIN_PCT FROM REDB.CHANGES ORDER BY CHANGE_ID DESC",
     "Current state of the change ledger with measured gains."),
    (("memory", "learn", "case", "remember"),
     "SELECT CASE_ID, CREATED_AT, FIX_KIND, GAIN_PCT, FIX_DETAIL FROM REDB.TUNING_MEMORY ORDER BY GAIN_PCT DESC",
     "Solved cases stored in vector memory."),
    (("index",),
     "SELECT TABNAME, INDNAME, COLNAMES, UNIQUERULE FROM SYSCAT.INDEXES WHERE TABSCHEMA = 'RETAIL' ORDER BY TABNAME",
     "Indexes on the RETAIL schema."),
    (("scan", "table", "read", "write"),
     "SELECT TABNAME, TABLE_SCANS, ROWS_READ, ROWS_INSERTED + ROWS_UPDATED + ROWS_DELETED AS ROWS_WRITTEN "
     "FROM TABLE(MON_GET_TABLE('RETAIL', '', -2)) T ORDER BY ROWS_READ DESC",
     "Table activity since database activation (MON_GET_TABLE)."),
]
TOP_ANSWER = ("SELECT NUM_EXECUTIONS, STMT_EXEC_TIME AS TOTAL_MS, ROWS_READ, ROWS_RETURNED, "
              "CAST(SUBSTR(STMT_TEXT, 1, 300) AS VARCHAR(300)) AS STMT FROM TABLE(MON_GET_PKG_CACHE_STMT('D', NULL, NULL, -2)) T "
              "WHERE STMT_TEXT LIKE '%RETAIL.%' AND STMT_TEXT NOT LIKE '%MON_GET%' ORDER BY STMT_EXEC_TIME DESC "
              "FETCH FIRST 10 ROWS ONLY", "The costliest RETAIL statements in the package cache.")


def heuristic_answer(question: str) -> "Answer":
    q = question.lower()
    sql, why = next(((s, w) for keys, s, w in CANNED if any(k in q for k in keys)), TOP_ANSWER)
    return Answer(sql=sql, explanation=why + " (offline mode: matched by keyword, set GOOGLE_API_KEY for free-form questions)")


class Brain:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or get_settings()
        self.online = bool(self.s.google_api_key)
        self.last_error: str | None = None
        self._chat = self._emb = None
        if self.online:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
                self._chat = ChatGoogleGenerativeAI(model=self.s.gemini_model, google_api_key=self.s.google_api_key,
                                                    temperature=0)
                self._emb = GoogleGenerativeAIEmbeddings(model=self.s.gemini_embed_model,
                                                         google_api_key=self.s.google_api_key)
            except Exception as e:  # noqa: BLE001
                self._fail(e)

    @property
    def mode(self) -> str:
        return f"Gemini ({self.s.gemini_model})" if self.online else "offline heuristics"

    def _fail(self, e: Exception) -> None:
        self.last_error = str(e)[:300]
        self.online = False  # stay offline for the rest of this run instead of failing per call
        log.warning("Gemini unavailable, falling back to heuristics: %s", self.last_error)

    def _structured(self, model: type[BaseModel], prompt: str) -> BaseModel | None:
        if not (self.online and self._chat):
            return None
        try:
            return self._chat.with_structured_output(model).invoke(prompt)
        except Exception as e:  # noqa: BLE001
            self._fail(e)
            return None

    # -- public API ------------------------------------------------------
    def diagnose(self, ctx: dict[str, Any]) -> dict[str, Any]:
        r = self._structured(Diagnosis, DIAGNOSE_PROMPT.format(
            sql=ctx["sql"], plan=ctx.get("plan_summary", ""), metrics=json.dumps(ctx.get("metrics", {})),
            catalog=ctx.get("catalog", "")))
        out = (r or heuristic_diagnosis(ctx)).model_dump()
        out["source"] = "gemini" if r else "heuristic"
        return out

    def rewrite(self, ctx: dict[str, Any]) -> dict[str, Any]:
        r = self._structured(Rewrite, REWRITE_PROMPT.format(
            sql=ctx["sql"], plan=ctx.get("plan_summary", ""), catalog=ctx.get("catalog", "")))
        out = (r or heuristic_rewrite(ctx["sql"], ctx.get("not_null_cols", set()))).model_dump()
        out["source"] = "gemini" if r else "heuristic"
        return out

    def narrate(self, report: dict[str, Any]) -> str:
        r = self._structured(Narrative, "Write a 4-6 sentence executive summary of this Db2 tuning run for an "
                                        "engineering manager. Quote the measured numbers.\n" + json.dumps(report, default=str))
        return r.summary if r else heuristic_narrative(report)

    def ask(self, question: str) -> dict[str, Any]:
        """Natural-language question -> one read-only SELECT (the caller still runs it through sqlguard)."""
        r = self._structured(Answer, ASK_PROMPT.format(question=question))
        out = (r or heuristic_answer(question)).model_dump()
        out["source"] = "gemini" if r else "heuristic"
        return out

    def embed(self, text: str) -> list[float]:
        if self.online and self._emb:
            try:
                v = self._emb.embed_query(text)
                return l2_normalize(list(v)[: self.s.embed_dim])
            except Exception as e:  # noqa: BLE001
                self._fail(e)
        return hash_embed(text, self.s.embed_dim)


# -- heuristics (offline mode) ------------------------------------------
def heuristic_diagnosis(ctx: dict[str, Any]) -> Diagnosis:
    flags, sql = ctx.get("flags", []), ctx["sql"].upper()
    causes = [f["detail"] for f in flags]
    if re.search(r"\b(YEAR|MONTH|DAY|DATE|UPPER|LOWER|SUBSTR)\s*\(", sql):
        causes.append("a function is applied to a filtered column, so no index range can be used (non-sargable)")
    if re.search(r"\bNOT\s+IN\s*\(\s*SELECT", sql):
        causes.append("NOT IN (subquery) must handle NULLs, which blocks an efficient anti-join")
    scans = [f for f in flags if f["kind"] == "TABLE_SCAN"]
    sev = "high" if scans else ("medium" if causes else "low")
    head = scans[0]["detail"].capitalize() if scans else (causes[0].capitalize() if causes else "No obvious problem")
    m = ctx.get("metrics", {})
    plain = (f"Each run reads about {m.get('read_per_returned', 0):,.0f} rows for every row it returns. "
             if m else "") + ("The plan scans whole tables instead of seeking with an index."
                              if scans else "The plan looks reasonable for this data volume.")
    return Diagnosis(headline=head, plain_english=plain, root_causes=causes or ["no issue detected"], severity=sev)


_YM = re.compile(r"YEAR\s*\(\s*([\w\.]+)\s*\)\s*=\s*(\d{4})\s+AND\s+MONTH\s*\(\s*\1\s*\)\s*=\s*(\d{1,2})", re.I)
_Y = re.compile(r"YEAR\s*\(\s*([\w\.]+)\s*\)\s*=\s*(\d{4})", re.I)
_NOTIN = re.compile(r"([\w\.]+)\s+NOT\s+IN\s*\(\s*SELECT\s+([\w\.]+)\s+FROM\s+([\w\.]+)\s+(\w+)\s+WHERE\s+(.+?)\)\s*$",
                    re.I | re.S)


def heuristic_rewrite(sql: str, not_null_cols: set[str] | None = None) -> Rewrite:
    def ym(m: re.Match) -> str:
        col, y, mo = m.group(1), int(m.group(2)), int(m.group(3))
        ny, nm = (y + 1, 1) if mo == 12 else (y, mo + 1)
        return f"{col} >= '{y:04d}-{mo:02d}-01' AND {col} < '{ny:04d}-{nm:02d}-01'"

    new = _YM.sub(ym, sql)
    if new == sql:
        new = _Y.sub(lambda m: f"{m.group(1)} >= '{m.group(2)}-01-01' AND {m.group(1)} < '{int(m.group(2)) + 1}-01-01'", sql)
    if new != sql:
        return Rewrite(should_rewrite=True, sql=new,
                       rationale="Replaced YEAR()/MONTH() on the column with an equivalent half-open date range, "
                                 "which is sargable and lets Db2 use an index range scan.")
    m = _NOTIN.search(sql)
    if m:
        outer, inner, tbl, alias, where = m.groups()
        col = inner.split(".")[-1].upper()
        nn = {c.upper() for c in (not_null_cols or set())}
        if col in nn and outer.split(".")[-1].upper() in nn:  # NOT IN == NOT EXISTS only without NULLs
            new = (sql[:m.start()] + f"NOT EXISTS (SELECT 1 FROM {tbl} {alias} WHERE {inner} = {outer} AND {where.strip()})")
            return Rewrite(should_rewrite=True, sql=new,
                           rationale=f"{col} is NOT NULL on both sides, so NOT IN is equivalent to NOT EXISTS, which Db2 runs "
                                     "as an anti-join.")
    m = _UNION.match(" ".join(sql.split()))
    if m and m.group(6) != m.group(8):
        cols, tbl, pre, col, a, post, b = m.group(2, 3, 4, 5, 6, 7, 8)
        return Rewrite(should_rewrite=True, sql=f"SELECT DISTINCT {cols} FROM {tbl} WHERE {pre}{col} IN ({a}, {b}){post}",
                       rationale="Both UNION branches scan the same table and differ in one literal; a single "
                                 "DISTINCT scan with an IN list returns the same set with one pass instead of two.")
    return Rewrite(should_rewrite=False, sql="", rationale="no safe rewrite pattern matched")


_LIT = r"('(?:[^']|'')*'|\d+)"
# SELECT cols FROM t WHERE pre col = lit post UNION SELECT <same, other literal>
_UNION = re.compile(r"^(SELECT (.+?) FROM (.+?) WHERE (.*?))([\w.]+) = " + _LIT + r"(.*?) UNION SELECT \2 FROM \3 "
                    r"WHERE \4\5 = " + _LIT + r"\7$", re.I)


def heuristic_narrative(report: dict[str, Any]) -> str:
    applied = report.get("applied", [])
    if not applied:
        return (f"reDB analysed {report.get('statements', 0)} statements and prepared "
                f"{report.get('proposals', 0)} proven proposals; none were applied yet.")
    b, a = report.get("ms_before", 0), report.get("ms_after", 0)
    pct = 100 * (b - a) / b if b else 0
    return (f"reDB analysed {report.get('statements', 0)} expensive statements and applied {len(applied)} approved "
            f"changes. Measured time for the tuned statements fell from {b:,.1f} ms to {a:,.1f} ms "
            f"({pct:.0f}% faster). Every change is in the temporal ledger with one-click rollback.")
