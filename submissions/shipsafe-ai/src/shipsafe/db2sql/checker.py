"""Check SQL against the real IBM Db2 database before it ships.

Two layers:

1. **Live validation** — the statement is PREPAREd on the Db2 server with
   deferred prepare turned off. Db2 itself reports syntax errors, unknown
   tables and unknown columns, and describes the result columns. Nothing is
   ever executed.
2. **Rules** — patterns that are valid SQL but risky in application code
   (UPDATE/DELETE without WHERE, string templating instead of `?` markers,
   unbounded SELECT *).

When Db2 rejects a name, the live catalog (read through SQLAlchemy's
inspector on `ibm_db_sa`) supplies "did you mean" suggestions.
"""

import difflib
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


_SQLCODE = re.compile(r"SQLCODE=(-?\d+)")
_SQLSTATE = re.compile(r"SQLSTATE=(\w+)")
_QUOTED = re.compile(r'"([^"]+)"')
_STRIP_LITERALS = re.compile(r"'(?:[^']|'')*'")
_STRIP_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)

SQLCODE_HELP = {
    -104: "Syntax error: Db2 did not expect this token.",
    -204: "The table, view or other object does not exist.",
    -206: "A column name is not valid in this context.",
    -551: "The user is not authorised for this operation on the object.",
    -408: "A value is not compatible with the column's data type.",
    -418: "A parameter marker is used where Db2 cannot infer its type; add a CAST(? AS type).",
    -420: "A character value could not be converted to a number.",
    -117: "The number of values does not match the number of columns.",
}
READ_ONLY = ("SELECT", "WITH", "VALUES")


def _vector_type():
    from sqlalchemy.types import UserDefinedType

    class _Db2Vector(UserDefinedType):
        """Db2 12.1 native VECTOR column (reflection only)."""
        cache_ok = True

        def get_col_spec(self, **_kw) -> str:
            return "VECTOR"

    return _Db2Vector


@dataclass
class SqlIssue:
    code: str
    severity: str
    message: str
    suggestion: str = ""


@dataclass
class SqlCheckResult:
    sql: str
    statement_type: str
    valid: bool
    issues: List[SqlIssue] = field(default_factory=list)
    result_columns: List[Dict[str, str]] = field(default_factory=list)
    parameter_markers: int = 0
    db2: Dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0

    @property
    def verdict(self) -> str:
        if not self.valid or any(i.severity in ("critical", "high") for i in self.issues):
            return "block"
        return "warn" if self.issues else "clean"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["verdict"] = self.verdict
        return d


def _normalise(sql: str) -> str:
    return _STRIP_COMMENTS.sub(" ", sql).strip().rstrip(";").strip()


def statement_type(sql: str) -> str:
    m = re.match(r"\s*\(?\s*(\w+)", _normalise(sql))
    return m.group(1).upper() if m else "UNKNOWN"


def static_rules(sql: str) -> List[SqlIssue]:
    """Risky-but-valid patterns, evaluated on the text with literals and comments removed."""
    body = _normalise(sql)
    bare = _STRIP_LITERALS.sub("''", body)
    upper = bare.upper()
    kind = statement_type(sql)
    issues: List[SqlIssue] = []
    if ";" in bare:
        issues.append(SqlIssue("MULTI-STATEMENT", "medium", "More than one statement in a single string.",
                               "Send one statement per call so errors and parameters stay unambiguous."))
    if re.search(r"%s|%d|%\(\w+\)s", body) or re.search(r"\{[^}]*\}", bare):
        issues.append(SqlIssue("TEMPLATE-PLACEHOLDER", "high",
                               "The SQL contains Python-style placeholders (%s, {name}). These are filled by string "
                               "formatting, which is SQL injection, and Db2 does not understand them.",
                               "Use `?` parameter markers and pass the values as a tuple."))
    if kind in ("UPDATE", "DELETE") and not re.search(r"\bWHERE\b", upper):
        issues.append(SqlIssue("NO-WHERE", "high", f"{kind} without a WHERE clause changes every row in the table.",
                               "Add a WHERE clause, or use TRUNCATE deliberately if that is the intent."))
    if kind in ("DROP", "TRUNCATE", "ALTER"):
        issues.append(SqlIssue("DESTRUCTIVE-DDL", "medium", f"{kind} changes or removes database objects.",
                               "Run schema changes through a reviewed migration, not application code."))
    if kind in READ_ONLY and re.search(r"SELECT\s+\*", upper):
        issues.append(SqlIssue("SELECT-STAR", "low", "SELECT * couples the code to the table's column order.",
                               "List the columns you need."))
    if kind in READ_ONLY and not re.search(r"\bWHERE\b|\bFETCH\s+FIRST\b|\bLIMIT\b|\bGROUP\s+BY\b", upper) \
            and "SYSDUMMY1" not in upper:
        issues.append(SqlIssue("UNBOUNDED-READ", "low", "The query has no WHERE or FETCH FIRST and may return the whole table.",
                               "Add a filter or `FETCH FIRST n ROWS ONLY`."))
    if re.search(r"(?:=|<>|<|>|\bLIKE)\s*'[^']+'", body) and kind in READ_ONLY + ("UPDATE", "DELETE"):
        issues.append(SqlIssue("INLINE-LITERAL", "low", "Values are written inline in the SQL text.",
                               "If these values come from users, bind them with `?` markers instead."))
    return issues


