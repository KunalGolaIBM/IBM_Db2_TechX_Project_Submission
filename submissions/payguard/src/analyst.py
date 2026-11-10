"""Fraud-analyst console: plain-English questions -> guarded, read-only Db2 SQL."""
from __future__ import annotations

import re

import llm

QUICK_QUESTIONS: dict[str, str] = {
    "Which scam categories are blocked most?": """
        SELECT TOP_CATEGORY, COUNT(*) AS BLOCKED, SUM(AMOUNT) AS AMOUNT_PROTECTED
        FROM PG_SCREENINGS WHERE VERDICT = 'BLOCK' AND TOP_CATEGORY IS NOT NULL
        GROUP BY TOP_CATEGORY ORDER BY BLOCKED DESC""",
    "Most reported scammer contacts": """
        SELECT ENTITY_TYPE, ENTITY_VALUE, STATUS, REPORT_COUNT, REPORTED_LOSS
        FROM PG_V_ENTITY_RISK WHERE STATUS <> 'TRUSTED'
        ORDER BY REPORT_COUNT DESC, REPORTED_LOSS DESC""",
    "Verdicts per day (last 14 days)": """
        SELECT SCREEN_DAY, VERDICT, SCREENINGS, TOTAL_AMOUNT FROM PG_V_DAILY_VERDICTS
        WHERE SCREEN_DAY > CURRENT DATE - 14 DAYS ORDER BY SCREEN_DAY DESC, VERDICT""",
    "Average risk score by payment method": """
        SELECT PAYMENT_METHOD, COUNT(*) AS SCREENINGS, DECIMAL(AVG(RISK_SCORE * 1.0), 5, 1) AS AVG_RISK
        FROM PG_SCREENINGS GROUP BY PAYMENT_METHOD ORDER BY AVG_RISK DESC""",
    "Biggest reported losses": """
        SELECT R.CATEGORY, R.AMOUNT, R.CURRENCY, E.ENTITY_VALUE, R.CREATED_AT
        FROM PG_REPORTS R JOIN PG_ENTITIES E ON E.ID = R.ENTITY_ID
        ORDER BY R.AMOUNT DESC""",
}

FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|GRANT|REVOKE|CALL|TRUNCATE|EXECUTE|EXEC|IMPORT|LOAD|"
    r"EXPORT|SET|DECLARE|LOCK|RENAME|COMMENT|REFRESH|REORG|RUNSTATS|ADMIN_CMD|PREPARE)\b", re.I)
TABLE_REF = re.compile(r"\b(?:FROM|JOIN)\s+([A-Z0-9_.\"]+)", re.I)
ALLOWED_TABLES = {"PG_SCAM_PATTERNS", "PG_ENTITIES", "PG_REPORTS", "PG_SCREENINGS",
                  "PG_V_ENTITY_RISK", "PG_V_DAILY_VERDICTS", "SYSIBM.SYSDUMMY1"}


class UnsafeSQL(ValueError):
    pass


def guard_sql(sql: str, max_rows: int = 100) -> str:
    """Allow a single read-only SELECT over PayGuard tables; enforce a row limit."""
    s = re.sub(r"--[^\n]*", " ", sql)
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S).strip().rstrip(";").strip()
    if ";" in s:
        raise UnsafeSQL("Only one statement is allowed.")
    if not re.match(r"^(SELECT|WITH)\b", s, re.I):
        raise UnsafeSQL("Only SELECT queries are allowed.")
    if FORBIDDEN.search(s):
        raise UnsafeSQL("Query contains a forbidden keyword.")
    if re.search(r"\bEMBEDDING\b", s, re.I):
        raise UnsafeSQL("Embedding columns cannot be selected.")
    ctes = {m.upper() for m in re.findall(r"\b([A-Z_][A-Z0-9_]*)\s+AS\s*\(", s, re.I)}
    # EXTRACT(DAY FROM x), TRIM(BOTH ' ' FROM x), SUBSTRING(x FROM 1) are not table references
    table_scan = re.sub(r"\b(EXTRACT|TRIM|SUBSTRING)\s*\([^()]*\)", " ", s, flags=re.I)
    for t in TABLE_REF.findall(table_scan):
        name = t.strip('"').upper()
        if name.startswith("("):
            continue
        if name not in ALLOWED_TABLES and name not in ctes:
            raise UnsafeSQL(f"Table {name} is not allowed.")
    if not re.search(r"\bFETCH\s+FIRST\b", s, re.I):
        s += f" FETCH FIRST {int(max_rows)} ROWS ONLY"
    return s


class Analyst:
    def __init__(self, repo):
        self.repo = repo
        self._schema: str | None = None

    def schema(self) -> str:
        if self._schema is None:
            self._schema = self.repo.schema_description()
        return self._schema

    def run_quick(self, title: str) -> dict:
        if title not in QUICK_QUESTIONS:
            raise KeyError(title)
        sql = guard_sql(QUICK_QUESTIONS[title])
        return {"question": title, "sql": sql, "mode": "preset", **self.repo.run_readonly(sql)}

    def answer(self, question: str, summarize: bool = True) -> dict:
        if question in QUICK_QUESTIONS:
            return self.run_quick(question)
        prompt = (
            "Write ONE IBM Db2 SQL SELECT statement answering the question. Use only these tables/views:\n"
            f"{self.schema()}\n"
            "Notes: VERDICT is ALLOW|REVIEW|BLOCK. Entity STATUS is BLOCKED|SUSPECT|TRUSTED. Use Db2 syntax "
            "(FETCH FIRST n ROWS ONLY, CURRENT DATE - 7 DAYS, DATE(ts)). Never select EMBEDDING. "
            'Return JSON {"sql": "..."}.\n\nQuestion: ' + question
        )
        try:
            sql = llm.generate_json(prompt)["sql"]
        except llm.LLMUnavailable:
            return {"question": question, "mode": "unavailable", "columns": [], "rows": [],
                    "error": "Free-form questions need GEMINI_API_KEY. Use a quick question instead."}
        try:
            safe = guard_sql(sql)
            data = self.repo.run_readonly(safe)
        except UnsafeSQL as exc:
            return {"question": question, "sql": sql, "mode": "rejected", "columns": [], "rows": [], "error": str(exc)}
        except Exception as exc:
            return {"question": question, "sql": sql, "mode": "error", "columns": [], "rows": [],
                    "error": f"Db2 error: {str(exc)[:300]}"}
        out = {"question": question, "sql": safe, "mode": "gemini", **data}
        if summarize and data["rows"]:
            try:
                out["summary"] = llm.generate(
                    f"Question: {question}\nColumns: {data['columns']}\nRows (first 20): {data['rows'][:20]}\n"
                    "Answer the question in 1-2 sentences using only these results.")
            except Exception:
                pass
        return out
