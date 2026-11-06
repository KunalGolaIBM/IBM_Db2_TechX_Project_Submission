"""The DAG imports cleanly, without touching Db2, and has the expected shape.

Runs in the Airflow virtualenv (airflow/requirements-airflow.txt); skipped anywhere Airflow is not installed.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

pytest.importorskip("airflow")

DAGS = Path(__file__).resolve().parents[1] / "dags"


@pytest.fixture(scope="module")
def bag():
    from airflow.dag_processing.dagbag import DagBag  # Airflow 3 (examples come from settings, off in CI)

    return DagBag(dag_folder=str(DAGS))


def test_the_dag_folder_imports_without_errors(bag):
    assert bag.import_errors == {}
    assert set(bag.dags) == {"asof_nightly_audit"}


def test_the_audit_runs_in_order_once_a_day_without_backfilling(bag):
    dag = bag.dags["asof_nightly_audit"]
    assert {t.task_id for t in dag.tasks} == {"verify_chain", "recently_changed_clauses", "impact_of_change", "report"}
    assert "verify_chain" in dag.get_task("recently_changed_clauses").upstream_task_ids  # a broken chain stops the rest
    assert {"verify_chain", "impact_of_change"} <= dag.get_task("report").upstream_task_ids
    assert dag.catchup is False and dag.max_active_runs == 1
    assert all(t.execution_timeout == dt.timedelta(minutes=10) and t.retries == 1 for t in dag.tasks)


def test_the_dag_passes_credentials_to_the_driver_not_in_the_dsn():
    source = (DAGS / "asof_nightly_audit.py").read_text()
    assert "PWD=" not in source.replace('"PWD=..."', "").replace("as PWD=...", "")
    assert "ibm_db_dbi.connect(dsn, c.login" in source


class _BrokenChain:
    """A Db2 connection whose VERIFY_CHAIN reports a broken chain."""

    def cursor(self):
        return self

    def callproc(self, name, params):
        assert name == "VERIFY_CHAIN"
        return ("BROKEN", 7, 4, "row content does not match its ROW_HASH")

    def close(self):
        pass


def test_a_broken_chain_fails_the_run(bag, monkeypatch):
    verify = bag.dags["asof_nightly_audit"].get_task("verify_chain").python_callable
    monkeypatch.setitem(verify.__globals__, "_connect", lambda: _BrokenChain())  # the module DagBag loaded
    with pytest.raises(RuntimeError, match="broken at entry 4"):
        verify()