class Db2SqlChecker:
    """Validates SQL on a live Db2 connection and inspects the catalog with SQLAlchemy."""

    def __init__(self, repository: Any, engine: Any = None):
        self.repository = repository
        self.schema = repository.schema
        self._engine = engine

    # -------------------------------------------------------------- catalog
    @property
    def engine(self):
        if self._engine is None:
            from sqlalchemy import create_engine
            from sqlalchemy.engine import URL

            cfg = self.repository.config
            query = {"Security": "SSL"} if cfg.security == "SSL" else {}
            url = URL.create("ibm_db_sa", username=cfg.username, password=cfg.password, host=cfg.host,
                             port=cfg.port, database=cfg.database, query=query)
            self._engine = create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=0)
            from sqlalchemy import event

            from ..db2.repository import set_lock_timeout

            event.listen(self._engine, "connect", lambda dbapi_conn, _rec: set_lock_timeout(dbapi_conn, cfg.lock_timeout))
            # ibm_db_sa does not know Db2's native VECTOR type yet: register it so reflection reports it.
            self._engine.dialect.ischema_names = {**self._engine.dialect.ischema_names, "VECTOR": _vector_type()}
        return self._engine

    def schema_overview(self, schema: Optional[str] = None, tables: Optional[List[str]] = None) -> Dict[str, Any]:
        """Tables, columns, keys and indexes of a schema, read through SQLAlchemy's inspector."""
        from sqlalchemy import inspect

        target = (schema or self.schema).lower()
        insp = inspect(self.engine)
        names = sorted(insp.get_table_names(schema=target))
        if tables:
            wanted = {t.lower() for t in tables}
            names = [n for n in names if n.lower() in wanted]
        out = []
        for name in names:
            cols = [{"name": c["name"].upper(), "type": str(c["type"]), "nullable": bool(c.get("nullable", True))}
                    for c in insp.get_columns(name, schema=target)]
            pk = insp.get_pk_constraint(name, schema=target) or {}
            fks = [{"columns": [c.upper() for c in fk["constrained_columns"]],
                    "references": f"{fk['referred_table'].upper()}({', '.join(c.upper() for c in fk['referred_columns'])})"}
                   for fk in insp.get_foreign_keys(name, schema=target)]
            idx = [{"name": i["name"].upper(), "columns": [str(c).upper() for c in i["column_names"] if c],
                    "unique": bool(i.get("unique"))} for i in insp.get_indexes(name, schema=target)]
            out.append({"table": name.upper(), "columns": cols,
                        "primary_key": [c.upper() for c in pk.get("constrained_columns", [])],
                        "foreign_keys": fks, "indexes": idx})
        views = sorted(v.upper() for v in insp.get_view_names(schema=target))
        return {"schema": target.upper(), "tables": out, "views": views}

    def _suggest(self, sqlcode: int, message: str) -> str:
        m = _QUOTED.search(message)
        if not m:
            return ""
        bad = m.group(1).split(".")[-1].upper()
        try:
            overview = self.schema_overview()
        except Exception:  # catalog lookup is best-effort help, never a reason to fail the check
            return ""
        if sqlcode == -204:
            pool = [t["table"] for t in overview["tables"]] + overview["views"]
        elif sqlcode == -206:
            pool = sorted({c["name"] for t in overview["tables"] for c in t["columns"]})
        else:
            return ""
        close = difflib.get_close_matches(bad, pool, n=3, cutoff=0.6)
        return f"Did you mean {', '.join(close)}?" if close else ""

    # ----------------------------------------------------------- validation
    def check(self, sql: str) -> SqlCheckResult:
        import ibm_db

        started = time.perf_counter()
        body = _normalise(sql)
        result = SqlCheckResult(sql=body, statement_type=statement_type(sql), valid=True, issues=static_rules(sql))
        if not body:
            result.valid = False
            result.issues.append(SqlIssue("EMPTY", "high", "No SQL statement was given."))
            return result
        if any(i.code in ("TEMPLATE-PLACEHOLDER", "MULTI-STATEMENT") for i in result.issues):
            result.db2 = {"prepared": False, "reason": "not sent to Db2 until the placeholders / statements are fixed"}
            result.duration_ms = int((time.perf_counter() - started) * 1000)
            return result

        handle = self.repository.conn.conn_handler
        try:
            stmt = ibm_db.prepare(handle, body, {ibm_db.SQL_ATTR_DEFERRED_PREPARE: 0})
            n = ibm_db.num_fields(stmt) or 0
            result.result_columns = [{"name": ibm_db.field_name(stmt, i), "type": ibm_db.field_type(stmt, i)}
                                     for i in range(n)]
            result.parameter_markers = _STRIP_LITERALS.sub("''", body).count("?")
            ibm_db.free_stmt(stmt)
            result.db2 = {"prepared": True, "schema": self.schema}
        except Exception as exc:
            message = ibm_db.stmt_errormsg() or str(exc)
            code_m, state_m = _SQLCODE.search(message), _SQLSTATE.search(message)
            sqlcode = int(code_m.group(1)) if code_m else 0
            result.valid = False
            result.db2 = {"prepared": False, "sqlcode": sqlcode, "sqlstate": state_m.group(1) if state_m else None,
                          "message": message.split("]")[-1].strip()[:400]}
            result.issues.insert(0, SqlIssue(f"SQL{abs(sqlcode):04d}N" if sqlcode else "DB2-ERROR", "high",
                                             SQLCODE_HELP.get(sqlcode, "Db2 rejected the statement.") + " "
                                             + result.db2["message"], self._suggest(sqlcode, message)))
        finally:
            self.repository.rollback()
        result.duration_ms = int((time.perf_counter() - started) * 1000)
        return result
