"""Custodian gateway: the ONLY path from the agent to Db2.

Layers, in the order a statement meets them:
  1. classifier     sqlglot + IBM's Db2 dialect: exactly one SELECT/INSERT/UPDATE/DELETE on BANK tables
  2. blast-radius   exact COUNT(*) rewrite, run AS THE USER, + EXPLAIN cost; CUSTODIAN.POLICY decides
  3. approval       APPROVE decisions wait in CUSTODIAN.APPROVALS until an admin decides
  4. db2 engine     the statement runs on the user's OWN connection: GRANTs and RCAC
                    (row permissions + column masks) are enforced by Db2 itself
Every attempt, allowed or not, is written to CUSTODIAN.LEDGER.
"""
import logging
import threading

import db2_sqlglot  # noqa: F401  registers the 'db2' dialect
import sqlglot
from sqlglot import exp

from db import connect, query, scalar

ALLOWED_TABLES = {"CUSTOMERS", "ACCOUNTS", "TICKETS", "TICKET_EMBEDDINGS"}
WRITABLE_TABLES = {"CUSTOMERS", "ACCOUNTS", "TICKETS"}
TEMPORAL_PK = {"CUSTOMERS": "CUSTOMER_ID", "ACCOUNTS": "ACCOUNT_ID"}  # system-period temporal tables
KINDS = {exp.Select: "SELECT", exp.Union: "SELECT", exp.Update: "UPDATE", exp.Delete: "DELETE", exp.Insert: "INSERT"}
MAX_RESULT_ROWS = 50
logging.getLogger("sqlglot").setLevel(logging.ERROR)

# ponytail: one cached connection per user behind a global lock; a pool if many users share the gateway.
_lock = threading.RLock()
_conns: dict = {}


def conn_for(user: str):
    user = user.upper()
    if user not in _conns:
        _conns[user] = connect(user)
    return _conns[user]


class Blocked(Exception):
    def __init__(self, layer: str, reason: str):
        super().__init__(reason)
        self.layer, self.reason = layer, reason


# --------------------------------------------------------------------------- 1. classifier
def classify(sql: str):
    """Return (kind, table, ast) or raise Blocked('classifier', ...)."""
    try:
        stmts = [s for s in sqlglot.parse(sql, read="db2") if s is not None]
    except sqlglot.errors.SqlglotError as e:
        raise Blocked("classifier", f"could not parse SQL as Db2: {str(e).splitlines()[0][:150]}")
    if len(stmts) != 1:
        raise Blocked("classifier", f"exactly one statement allowed, got {len(stmts)}")
    ast = stmts[0]
    kind = KINDS.get(type(ast))
    if kind is None:
        word = str(ast.this).split()[0].upper() if isinstance(ast, exp.Command) else ast.key.upper()
        raise Blocked("classifier", f"{word} statements are never allowed for agents")
    ctes = {c.alias_or_name.upper() for c in ast.find_all(exp.CTE)}
    for t in ast.find_all(exp.Table):
        schema, name = t.db.upper(), t.name.upper()
        if name in ctes and not schema:
            continue
        if not name:
            raise Blocked("classifier", "table functions are not allowed")
        if schema not in ("", "BANK") or name not in ALLOWED_TABLES:
            raise Blocked("classifier", f"table {(schema + '.') if schema else ''}{name} is outside the agent's scope")
    for d in ast.find_all(exp.Dot):  # schema-qualified routine calls, e.g. SYSPROC.ADMIN_CMD(...)
        if isinstance(d.expression, exp.Func) or isinstance(d.this, exp.Func):
            raise Blocked("classifier", f"calling routine {d.sql('db2')[:60]} is not allowed")
    table = None
    if kind != "SELECT":
        target = ast.this if isinstance(ast.this, exp.Table) else ast.this.find(exp.Table)
        table = target.name.upper()
        if table not in WRITABLE_TABLES:
            raise Blocked("classifier", f"agents may not write to {table}")
    return kind, table, ast


