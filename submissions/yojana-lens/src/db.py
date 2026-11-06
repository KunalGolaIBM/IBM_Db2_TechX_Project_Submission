"""Thin, explicit Db2 access layer.

Design choices worth calling out for reviewers:

* One connection per unit of work, committed as a transaction. The rule
  matrix and the trace it writes are therefore atomic.
* Every statement lives in ``sql/*.sql``; nothing is assembled by string
  concatenation at runtime.
* ``wait_for_db`` exists because the Db2 container needs a few minutes on
  first boot and the app is started by the same compose file.
"""

from __future__ import annotations

import hashlib
import time
from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Optional, Sequence

try:  # The driver loads its own native client, which can be absent on a
    # developer laptop even though it works fine inside the Docker image.
    import ibm_db  # type: ignore
    DRIVER_ERROR: Optional[str] = None
except Exception as exc:  # pragma: no cover - depends on the host machine
    ibm_db = None  # type: ignore[assignment]
    DRIVER_ERROR = str(exc)

from .config import SQL_DIR, settings
from .sql_loader import query as load_query
from .sql_loader import script_statements

SCHEMA_VERSION = "1.0.0"


class Db2Error(RuntimeError):
    pass


def _driver():
    if ibm_db is None:
        raise Db2Error(
            "The IBM Db2 driver (ibm_db) could not be loaded on this machine.\n"
            f"Reason: {DRIVER_ERROR}\n"
            "The supported way to run YojanaLens is the Docker image, which ships "
            "a working driver: `docker compose up --build`."
        )
    return ibm_db


@contextmanager
def connect() -> Iterator[Any]:
    driver = _driver()
    conn = driver.connect(settings.db_conn_string, "", "")
    if not conn:
        raise Db2Error(f"Could not connect to Db2: {driver.conn_errormsg()}")
    try:
        yield conn
        driver.commit(conn)
    except Exception:
        try:
            driver.rollback(conn)
        except Exception:  # pragma: no cover - rollback best effort
            pass
        raise
    finally:
        try:
            driver.close(conn)
        except Exception:  # pragma: no cover
            pass


def fetch_all(conn: Any, sql: str, params: Sequence[Any] = ()) -> list[dict]:
    driver = _driver()
    stmt = _execute(conn, sql, params)
    rows: list[dict] = []
    while True:
        row = driver.fetch_assoc(stmt)
        if not row:
            break
        rows.append({str(k).lower(): v for k, v in row.items()})
    return rows


def fetch_one(conn: Any, sql: str, params: Sequence[Any] = ()) -> Optional[dict]:
    rows = fetch_all(conn, sql, params)
    return rows[0] if rows else None


def execute(conn: Any, sql: str, params: Sequence[Any] = ()) -> int:
    stmt = _execute(conn, sql, params)
    return _num_rows(stmt)


def _execute(conn: Any, sql: str, params: Sequence[Any] = ()):
    driver = _driver()
    try:
        if params:
            return driver.exec_immediate(conn, sql, tuple(params))
        return driver.exec_immediate(conn, sql)
    except Exception as exc:  # ibm_db raises Exception with a useful message
        raise Db2Error(f"{exc}\n--- SQL ---\n{sql.strip()[:1200]}") from exc


def _num_rows(stmt: Any) -> int:
    try:
        count = _driver().num_rows(stmt)
        return count if isinstance(count, int) and count > 0 else 0
    except Exception:  # pragma: no cover
        return 0


# ---------------------------------------------------------------------
# Named-query helpers (single source of truth: sql/03_queries.sql)
# ---------------------------------------------------------------------
def fetch_named(conn: Any, name: str, values: Mapping[str, Any]) -> list[dict]:
    sql, params = load_query(name, values)
    return fetch_all(conn, sql, params)


def fetch_named_one(conn: Any, name: str, values: Mapping[str, Any]) -> Optional[dict]:
    rows = fetch_named(conn, name, values)
    return rows[0] if rows else None


# ---------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------
def wait_for_db(timeout: int = 420, interval: int = 5) -> None:
    driver = _driver()
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            conn = driver.connect(settings.db_conn_string, "", "")
            if conn:
                driver.close(conn)
                return
        except Exception as exc:
            if attempt == 1 or attempt % 6 == 0:
                print(f"[db] waiting for Db2 at {settings.db_host}:{settings.db_port} "
                      f"(attempt {attempt}: {str(exc)[:120]})", flush=True)
        time.sleep(interval)
    raise Db2Error(
        f"Db2 did not become reachable within {timeout}s. "
        f"Check the container logs: docker compose logs db2"
    )


