"""Fraud-analyst console: plain-English questions -> guarded, read-only Db2 SQL."""
from __future__ import annotations

import re

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from adapters import gemini as llm
from domain.ports import LLM

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
    if "--" in sql or "/*" in sql or "*/" in sql:
        raise UnsafeSQL("SQL comments are not allowed.")
    s = sql.strip()
    if s.endswith(";"):
        s = s[:-1].strip()
    if ";" in s:
        raise UnsafeSQL("Only one statement is allowed.")
    if not re.match(r"^(SELECT|WITH)\b", s, re.I):
        raise UnsafeSQL("Only SELECT queries are allowed.")
    if FORBIDDEN.search(s):
        raise UnsafeSQL("Query contains a forbidden keyword.")
    if re.search(r"\bEMBEDDING\b", s, re.I):
        raise UnsafeSQL("Embedding columns cannot be selected.")
    try:
        # SQLGlot has no Db2 dialect. Normalize only Db2 datetime spellings for
        # validation; execute the original, guarded Db2 statement unchanged.
        validation = re.sub(r"\bCURRENT\s+(DATE|TIMESTAMP)\b", r"CURRENT_\1", s, flags=re.I)
        validation = re.sub(r"\b(\d+)\s+(DAYS?|HOURS?)\b", r"INTERVAL '\1' \2", validation, flags=re.I)
        parsed = sqlglot.parse(validation)
    except ParseError as exc:
        raise UnsafeSQL("Cannot validate SQL syntax.") from exc
    if len(parsed) != 1 or not isinstance(parsed[0], exp.Query):
        raise UnsafeSQL("Only one SELECT query is allowed.")
    tree = parsed[0]
    # CTE names are resolved per scope, so a same-named CTE cannot hide a system table.
    from sqlglot.optimizer.scope import traverse_scope

    tables = []
    for scope in traverse_scope(tree):
        for source in scope.sources.values():
            if not isinstance(source, exp.Table):
                continue
            name = ".".join(str(x).upper() for x in (source.catalog, source.db, source.name) if x)
            if name not in ALLOWED_TABLES:
                raise UnsafeSQL(f"Table {name} is not allowed.")
            tables.append(name)
    if any(t in {"PG_SCAM_PATTERNS", "PG_REPORTS"} for t in tables) and any(
            not isinstance(star.parent, exp.Count) for star in tree.find_all(exp.Star)):
        raise UnsafeSQL("Select explicit columns; wildcard could expose EMBEDDING.")
    if any(tree.find_all(exp.Into, exp.Lock, exp.Command)):
        raise UnsafeSQL("Query has a forbidden operation.")
    if any(fn.name.upper() not in {"DECIMAL"} for fn in tree.find_all(exp.Anonymous)) or any(tree.find_all(exp.Dot)):
        raise UnsafeSQL("User-defined functions are not allowed.")
    # Replace any client row limit; a subquery limit does not bound the outer query.
    s = re.sub(r"\s+FETCH\s+FIRST\s+\d+\s+ROWS?\s+ONLY\s*$", "", s, flags=re.I)
    if tree.args.get("limit") and not re.search(r"\bFETCH\s+FIRST\b", sql, re.I):
        raise UnsafeSQL("Use Db2 FETCH FIRST for row limits.")
    s += f" FETCH FIRST {max(1, min(100, int(max_rows)))} ROWS ONLY"
    return s


class Analyst:
    def __init__(self, repo, model: LLM = llm):
        self.repo, self.llm = repo, model
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
            sql = self.llm.generate_json(prompt)["sql"]
        except Exception:
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
                out["summary"] = self.llm.generate(
                    f"Question: {question}\nColumns: {data['columns']}\nRows (first 20): {data['rows'][:20]}\n"
                    "Answer the question in 1-2 sentences using only these results.")
            except Exception:
                pass
        return out
