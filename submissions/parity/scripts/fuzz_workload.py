"""Run a fuzz case over the sample workload.

Runs inside a Linux container where the ibm_db driver
works. It loads edge case rows into both databases and
then runs the workload on both, so the engine can show
which queries behave differently on edge case data.

Usage in the bridge container:

    python /app/scripts/fuzz_workload.py --dir /app/samples --rows 20
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> int:
    """Load fuzz rows into both databases and run the workload."""
    parser = argparse.ArgumentParser(prog="fuzz_workload")
    parser.add_argument("--dir", default="samples", help="Workload directory")
    parser.add_argument("--rows", type=int, default=20, help="Fuzz rows per table")
    parser.add_argument("--seed", type=int, default=42, help="Fuzz seed")
    parser.add_argument("--out", default="", help="Optional JSON report path")
    args = parser.parse_args()

    from parity.config import load_settings
    from parity.engine.db2 import Db2Executor
    from parity.engine.postgres import PostgresExecutor
    from parity.fuzz.runner import run_fuzz_case
    from parity.sync.db2_admin import Db2Admin
    from parity.sync.schema import introspect_postgres
    from parity.translate.schema import schema_from_postgres

    source_settings, db2_settings = load_settings()
    admin = Db2Admin(db2_settings)
    tables = introspect_postgres(source_settings)
    schema = schema_from_postgres(source_settings)
    print("tables:", ", ".join(table.name for table in tables))

    outcomes, reports = run_fuzz_case(
        Path(args.dir),
        PostgresExecutor(source_settings),
        Db2Executor(db2_settings),
        source_settings,
        admin,
        tables,
        rows_per_table=args.rows,
        seed=args.seed,
        schema=schema,
    )
    for outcome in outcomes:
        print(
            f"fuzzed {outcome.table}: {outcome.rows} rows, "
            f"plan {outcome.plan_id}, checksum {outcome.checksum[:12]}"
        )
    counts = Counter(report.result.status.value for report in reports)
    print("result:", dict(counts))
    mismatched = [
        (report.query_id, report.source_sql) for report in reports
        if report.result.status.value != "MATCH"
    ]
    for query_id, sql in mismatched:
        print(f"  {query_id} {sql[:70]}")
    if args.out:
        Path(args.out).write_text(
            json.dumps(
                {
                    "fuzz": [
                        {
                            "table": outcome.table,
                            "plan_id": outcome.plan_id,
                            "rows": outcome.rows,
                            "checksum": outcome.checksum,
                        }
                        for outcome in outcomes
                    ],
                    "queries": [
                        {
                            "query_id": report.query_id,
                            "status": report.result.status.value,
                            "source_sql": report.source_sql,
                            "db2_sql": report.db2_sql,
                            "note": report.result.note,
                            "diffs": [
                                {
                                    "kind": diff.kind.value,
                                    "detail": diff.detail,
                                    "source": str(diff.source_value),
                                    "target": str(diff.target_value),
                                }
                                for diff in report.result.diffs
                            ],
                        }
                        for report in reports
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print("report written:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
