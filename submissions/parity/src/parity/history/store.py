"""History stores.

The run history gives every run a durable id and keeps
one row per query outcome. This is the base for the
regression mode later: rerun the same workload and diff
against the last passing run.

InMemoryRunStore is for tests and local runs. Db2RunStore
keeps the history in Db2 tables as system of record. The
Db2 store works where the ibm_db driver works, which on
this project means a Linux bridge environment.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol

from parity.history.types import ComparisonRecord, RunRecord
from parity.report.risk import QueryReport
from parity.sync.db2_admin import Db2Admin

RUN_TABLE_DDL = """CREATE TABLE run (
    run_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_dir VARCHAR(500) NOT NULL,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    finished_at TIMESTAMP,
    exit_code INTEGER
)"""

COMPARISON_RESULT_DDL = """CREATE TABLE comparison_result (
    result_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id INTEGER NOT NULL,
    query_id VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    risk_score INTEGER,
    risk_label VARCHAR(10),
    note VARCHAR(500),
    source_sql VARCHAR(3000),
    db2_sql VARCHAR(3000),
    diff_summary VARCHAR(1000)
)"""


class RunStore(Protocol):
    """Store interface for run history."""

    def start_run(self, source_dir: str) -> int:
        """Create one run row. Return its id."""
        ...

    def save_records(
        self, run_id: int, records: Sequence[ComparisonRecord]
    ) -> None:
        """Save the query outcomes of one run."""
        ...

    def finish_run(self, run_id: int, exit_code: int) -> None:
        """Mark one run finished with its exit code."""
        ...

    def get_run(self, run_id: int) -> RunRecord:
        """Load one run with its records."""
        ...

    def list_runs(self) -> Sequence[RunRecord]:
        """List all runs, oldest first."""
        ...


class InMemoryRunStore:
    """Dict backed store. For tests and local runs."""

    def __init__(self) -> None:
        self._runs: dict[int, RunRecord] = {}
        self._next_id = 1

    def start_run(self, source_dir: str) -> int:
        """Create one run row. Return its id."""
        run = RunRecord(run_id=self._next_id, source_dir=source_dir)
        self._runs[run.run_id] = run
        self._next_id += 1
        return run.run_id

    def save_records(
        self, run_id: int, records: Sequence[ComparisonRecord]
    ) -> None:
        """Save the query outcomes of one run."""
        run = self._require(run_id)
        run.records = tuple(records)

    def finish_run(self, run_id: int, exit_code: int) -> None:
        """Mark one run finished with its exit code."""
        run = self._require(run_id)
        run.exit_code = exit_code
        run.finished_at = datetime.now(UTC).isoformat()

    def get_run(self, run_id: int) -> RunRecord:
        """Load one run with its records."""
        return self._require(run_id)

    def list_runs(self) -> Sequence[RunRecord]:
        """List all runs, oldest first."""
        return tuple(self._runs.values())

    def _require(self, run_id: int) -> RunRecord:
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(f"unknown run id: {run_id}")
        return run


def save_run(
    store: RunStore,
    source_dir: str,
    reports: Sequence[QueryReport],
    exit_code: int,
) -> int:
    """Store one full run. Return the run id."""
    run_id = store.start_run(source_dir)
    store.save_records(run_id, [ComparisonRecord.from_report(r) for r in reports])
    store.finish_run(run_id, exit_code)
    return run_id


class Db2RunStore:
    """Db2 backed store using the run history tables."""

    def __init__(self, admin: Db2Admin) -> None:
        if not isinstance(admin, Db2Admin):
            raise TypeError("Db2RunStore needs a Db2Admin instance")
        self._admin = admin

    def create_tables(self) -> None:
        """Create the run and comparison_result tables."""
        self._admin.execute_ddl(RUN_TABLE_DDL)
        self._admin.execute_ddl(COMPARISON_RESULT_DDL)

    def start_run(self, source_dir: str) -> int:
        """Create one run row. Return the generated id."""
        import ibm_db

        conn = self._admin._connect()
        try:
            stmt = ibm_db.prepare(conn, "INSERT INTO run (source_dir) VALUES (?)")
            ibm_db.bind_param(stmt, 1, source_dir)
            ibm_db.execute(stmt)
            result = ibm_db.exec_immediate(
                conn, "SELECT IDENTITY_VAL_LOCAL() FROM SYSIBM.SYSDUMMY1"
            )
            row = ibm_db.fetch_tuple(result)
            if row is None or row is False:
                raise RuntimeError("could not read the new run id")
            return int(row[0])
        finally:
            ibm_db.close(conn)

    def save_records(
        self, run_id: int, records: Sequence[ComparisonRecord]
    ) -> None:
        """Save the query outcomes with bound parameters."""
        rows = [
            (
                run_id,
                record.query_id,
                record.status,
                record.risk_score,
                record.risk_label,
                record.note,
                record.source_sql,
                record.db2_sql,
                record.diff_summary,
            )
            for record in records
        ]
        self._admin.insert_rows(
            "comparison_result",
            (
                "run_id",
                "query_id",
                "status",
                "risk_score",
                "risk_label",
                "note",
                "source_sql",
                "db2_sql",
                "diff_summary",
            ),
            rows,
        )

    def finish_run(self, run_id: int, exit_code: int) -> None:
        """Mark one run finished with its exit code."""
        import ibm_db

        conn = self._admin._connect()
        try:
            stmt = ibm_db.prepare(
                conn,
                "UPDATE run SET finished_at = CURRENT TIMESTAMP, exit_code = ? "
                "WHERE run_id = ?",
            )
            ibm_db.bind_param(stmt, 1, exit_code)
            ibm_db.bind_param(stmt, 2, run_id)
            ibm_db.execute(stmt)
        finally:
            ibm_db.close(conn)

    def get_run(self, run_id: int) -> RunRecord:
        """Load one run with its records."""
        import ibm_db

        conn = self._admin._connect()
        try:
            stmt = ibm_db.prepare(
                conn,
                "SELECT run_id, source_dir, started_at, finished_at, exit_code "
                "FROM run WHERE run_id = ?",
            )
            ibm_db.bind_param(stmt, 1, run_id)
            ibm_db.execute(stmt)
            row = ibm_db.fetch_tuple(stmt)
            if row is None or row is False:
                raise KeyError(f"unknown run id: {run_id}")
            run = RunRecord(
                run_id=int(row[0]),
                source_dir=str(row[1]),
                started_at=str(row[2]),
                finished_at=str(row[3]),
                exit_code=int(row[4]) if row[4] is not None else None,
            )
            stmt = ibm_db.prepare(
                conn,
                "SELECT query_id, source_sql, db2_sql, status, risk_score, "
                "risk_label, note, diff_summary FROM comparison_result "
                "WHERE run_id = ? ORDER BY result_id",
            )
            ibm_db.bind_param(stmt, 1, run_id)
            ibm_db.execute(stmt)
            records: list[ComparisonRecord] = []
            while True:
                item = ibm_db.fetch_tuple(stmt)
                if item is None or item is False:
                    break
                records.append(
                    ComparisonRecord(
                        query_id=str(item[0]),
                        source_sql=str(item[1]),
                        db2_sql=str(item[2]),
                        status=str(item[3]),
                        risk_score=int(item[4]) if item[4] is not None else 0,
                        risk_label=str(item[5]),
                        note=item[6] or "",
                        diff_summary=item[7] or "",
                    )
                )
            run.records = tuple(records)
            return run
        finally:
            ibm_db.close(conn)

    def list_runs(self) -> Sequence[RunRecord]:
        """List all runs, oldest first. Records are not attached."""
        import ibm_db

        conn = self._admin._connect()
        try:
            stmt = ibm_db.prepare(
                conn,
                "SELECT run_id, source_dir, started_at, finished_at, exit_code "
                "FROM run ORDER BY run_id",
            )
            ibm_db.execute(stmt)
            runs: list[RunRecord] = []
            while True:
                row = ibm_db.fetch_tuple(stmt)
                if row is None or row is False:
                    break
                runs.append(
                    RunRecord(
                        run_id=int(row[0]),
                        source_dir=str(row[1]),
                        started_at=str(row[2]),
                        finished_at=str(row[3]),
                        exit_code=int(row[4]) if row[4] is not None else None,
                    )
                )
            return tuple(runs)
        finally:
            ibm_db.close(conn)