# --------------------------------------------------------------------------- 2. blast radius
def count_sql(kind: str, ast) -> str | None:
    """Rewrite a DML statement into the SELECT COUNT(*) that measures exactly the rows it touches."""
    if kind in ("UPDATE", "DELETE"):
        q = exp.select("COUNT(*)").from_(ast.this.copy())
        where = ast.args.get("where")
        if where is not None:
            q = q.where(where.this.copy())
        return q.sql("db2")
    if kind == "INSERT":
        src = ast.expression
        if isinstance(src, exp.Values):
            return None  # counted directly
        return f"SELECT COUNT(*) FROM ({src.sql('db2')}) AS SRC"
    return None


def explain(sql: str):
    """EXPLAIN PLAN FOR <dml> (never executes it). Returns (total_cost, estimated_rows)."""
    g = conn_for("DB2INST1")
    query(g, "EXPLAIN PLAN FOR " + sql)
    _, rows = query(g, """
        SELECT S.TOTAL_COST,
               (SELECT MAX(ST.STREAM_COUNT) FROM DB2INST1.EXPLAIN_STREAM ST
                  JOIN DB2INST1.EXPLAIN_OPERATOR O ON O.EXPLAIN_TIME = ST.EXPLAIN_TIME AND O.OPERATOR_ID = ST.TARGET_ID
                 WHERE ST.EXPLAIN_TIME = S.EXPLAIN_TIME AND O.OPERATOR_TYPE IN ('DELETE', 'UPDATE', 'INSERT'))
          FROM DB2INST1.EXPLAIN_STATEMENT S
         WHERE S.EXPLAIN_LEVEL = 'P'
         ORDER BY S.EXPLAIN_TIME DESC FETCH FIRST 1 ROW ONLY""")
    return (float(rows[0][0]), float(rows[0][1]) if rows[0][1] is not None else None) if rows else (None, None)


def role_of(user: str) -> str | None:
    return scalar(conn_for("DB2INST1"),
                  "SELECT RTRIM(ROLENAME) FROM SYSCAT.ROLEAUTH WHERE GRANTEETYPE = 'U' AND GRANTEE = ?", [user.upper()])


def decide(role: str | None, table: str, kind: str, rows: int, table_rows: int):
    pol = query(conn_for("DB2INST1"),
                "SELECT AUTO_ALLOW_MAX, APPROVAL_MAX FROM CUSTODIAN.POLICY"
                " WHERE ROLE_NAME = ? AND TABLE_NAME = ? AND OPERATION = ?", [role or "", table, kind])[1]
    pct = f"{100.0 * rows / table_rows:.1f}% of the rows you can see" if table_rows else "n/a"
    if not pol:
        return "DENY", f"no policy lets {role} {kind} on {table}"
    auto, approval = pol[0]
    if rows <= auto:
        return "ALLOW", f"{rows} row(s) ({pct}) <= auto-allow limit {auto}"
    if rows <= approval:
        return "APPROVE", f"{rows} row(s) ({pct}) needs a human: limit for {role} {kind} on {table} is {auto} automatic, {approval} with approval"
    return "DENY", f"{kind} would touch {rows:,} rows ({pct}); policy max for {role} {kind} on {table} is {approval}"


# --------------------------------------------------------------------------- ledger
def ledger(user, sql, prompt=None, **f) -> int:
    cols = ["DB_USER", "PROMPT", "SQL_TEXT"] + [k.upper() for k in f]
    vals = [user.upper(), (prompt or "")[:2000], sql[:4000]] + list(f.values())
    return scalar(conn_for("DB2INST1"),
                  f"SELECT ENTRY_ID FROM FINAL TABLE (INSERT INTO CUSTODIAN.LEDGER ({', '.join(cols)})"
                  f" VALUES ({', '.join('?' * len(cols))}))", vals)


def record_answer(entry_ids, answer: str):
    g = conn_for("DB2INST1")
    for eid in entry_ids:
        query(g, "UPDATE CUSTODIAN.LEDGER SET ANSWER = ? WHERE ENTRY_ID = ?", [answer[:4000], eid])


