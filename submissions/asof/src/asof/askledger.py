"""Ask the ledger: plain-English questions over the audit trail, for auditors and compliance.

    question -> SQL (LLM) -> SQLGlot gate -> Db2, as the read-only analyst -> short answer (LLM)

A LangChain chain. LangChain's SQLDatabase, reflected through SQLAlchemy and ibm_db_sa as the
analyst, describes the allowed views to the model, and the steps are LCEL runnables. Every
layer assumes the one before it failed:

1. The model sees only the allowed views.
2. Its SQL must pass `validate`. SQLGlot's Db2 dialect parses it, and it must be exactly one
   SELECT that reads only allowed views, calls only allowed functions, and uses the masked
   text columns only as plain output columns. What runs is SQLGlot's regeneration of the
   checked tree, never the model's text, so the checker and Db2 cannot read it differently.
3. It runs as the analyst user (asofread, role ASOF_ANALYST), whose only privileges are
   CONNECT and SELECT on those views. No tables, no procedures, no writes.
4. Db2's column masks return '[masked]' for the customer's question and the released answer
   to that user, whatever the SQL says (05_masks.sql). Db2 does not mask predicates, which is
   why rule 2 keeps those columns out of WHERE, ORDER BY, GROUP BY, joins and functions.
5. Db2 cancels the statement after QUERY_TIMEOUT_S, and at most ROW_CAP rows come back.

If the SQL is refused, or Db2 rejects it, the model gets one more try with the reason. The
written answer comes only from the returned rows, and the UI shows the rows and the SQL with it.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import ibm_db
import sqlglot
from langchain_core.runnables import RunnableLambda
from sqlglot import exp
from sqlglot.errors import SqlglotError

from . import db
from .config import Settings
from .llm import LLMError
from .prompts import ASK_PROMPT_VERSION, ask_answer_messages, ask_sql_messages
from .schemas import LedgerAnswer, LedgerSql

log = logging.getLogger(__name__)

ALLOWED_VIEWS = ("V_AUDIT_DECISIONS", "V_AUDIT_CLAIMS", "V_POLICY_TIMELINE", "V_DECISION_STATS",
                 "V_CLAIM_OUTCOMES_BY_AREA", "V_RULE_OVERRIDES")
# Columns with a Db2 column mask (05_masks.sql). Masks hide the value, not predicates on it.
MASKED_COLUMNS = frozenset({"QUESTION_REDACTED", "DRAFT_REDACTED", "FINAL_ANSWER", "VERDICTS_JSON"})
# Names as SQLGlot's Db2 dialect reports them (a known function's sql_name, else the name used).
ALLOWED_FUNCTIONS = frozenset({
    "COUNT", "SUM", "AVG", "MIN", "MAX", "STDDEV", "VARIANCE", "MEDIAN", "PERCENTILE_CONT",
    "ROUND", "ABS", "FLOOR", "CEIL", "GREATEST", "LEAST", "COALESCE", "NULLIF", "CASE", "IF", "CAST",
    "INTEGER", "DECIMAL", "DOUBLE", "VARCHAR",
    "YEAR", "MONTH", "DAY", "WEEK", "QUARTER", "HOUR", "EXTRACT", "DATE", "DAYS", "DAYS_BETWEEN",
    "ADD_DAYS", "ADD_MONTHS", "DAYNAME", "MONTHNAME", "TIME_TO_STR", "DATE_TRUNC", "TRUNC",
    "CURRENT_DATE", "CURRENT_TIMESTAMP",
    "UPPER", "LOWER", "SUBSTRING", "LENGTH", "TRIM", "LEFT", "RIGHT", "CONCAT", "REPLACE", "STR_POSITION",
    "EXISTS", "LISTAGG", "ROW_NUMBER", "RANK", "DENSE_RANK", "PERCENT_RANK", "NTILE", "LAG", "LEAD",
})
# Labeled durations ("D - 7 DAYS") come out of this dialect as an alias ("D - 7 AS DAYS"), which
# would silently change the query. Aliases with these names are refused.
DURATION_WORDS = frozenset({"DAY", "DAYS", "MONTH", "MONTHS", "YEAR", "YEARS", "HOUR", "HOURS", "MINUTE",
                            "MINUTES", "SECOND", "SECONDS", "MICROSECOND", "MICROSECONDS"})
_FORBIDDEN = {
    "Insert": "INSERT", "Update": "UPDATE", "Delete": "DELETE", "Merge": "MERGE", "Create": "CREATE",
    "Drop": "DROP", "Alter": "ALTER", "TruncateTable": "TRUNCATE", "Command": "a command", "Into": "SELECT INTO",
    "Placeholder": "parameter markers", "Parameter": "parameters", "SetOperation": "UNION, INTERSECT and EXCEPT",
    "Dot": "schema-qualified functions", "Transaction": "transactions", "Commit": "COMMIT", "Rollback": "ROLLBACK",
    "Use": "USE", "Set": "SET", "Grant": "GRANT", "Lateral": "LATERAL", "Unnest": "UNNEST", "Values": "VALUES",
    "Mod": "MOD and % (not supported here)",
    "Chr": "CHAR() (this checker reads it as CHR; use VARCHAR)",
}
FORBIDDEN_NODES = tuple((getattr(exp, k), v) for k, v in _FORBIDDEN.items() if hasattr(exp, k))
PLAIN_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")

MAX_SQL_CHARS = 4000
MAX_TABLE_REFS = 6
ROW_CAP = 200
ANSWER_ROWS = 50  # rows the model sees when it writes the answer
QUERY_TIMEOUT_S = 10
MAX_ATTEMPTS = 2  # the first try plus one repair


class Refused(ValueError):
    """The SQL did not pass the gate. The message says why, for the model and for the UI."""


def validate(sql: str, row_cap: int = ROW_CAP) -> str:
    """Return the only SQL that may run for `sql`, or raise Refused. Pure: no database, no model."""
    text = (sql or "").strip()
    while text.endswith(";"):
        text = text[:-1].rstrip()
    if not text:
        raise Refused("the query is empty")
    if len(text) > MAX_SQL_CHARS:
        raise Refused(f"the query is longer than {MAX_SQL_CHARS} characters")
    if ";" in text:
        raise Refused("only one statement is allowed")
    if "--" in text or "/*" in text:
        raise Refused("comments are not allowed")
    try:
        trees = [t for t in sqlglot.parse(text, dialect="db2") if t is not None]
    except SqlglotError as exc:
        raise Refused(f"not Db2 SQL this checker can read: {str(exc).splitlines()[0][:160]}") from None
    if len(trees) != 1:
        raise Refused("exactly one statement is allowed")
    tree = trees[0]
    if not isinstance(tree, exp.Select):
        raise Refused(f"only a SELECT is allowed, not {tree.key.upper()}")
    if tree.args.get("locks"):
        raise Refused("locking clauses such as FOR UPDATE are not allowed")
    for node in tree.walk():
        for cls, what in FORBIDDEN_NODES:
            if isinstance(node, cls):
                raise Refused(f"{what} not allowed")
    for ident in tree.find_all(exp.Identifier):  # Db2 folds unquoted names to upper case
        if ident.args.get("quoted"):
            if not PLAIN_NAME.match(ident.name):
                raise Refused(f"identifier {ident.name!r} is not a plain name")
            ident.set("quoted", False)

    ctes = {cte.alias_or_name.upper() for cte in tree.find_all(exp.CTE)}
    tables = list(tree.find_all(exp.Table))
    if len(tables) > MAX_TABLE_REFS:
        raise Refused(f"at most {MAX_TABLE_REFS} view references are allowed")
    for t in tables:
        name = t.name.upper() if isinstance(t.this, exp.Identifier) else ""
        if not name:
            raise Refused("only view names may follow FROM or JOIN (no table functions or expressions)")
        if t.args.get("db") or t.args.get("catalog"):
            raise Refused(f"write view names unqualified: {t.sql(dialect='db2')}")
        if name not in ALLOWED_VIEWS and name not in ctes:
            raise Refused(f"{name} is not one of the views you may query ({', '.join(ALLOWED_VIEWS)})")

    for f in tree.find_all(exp.Func):
        if isinstance(f, (exp.Connector, exp.Binary)):  # AND, OR and operators are Func nodes in SQLGlot
            continue
        fname = f.name.upper() if isinstance(f, exp.Anonymous) else f.sql_name().upper()
        if fname not in ALLOWED_FUNCTIONS:
            raise Refused(f"function {fname} is not allowed")
    for a in tree.find_all(exp.Alias):
        if a.alias.upper() in DURATION_WORDS:
            raise Refused("labeled durations such as '- 7 DAYS' (or aliases named like them) are not supported: "
                          "use ADD_DAYS(date, n), ADD_MONTHS(date, n) or DAYS(a) - DAYS(b)")
    _check_masked(tree)
    _check_stars(tree)
    order = tree.args.get("order")
    if order and any(isinstance(o.this, exp.Literal) for o in order.expressions):
        raise Refused("ORDER BY must name columns, not positions")
    if not tree.args.get("limit"):
        tree = tree.limit(row_cap + 1)  # the database stops early; one extra row tells us there were more
    return tree.sql(dialect="db2")


def _check_masked(tree: exp.Select) -> None:
    """Masked columns (and aliases of them) only as plain output columns of the outermost SELECT."""
    outputs = {id(e) for e in tree.expressions}
    masked = set(MASKED_COLUMNS)
    for e in tree.expressions:
        if isinstance(e, exp.Alias) and isinstance(e.this, exp.Column) and e.this.name.upper() in MASKED_COLUMNS:
            masked.add(e.alias.upper())
    for col in tree.find_all(exp.Column):
        if isinstance(col.this, exp.Star) or col.name.upper() not in masked:
            continue
        node = col.parent if isinstance(col.parent, exp.Alias) else col
        if id(node) in outputs and node.parent is tree and not tree.args.get("distinct"):
            continue
        raise Refused(f"{col.name.upper()} is masked: list it only as an output column of the outermost SELECT "
                      "(never in WHERE, ORDER BY, GROUP BY, a join, DISTINCT, a subquery or a function)")


def _check_stars(tree: exp.Select) -> None:
    """SELECT * only at the top: an inner * could carry a masked column out under another name."""
    for sel in tree.find_all(exp.Select):
        if sel is tree:
            continue
        for e in sel.expressions:
            if isinstance(e, exp.Star) or (isinstance(e, exp.Column) and isinstance(e.this, exp.Star)):
                raise Refused("SELECT * is allowed only in the outermost SELECT: name the columns in subqueries "
                              "and WITH blocks")


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value) if value != value.to_integral_value() else int(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, str):
        return value.rstrip()  # CHAR columns come back blank-padded
    return value


def _no_materialized_views(*_args, **_kwargs) -> list[str]:
    return []


@dataclass
class AskResult:
    question: str
    status: str  # ANSWERED, REFUSED (no SQL passed the gate) or FAILED (Db2 rejected the checked SQL)
    answer: str | None = None
    sql: str | None = None  # the checked SQL that ran
    explanation: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    truncated: bool = False
    reason: str | None = None
    attempts: list[dict[str, Any]] = field(default_factory=list)
    model: str = ""
    prompt_version: str = ASK_PROMPT_VERSION
    latency_ms: int = 0
    runs_as: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class LedgerAsker:
    """The chain, plus the analyst's connection. One instance per app; thread-safe."""

    def __init__(self, llm, settings: Settings, schema: str = db.SCHEMA, *, row_cap: int = ROW_CAP,
                 timeout_s: int = QUERY_TIMEOUT_S):
        self.llm = llm
        self.settings = settings
        self.schema = db.validate_schema(schema)
        self.row_cap = row_cap
        self.timeout_s = timeout_s
        self._lock = threading.Lock()
        self._engine = None
        self._database = None

    # --- Db2, as the analyst -------------------------------------------------------------

    def engine(self):
        """SQLAlchemy engine (ibm_db_sa) whose every connection is the analyst, pointed at the schema."""
        with self._lock:
            if self._engine is None:
                from sqlalchemy import create_engine
                from sqlalchemy.pool import NullPool

                def creator():
                    conn = db.connect(self.settings, "analyst")
                    db.use_schema(conn, self.schema)
                    return conn

                eng = create_engine("ibm_db_sa://", creator=creator, poolclass=NullPool)
                # ibm_db_sa 0.4.4 does not implement this, and LangChain's SQLDatabase calls it for
                # view support. None of the allowed views is a materialized query table.
                eng.dialect.get_materialized_view_names = _no_materialized_views
                self._engine = eng
            return self._engine

    def database(self):
        """LangChain's SQLDatabase over the allowed views only, reflected as the analyst."""
        engine = self.engine()
        with self._lock:
            if self._database is None:
                from langchain_community.utilities import SQLDatabase

                self._database = SQLDatabase(engine, schema=self.schema, view_support=True,
                                             include_tables=[v.lower() for v in ALLOWED_VIEWS],
                                             sample_rows_in_table_info=2)
            return self._database

    def views(self) -> str:
        """The views as the model sees them: columns plus two sample rows each, read as the analyst."""
        info = self.database().get_table_info()
        return info.replace(f'"{self.schema}".', "")  # the queries use unqualified names

    def run_sql(self, sql: str) -> tuple[list[str], list[list[Any]], bool]:
        """Run checked SQL as the analyst, with Db2's statement timeout and the row cap."""
        with self.engine().connect() as c:
            handle = c.connection.dbapi_connection.conn_handler
            stmt = None
            try:
                stmt = ibm_db.prepare(handle, sql)
                ibm_db.set_option(stmt, {ibm_db.SQL_ATTR_QUERY_TIMEOUT: self.timeout_s}, 0)
                ibm_db.execute(stmt)
                columns = [ibm_db.field_name(stmt, i) for i in range(ibm_db.num_fields(stmt))]
                rows: list[list[Any]] = []
                while len(rows) <= self.row_cap:
                    row = ibm_db.fetch_tuple(stmt)
                    if not row:
                        break
                    rows.append([_jsonable(v) for v in row])
            except Exception as exc:  # noqa: BLE001 - ibm_db raises plain Exception subclasses
                raise db.wrap_error(exc, "Query failed") from None
            finally:
                if stmt is not None:
                    ibm_db.free_stmt(stmt)
                c.rollback()
        truncated = len(rows) > self.row_cap
        return [str(col).upper() for col in columns], rows[: self.row_cap], truncated

    # --- the chain -----------------------------------------------------------------------

    def chain(self):
        return (RunnableLambda(self._with_views)
                | RunnableLambda(self._query)
                | RunnableLambda(self._answer))

    def ask(self, question: str) -> AskResult:
        started = time.monotonic()
        result: AskResult = self.chain().invoke(question)
        result.latency_ms = int((time.monotonic() - started) * 1000)
        log.info("ask-the-ledger %s in %d ms, %d attempt(s), %d row(s)", result.status, result.latency_ms,
                 len(result.attempts), len(result.rows))
        return result

    def _with_views(self, question: str) -> dict[str, Any]:
        return {"question": question, "views": self.views()}

    def _query(self, state: dict[str, Any]) -> AskResult:
        question = state["question"]
        out = AskResult(question=question, status="REFUSED", model=self.llm.info,
                        runs_as=f"{self.settings.asof_analyst_user} (role ASOF_ANALYST: SELECT on the audit views only)")
        previous: tuple[str, str] | None = None
        for _ in range(MAX_ATTEMPTS):
            draft = self.llm.structured(LedgerSql, ask_sql_messages(question, state["views"], previous)).value
            attempt: dict[str, Any] = {"proposed_sql": draft.sql[:MAX_SQL_CHARS]}
            out.attempts.append(attempt)
            try:
                checked = validate(draft.sql, self.row_cap)
            except Refused as why:
                attempt["refused"] = str(why)
                out.status, out.reason = "REFUSED", f"the SQL did not pass the check: {why}"
                previous = (draft.sql[:MAX_SQL_CHARS], f"refused: {why}")
                continue
            attempt["checked_sql"] = checked
            try:
                out.columns, out.rows, out.truncated = self.run_sql(checked)
            except db.DatabaseError as err:
                attempt["db2_error"] = str(err)[:300]
                out.status, out.reason = "FAILED", f"Db2 rejected the checked SQL: {str(err)[:300]}"
                previous = (checked, f"Db2 error: {str(err)[:300]}")
                continue
            out.status, out.reason, out.sql, out.explanation = "ANSWERED", None, checked, draft.explanation[:300]
            return out
        return out

    def _answer(self, out: AskResult) -> AskResult:
        if out.status != "ANSWERED":
            return out
        if not out.rows:
            out.answer = "The query returned no rows."
            return out
        try:
            reply = self.llm.structured(LedgerAnswer, ask_answer_messages(
                out.question, out.sql or "", out.columns, out.rows[:ANSWER_ROWS], out.truncated or len(out.rows) >
                ANSWER_ROWS)).value
            out.answer = reply.answer.strip()[:1200]
        except LLMError as exc:  # the rows stand on their own; the summary is a convenience
            log.warning("ask-the-ledger summary failed: %s", exc)
            out.answer = None
            out.reason = "the rows are below; the written summary could not be produced"
        return out
