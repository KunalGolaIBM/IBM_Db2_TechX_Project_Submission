"""Nightly audit of the AsOf ledger and policy store, as an Airflow DAG (IBM Db2 provider).

    verify_chain  ->  recently_changed_clauses  ->  impact_of_change (one mapped task per clause)  ->  report

- verify_chain calls VERIFY_CHAIN as the runtime user and fails the run if any row, link or
  citation does not verify, so a broken chain pages someone instead of waiting for a dispute.
- recently_changed_clauses finds clause versions recorded in the last LOOKBACK_HOURS (system time),
  other than the initial load.
- impact_of_change runs CHANGE_IMPACT for each of them: answers now stale for their date, and
  help-centre answers that need review.

Connection: Airflow connection ASOF_DB2_APP (conn type ibmdb2), the least-privilege runtime user
asofapp, whose only privileges are SELECT and EXECUTE on these procedures. Every statement is a
literal with ? parameters; the schema is bound with SET CURRENT SCHEMA = ? and SET CURRENT PATH.
"""

from __future__ import annotations

import datetime as dt
import logging

from airflow.providers.ibm.db2.hooks.db2 import Db2Hook
from airflow.sdk import Param, dag, task

log = logging.getLogger(__name__)

APP_CONN_ID = "asof_db2_app"
SCHEMA = "ASOF"
LOOKBACK_HOURS = 24  # default; a run can set params.lookback_hours
# The columns of CHANGE_IMPACT's result set (asof/policy.py reads the same ones).
IMPACT_KEYS = ("kind", "ref_id", "for_from", "for_to", "state", "created_at", "cited_version", "current_version",
               "status", "stale_from")

INITIAL_LOAD = "Initial policy load"  # the change note seed.py gives the seeded versions
SQL_CHANGED = ("SELECT DISTINCT CLAUSE_ID FROM POLICY_CLAUSE "
               "WHERE SYS_START >= CURRENT TIMESTAMP - CAST(? AS INTEGER) HOURS AND CHANGE_NOTE <> ? ORDER BY CLAUSE_ID")


class AsOfDb2Hook(Db2Hook):
    """The provider's hook, with credentials passed to the driver as arguments.

    Db2Hook.get_conn (provider 0.1.0) splices the password into the DSN string as PWD=..., where a
    ';' in a password would break the string. AsOf's rule is that credentials never enter a DSN.
    """

    def get_conn(self):
        import ibm_db_dbi

        c = self.get_connection(self.get_conn_id())
        dsn = (f"DATABASE={c.schema or 'testdb'};HOSTNAME={c.host or 'localhost'};PORT={c.port or 50000};"
               "PROTOCOL=TCPIP;CONNECTTIMEOUT=15;")
        return ibm_db_dbi.connect(dsn, c.login or "", c.password or "")


def _connect():
    conn = AsOfDb2Hook(db2_conn_id=APP_CONN_ID).get_conn()
    cur = conn.cursor()
    cur.execute("SET CURRENT SCHEMA = ?", (SCHEMA,))  # tables and views
    cur.execute("SET CURRENT PATH = SYSTEM PATH, ?", (SCHEMA,))  # unqualified CALLs resolve through the path
    cur.close()
    return conn


@dag(dag_id="asof_nightly_audit", schedule="@daily", start_date=dt.datetime(2026, 11, 1), catchup=False,
     max_active_runs=1, tags=["asof", "db2", "audit"],
     params={"lookback_hours": Param(LOOKBACK_HOURS, type="integer", minimum=0, maximum=24 * 31)},
     default_args={"retries": 1, "retry_delay": dt.timedelta(minutes=5), "execution_timeout": dt.timedelta(minutes=10)})
def asof_nightly_audit():
    @task
    def verify_chain() -> dict:
        conn = _connect()
        try:
            cur = conn.cursor()
            status, checked, first_bad, detail = cur.callproc("VERIFY_CHAIN", (" " * 12, 0, 0, " " * 300))
            cur.close()
        finally:
            conn.close()
        result = {"status": str(status).strip(), "rows": int(checked or 0), "first_bad": int(first_bad or 0),
                  "detail": str(detail).strip()}
        log.info("VERIFY_CHAIN: %s", result)
        if result["status"] != "OK":
            raise RuntimeError(f"ledger chain is broken at entry {result['first_bad']}: {result['detail']}")
        return result

    @task
    def recently_changed_clauses(**context) -> list[str]:
        hours = int(context["params"]["lookback_hours"])
        conn = _connect()
        try:
            cur = conn.cursor()
            cur.execute(SQL_CHANGED, (hours, INITIAL_LOAD))
            ids = [r[0].strip() for r in cur.fetchall()]
            cur.close()
        finally:
            conn.close()
        log.info("clauses recorded in the last %d hours: %s", hours, ids or "none")
        return ids

    @task
    def impact_of_change(clause_id: str) -> dict:
        conn = _connect()
        try:
            cur = conn.cursor()
            cur.callproc("CHANGE_IMPACT", (clause_id,))
            rows = [dict(zip(IMPACT_KEYS, r, strict=False)) for r in (cur.fetchall() or [])]
            cur.close()
        finally:
            conn.close()
        counts: dict[str, int] = {}
        for r in rows:
            key = str(r["status"]).strip()
            counts[key] = counts.get(key, 0) + 1
        return {"clause_id": clause_id, "counts": counts}

    @task(trigger_rule="none_failed")  # also on a night with no changes, when the mapped task has nothing to do
    def report(chain: dict, impacts: list[dict]) -> dict:
        impacts = list(impacts or [])  # mapped results arrive as a lazy sequence
        needs_review = sum(i["counts"].get("NEEDS_REVIEW", 0) + i["counts"].get("STALE", 0) for i in impacts)
        summary = {"chain_rows": chain["rows"], "clauses_changed": len(impacts), "answers_to_review": needs_review,
                   "by_clause": impacts}
        log.info("nightly audit: %s", summary)
        return summary

    chain = verify_chain()
    changed = recently_changed_clauses()
    chain >> changed
    report(chain, impact_of_change.expand(clause_id=changed))


asof_nightly_audit()
