"""File backed run history.

The Db2 store is the system of record inside the bridge
environment. On a machine without a working ibm_db
driver, a history file gives the same audit trail. One
JSON file holds all runs of a workload.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from parity.history.types import ComparisonRecord, RunRecord

if TYPE_CHECKING:
    from collections.abc import Sequence


class JsonRunStore:
    """One JSON file holds every run of a workload."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._runs: list[RunRecord] = []
        if path.exists():
            self._runs = [RunRecord(**raw) for raw in self._load()]

    def _load(self) -> list[dict]:
        text = self._path.read_text(encoding="utf-8")
        data = json.loads(text)
        runs = data.get("runs", [])
        for run in runs:
            run["records"] = tuple(ComparisonRecord(**item) for item in run["records"])
        return runs

    def _flush(self) -> None:
        payload = {"runs": []}
        for run in self._runs:
            item = asdict(run)
            item["records"] = [asdict(record) for record in run.records]
            payload["runs"].append(item)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def start_run(self, source_dir: str) -> int:
        """Create one run row. Set the start time. Return its id."""
        run_id = max((run.run_id for run in self._runs), default=0) + 1
        active = RunRecord(run_id=run_id, source_dir=source_dir, started_at=datetime.now(UTC).isoformat())
        self._runs.append(active)
        self._flush()
        return run_id

    def save_records(
        self, run_id: int, records: Sequence[ComparisonRecord]
    ) -> None:
        """Save the query outcomes of one run."""
        run = self._require(run_id)
        run.records = tuple(records)
        self._flush()

    def finish_run(self, run_id: int, exit_code: int) -> None:
        """Mark one run finished with its exit code."""
        run = self._require(run_id)
        run.exit_code = exit_code
        run.finished_at = datetime.now(UTC).isoformat()
        self._flush()

    def get_run(self, run_id: int) -> RunRecord:
        """Load one run with its records."""
        return self._require(run_id)

    def list_runs(self) -> Sequence[RunRecord]:
        """List all runs, oldest first."""
        return tuple(self._runs)

    def _require(self, run_id: int) -> RunRecord:
        run = next((item for item in self._runs if item.run_id == run_id), None)
        if run is None:
            raise KeyError(f"unknown run id: {run_id}")
        return run