def db2_layer(e: Exception) -> str:
    msg = str(e)
    if "SQL0551N" in msg or "SQL0552N" in msg or "42501" in msg:
        return "db2-privileges"
    if "SQL20471N" in msg or "SQL20478N" in msg:
        return "rcac"
    return "db2-error"


# --------------------------------------------------------------------------- the pipeline
def run(user: str, sql: str, prompt: str | None = None, thread_id: str | None = None,
        approved_by: str | None = None, approved_rows: int | None = None) -> dict:
    """Send one agent statement through every layer. Returns a dict the UI renders as one step."""
    user = user.upper()
    sql = sql.strip().rstrip(";").strip()
    out = {"user": user, "sql": sql, "kind": None, "table": None, "rows": None, "table_rows": None,
           "est_cost": None, "est_rows": None, "columns": [], "data": [], "approval_id": None, "tx_ts": None}
    with _lock:
        try:
            kind, table, ast = classify(sql)
        except Blocked as b:
            out.update(decision="DENY", layer=b.layer, reason=b.reason)
            out["ledger_id"] = ledger(user, sql, prompt, decision="DENY", layer=b.layer, reason=b.reason)
            return out
        out.update(kind=kind, table=table)
        uc = conn_for(user)

        if kind == "SELECT":  # reads are always allowed: RCAC decides what comes back
            try:
                as_of = scalar(uc, "VALUES CURRENT TIMESTAMP(12)")
                cols, data = query(uc, sql, limit=MAX_RESULT_ROWS)
            except Exception as e:
                out.update(decision="DENY" if db2_layer(e) != "db2-error" else "ERROR", layer=db2_layer(e), reason=str(e)[:300])
                out["ledger_id"] = ledger(user, sql, prompt, statement_type=kind, decision=out["decision"],
                                          layer=out["layer"], reason=out["reason"])
                return out
            reason = "read executed as " + user + "; Db2 RCAC applied row permissions and column masks"
            out.update(decision="ALLOW", layer="rcac", reason=reason, columns=cols,
                       data=[[str(v) if v is not None else None for v in r] for r in data], rows=len(data))
            out["ledger_id"] = ledger(user, sql, prompt, statement_type=kind, decision="ALLOW", layer="rcac",
                                      reason=reason, rows_affected=len(data), as_of=as_of)
            return out

        # ---- writes: measure the blast radius as the user (RCAC row permissions apply to the count)
        try:
            csql = count_sql(kind, ast)
            rows = len(ast.expression.expressions) if csql is None else int(scalar(uc, csql))
            table_rows = int(scalar(uc, f"SELECT COUNT(*) FROM BANK.{table}"))
            est_cost, est_rows = explain(sql)
        except Exception as e:
            out.update(decision="DENY" if db2_layer(e) != "db2-error" else "ERROR", layer=db2_layer(e), reason=str(e)[:300])
            out["ledger_id"] = ledger(user, sql, prompt, statement_type=kind, table_name=table,
                                      decision=out["decision"], layer=out["layer"], reason=out["reason"])
            return out
        role = role_of(user)
        decision, reason = decide(role, table, kind, rows, table_rows)
        if approved_by and decision != "DENY" and rows > (approved_rows or 0):  # never more than the human saw
            decision, reason = "DENY", f"now touches {rows} rows but {approved_by} approved {approved_rows}"
        out.update(rows=rows, table_rows=table_rows, est_cost=est_cost, est_rows=est_rows, count_sql=csql)
        common = dict(statement_type=kind, table_name=table, rows_affected=rows, table_rows=table_rows, est_cost=est_cost)

        if decision == "DENY":
            out.update(decision="DENY", layer="blast-radius", reason=reason)
            out["ledger_id"] = ledger(user, sql, prompt, decision="DENY", layer="blast-radius", reason=reason, **common)
            return out
        if decision == "APPROVE" and not approved_by:
            out.update(decision="APPROVE", layer="approval", reason=reason)
            out["ledger_id"] = ledger(user, sql, prompt, decision="APPROVE", layer="approval", reason=reason, **common)
            out["approval_id"] = scalar(conn_for("DB2INST1"),
                "SELECT APPROVAL_ID FROM FINAL TABLE (INSERT INTO CUSTODIAN.APPROVALS"
                " (LEDGER_ID, REQUESTED_BY, SQL_TEXT, ROWS_AFFECTED, THREAD_ID) VALUES (?, ?, ?, ?, ?))",
                [out["ledger_id"], user, sql, rows, thread_id])
            return out

        try:
            n, tx_ts = execute_write(user, kind, table, sql, expected=rows)
        except Exception as e:
            out.update(decision="DENY" if db2_layer(e) != "db2-error" else "ERROR", layer=db2_layer(e), reason=str(e)[:300])
            out["ledger_id"] = ledger(user, sql, prompt, decision=out["decision"], layer=out["layer"], reason=out["reason"], **common)
            return out
        why = f"approved by {approved_by}; " if approved_by else ""
        out.update(decision="EXECUTED", layer="approval" if approved_by else "blast-radius",
                   reason=f"{why}{n} row(s) changed as {user}", tx_ts=str(tx_ts) if tx_ts else None)
        out["ledger_id"] = ledger(user, sql, prompt, decision="EXECUTED", layer=out["layer"], reason=out["reason"],
                                  tx_ts=tx_ts, **common)
        return out