def table_exists(conn: Any, name: str) -> bool:
    row = fetch_one(
        conn,
        "SELECT COUNT(*) AS n FROM SYSCAT.TABLES "
        "WHERE TABLESCHEMA = CURRENT SCHEMA AND TABLENAME = ?",
        (name.upper(),),
    )
    return bool(row and int(row["n"]) > 0)


def init_db(verbose: bool = True) -> None:
    """Create the schema once, then (re)install the stored procedure."""
    wait_for_db()
    with connect() as conn:
        if table_exists(conn, "SCHEMES"):
            if verbose:
                print("[db] schema already present - skipping DDL")
        else:
            if verbose:
                print("[db] creating schema ...")
            for statement in script_statements(SQL_DIR / "01_schema.sql"):
                execute(conn, statement)
            if verbose:
                print("[db] schema ready")

    with connect() as conn:
        statements = script_statements(SQL_DIR / "04_procedure.sql")
        for statement in statements:
            execute(conn, statement)
        if verbose:
            print("[db] SP_RECORD_TRACE installed")


def reset_db(verbose: bool = True) -> None:
    wait_for_db()
    with connect() as conn:
        for statement in script_statements(SQL_DIR / "00_reset.sql"):
            try:
                execute(conn, statement)
            except Db2Error as exc:
                if verbose:
                    print(f"[db] ignoring: {str(exc).splitlines()[0]}")
    init_db(verbose=verbose)


# ---------------------------------------------------------------------
# Audit helpers
# ---------------------------------------------------------------------
def sql_hash(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()[:32]


def audit(conn: Any, run_id: Optional[str], actor: str, action: str,
          detail: str = "", sql: str = "") -> None:
    execute(
        conn,
        "INSERT INTO audit_log (run_id, actor, action, detail, sql_hash) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_id, actor[:64], action[:64], detail[:2000], sql_hash(sql) if sql else None),
    )


def create_profile(conn: Any, profile_id: str, raw_text: str) -> None:
    execute(conn, "DELETE FROM profiles WHERE profile_id = ?", (profile_id,))
    execute(
        conn,
        "INSERT INTO profiles (profile_id, raw_text, structured_json) VALUES (?, ?, ?)",
        (profile_id, raw_text, "{}"),
    )


def insert_facts(conn: Any, profile_id: str, facts: Mapping[str, Any],
                 structured_json: str) -> None:
    execute(conn, "DELETE FROM profile_facts WHERE profile_id = ?", (profile_id,))
    execute(
        conn, "UPDATE profiles SET structured_json = ? WHERE profile_id = ?",
        (structured_json, profile_id),
    )
    for key, value in facts.items():
        num = float(value) if isinstance(value, (int, float)) else None
        text = None if num is not None else str(value)
        execute(
            conn,
            "INSERT INTO profile_facts (profile_id, fact_key, fact_num, fact_text) "
            "VALUES (?, ?, ?, ?)",
            (profile_id, key, num, text),
        )


def record_trace(conn: Any, run_id: str, profile_id: str) -> int:
    execute(conn, "CALL SP_RECORD_TRACE(?, ?)", (run_id, profile_id))
    row = fetch_one(
        conn, "SELECT COUNT(*) AS n FROM decision_trace WHERE run_id = ?", (run_id,)
    )
    return int(row["n"]) if row else 0


def start_run(conn: Any, run_id: str, profile_id: str, retriever_top_k: int,
              started_at: Any) -> None:
    execute(
        conn,
        "INSERT INTO agent_runs (run_id, profile_id, model, prompt_version, "
        "retriever_top_k, status, started_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (run_id, profile_id, settings.llm_model, settings.prompt_version,
         retriever_top_k, "RUNNING", started_at),
    )


def finish_run(conn: Any, run_id: str, status: str, latency_ms: int,
               candidates: int, summary_json: str) -> None:
    execute(
        conn,
        "UPDATE agent_runs SET status = ?, latency_ms = ?, candidates = ?, "
        "summary_json = ?, finished_at = CURRENT TIMESTAMP WHERE run_id = ?",
        (status, latency_ms, candidates, summary_json, run_id),
    )