def execute_write(user: str, kind: str, table: str, sql: str, expected: int):
    """Run the DML on the user's own connection in one transaction and capture the transaction
    timestamp Db2 stamped on the rows (SYS_START / history SYS_END), which is what Rewind needs."""
    c = connect(user, autocommit=False)
    try:
        pk = TEMPORAL_PK.get(table)
        tx_ts = None
        if pk and kind in ("UPDATE", "INSERT"):
            _, got = query(c, f"SELECT {pk}, SYS_START FROM FINAL TABLE ({sql})")
            n, tx_ts = len(got), (got[0][1] if got else None)
        elif pk and kind == "DELETE":
            _, got = query(c, f"SELECT {pk} FROM OLD TABLE ({sql})")
            n, keys = len(got), [r[0] for r in got]
        else:
            cur = c.cursor()
            cur.execute(sql)
            n = cur.rowcount
            cur.close()
        if n != expected:  # data moved between preflight and execution: never exceed what was measured
            c.rollback()
            raise RuntimeError(f"preflight counted {expected} rows but the statement touched {n}; rolled back")
        c.commit()
        if pk and kind == "DELETE" and n:  # the deleted versions now end at the transaction timestamp
            tx_ts = scalar(c, f"SELECT MAX(SYS_END) FROM BANK.{table} {ALL_TIME}"
                              f" WHERE {pk} IN ({', '.join('?' * n)})", keys)
        return n, tx_ts
    finally:
        c.close()


# --------------------------------------------------------------------------- 3. approvals
def pending_approvals():
    return query(conn_for("DB2INST1"),
                 "SELECT APPROVAL_ID, REQUESTED_BY, SQL_TEXT, ROWS_AFFECTED, THREAD_ID, LEDGER_ID"
                 " FROM CUSTODIAN.APPROVALS WHERE STATUS = 'PENDING' ORDER BY APPROVAL_ID")[1]


def decide_approval(approval_id: int, approver: str, approve: bool) -> dict:
    """An admin approves or rejects. Approved SQL is re-checked and executed AS THE REQUESTER."""
    approver = approver.upper()
    g = conn_for("DB2INST1")
    _, rows = query(g, "SELECT REQUESTED_BY, SQL_TEXT, ROWS_AFFECTED, STATUS FROM CUSTODIAN.APPROVALS WHERE APPROVAL_ID = ?",
                    [approval_id])
    if not rows or rows[0][3] != "PENDING":
        raise ValueError(f"approval {approval_id} is not pending")
    if role_of(approver) != "ADMINS":
        raise PermissionError(f"{approver} is not an admin")
    requester, sql, n, _ = rows[0]
    if requester == approver:
        raise PermissionError("four-eyes rule: you cannot approve your own request")
    query(g, "UPDATE CUSTODIAN.APPROVALS SET STATUS = ?, DECIDED_BY = ?, DECIDED_AT = CURRENT TIMESTAMP"
             " WHERE APPROVAL_ID = ?", ["APPROVED" if approve else "REJECTED", approver, approval_id])
    if not approve:
        lid = ledger(requester, sql, decision="DENY", layer="approval", reason=f"rejected by {approver}")
        return {"user": requester, "sql": sql, "decision": "DENY", "layer": "approval",
                "reason": f"rejected by {approver}", "ledger_id": lid}
    return run(requester, sql, approved_by=approver, approved_rows=n)


# --------------------------------------------------------------------------- 4. temporal rewind
# Db2 protects *_HIST with a default deny-all row permission once RCAC is active on the base table,
# so history is read through the base table with a period specification: the same RCAC rules apply.
ALL_TIME = "FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-31'"


def rewind_sql(table: str, cols: list[str]):
    pk = TEMPORAL_PK[table]
    non_pk = [c for c in cols if c != pk]
    t, h = f"BANK.{table}", f"BANK.{table} {ALL_TIME}"
    return [
        # rows the transaction UPDATED -> put back the version Db2 archived at that instant
        f"UPDATE {t} T SET ({', '.join(non_pk)}) = (SELECT {', '.join(non_pk)} FROM {h} H"
        f" WHERE H.{pk} = T.{pk} AND H.SYS_END = ?)"
        f" WHERE T.SYS_START = ? AND EXISTS (SELECT 1 FROM {h} H WHERE H.{pk} = T.{pk} AND H.SYS_END = ?)",
        # rows the transaction DELETED -> re-insert them from history
        f"INSERT INTO {t} ({', '.join(cols)}) SELECT {', '.join(cols)} FROM {h} H"
        f" WHERE H.SYS_END = ? AND NOT EXISTS (SELECT 1 FROM {t} T WHERE T.{pk} = H.{pk})",
        # rows the transaction INSERTED -> remove them
        f"DELETE FROM {t} T WHERE T.SYS_START = ?"
        f" AND NOT EXISTS (SELECT 1 FROM {h} H WHERE H.{pk} = T.{pk} AND H.SYS_END = ?)",
    ]


def rewind(entry_id: int, by_user: str) -> dict:
    """Undo one agent transaction from Db2's own history, as by_user (an admin), in one transaction."""
    by_user = by_user.upper()
    if role_of(by_user) != "ADMINS":  # a masked identity must never write masked values back
        raise PermissionError(f"{by_user} is not an admin; only ADMINS may rewind")
    with _lock:
        g = conn_for("DB2INST1")
        _, rows = query(g, "SELECT TABLE_NAME, TX_TS, DECISION, REWOUND_BY FROM CUSTODIAN.LEDGER WHERE ENTRY_ID = ?", [entry_id])
        if not rows:
            raise ValueError(f"no ledger entry {entry_id}")
        table, tx, decision, rewound = rows[0]
        if decision != "EXECUTED" or table not in TEMPORAL_PK or tx is None:
            raise ValueError("only executed writes on temporal tables can be rewound")
        if rewound:
            raise ValueError(f"already rewound by ledger entry {rewound}")
        pk = TEMPORAL_PK[table]
        cols = [r[0] for r in query(g, "SELECT COLNAME FROM SYSCAT.COLUMNS WHERE TABSCHEMA = 'BANK' AND TABNAME = ?"
                                       " AND COLNAME NOT IN ('SYS_START', 'SYS_END', 'TRANS_ID') ORDER BY COLNO", [table])[1]]
        c = connect(by_user, autocommit=False)
        try:
            # Refuse if anything the agent wrote was changed again later (rewind would clobber that edit).
            later = scalar(c, f"SELECT COUNT(*) FROM BANK.{table} {ALL_TIME}"
                              " WHERE SYS_START = ? AND SYS_END < '9999-12-30'", [tx])
            if later:
                raise ValueError(f"{later} row(s) were modified after the agent's transaction; rewind refused")
            keys_sql = (f"SELECT {pk} FROM BANK.{table} {ALL_TIME} WHERE SYS_END = ?"
                        f" UNION SELECT {pk} FROM BANK.{table} WHERE SYS_START = ?")
            keys = [r[0] for r in query(c, keys_sql, [tx, tx])[1]]
            sel = f"SELECT {', '.join(cols)} FROM BANK.{table} WHERE {pk} IN ({', '.join('?' * len(keys))}) ORDER BY {pk}"
            before = query(c, sel, keys) if keys else (cols, [])
            upd, ins, dele = rewind_sql(table, cols)
            cur = c.cursor()
            cur.execute(upd, (tx, tx, tx))
            cur.execute(ins, (tx,))
            cur.execute(dele, (tx, tx))
            cur.close()
            after = query(c, sel, keys) if keys else (cols, [])
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()
        text = ";\n".join(rewind_sql(table, cols)).replace("?", f"TIMESTAMP('{tx}')")
        lid = ledger(by_user, text, f"rewind of ledger entry {entry_id}", statement_type="REWIND", table_name=table,
                     decision="EXECUTED", layer="rewind", reason=f"restored {len(keys)} row(s) of {table} to before {tx}",
                     rows_affected=len(keys))
        query(g, "UPDATE CUSTODIAN.LEDGER SET REWOUND_BY = ? WHERE ENTRY_ID = ?", [lid, entry_id])
        fmt = lambda rs: [[str(v) for v in r] for r in rs]  # noqa: E731
        return {"ledger_id": lid, "table": table, "tx_ts": str(tx), "columns": cols,
                "before": fmt(before[1]), "after": fmt(after[1]), "sql": text}


# --------------------------------------------------------------------------- 5. as-of replay
def replay(entry_id: int) -> dict:
    """Re-run a past read exactly as the AI saw it: same SQL, same Db2 identity, and the session's
    CURRENT TEMPORAL SYSTEM_TIME set to the instant it originally ran. Then run it again for 'now'."""
    with _lock:
        _, rows = query(conn_for("DB2INST1"), "SELECT DB_USER, SQL_TEXT, AS_OF, ANSWER, PROMPT FROM CUSTODIAN.LEDGER"
                                              " WHERE ENTRY_ID = ? AND AS_OF IS NOT NULL", [entry_id])
        if not rows:
            raise ValueError(f"ledger entry {entry_id} is not a replayable read")
        user, sql, as_of, answer, prompt = rows[0]
        c = conn_for(user)
        try:
            query(c, "SET CURRENT TEMPORAL SYSTEM_TIME = ?", [as_of])
            cols, then = query(c, sql, limit=MAX_RESULT_ROWS)
        finally:
            query(c, "SET CURRENT TEMPORAL SYSTEM_TIME = NULL")
        _, now = query(c, sql, limit=MAX_RESULT_ROWS)
        fmt = lambda rs: [[str(v) if v is not None else None for v in r] for r in rs]  # noqa: E731
        return {"user": user, "sql": sql, "as_of": str(as_of), "answer": answer, "prompt": prompt,
                "columns": cols, "then": fmt(then), "now": fmt(now)}


def ledger_rows(limit: int = 100):
    return query(conn_for("DB2INST1"),
                 "SELECT ENTRY_ID, CREATED_AT, DB_USER, STATEMENT_TYPE, TABLE_NAME, DECISION, LAYER, ROWS_AFFECTED,"
                 " CASE WHEN AS_OF IS NULL THEN 'N' ELSE 'Y' END AS REPLAYABLE, TX_TS, REWOUND_BY, SQL_TEXT, REASON, ANSWER"
                 f" FROM CUSTODIAN.LEDGER ORDER BY ENTRY_ID DESC FETCH FIRST {int(limit)} ROWS ONLY")
