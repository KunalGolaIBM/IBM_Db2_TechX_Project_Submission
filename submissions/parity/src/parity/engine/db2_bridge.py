"""Db2 executor through a Linux container bridge.

The Windows ibm_db driver fails with SQL1042C. This
executor runs the same driver inside a Linux container
instead. It shells out to docker run, sends SQL on
stdin, and reads JSON on stdout.

Parity already needs Docker for the databases, so
this adds no new requirement.
"""

from __future__ import annotations

import json
import os
import subprocess
import time

from parity.config import DatabaseSettings
from parity.engine.db2_types import convert_row
from parity.engine.result import ResultSet
from parity.engine.safety import assert_read_only

_DEFAULT_IMAGE = "parity-bridge:latest"
_DEFAULT_ROW_LIMIT = 100_000
_BRIDGE_ATTEMPTS = 2
_BRIDGE_RETRY_SECONDS = 1.0


class Db2BridgeExecutor:
    """Execute read queries on Db2 via a Linux container."""

    def __init__(
        self,
        settings: DatabaseSettings,
        image: str = _DEFAULT_IMAGE,
        row_limit: int = _DEFAULT_ROW_LIMIT,
    ) -> None:
        settings.require_complete("Db2")
        if row_limit <= 0:
            raise ValueError("row_limit must be positive")
        self._settings = settings
        self._image = image
        self._row_limit = row_limit

    def _docker_command(self) -> list[str]:
        env_args: list[str] = []
        for name in (
            "PARITY_DB2_HOST",
            "PARITY_DB2_PORT",
            "PARITY_DB2_USER",
            "PARITY_DB2_PASSWORD",
            "PARITY_DB2_DB",
        ):
            value = os.environ.get(name, "")
            if value:
                env_args.extend(["-e", f"{name}={value}"])
        return [
            "docker",
            "run",
            "--rm",
            "-i",
            "--add-host=host.docker.internal:host-gateway",
            *env_args,
            self._image,
            "python",
            "-m",
            "parity.bridge_client",
        ]

    def _run(self, sql: str, timeout_seconds: float) -> str:
        """Run the bridge once. Return the raw output."""
        completed = subprocess.run(
            self._docker_command(),
            input=sql,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()[:300]
            raise RuntimeError(
                f"bridge failed (exit {completed.returncode}): {detail}"
            )
        return completed.stdout

    def _run_with_retry(self, sql: str, timeout_seconds: float) -> str:
        """Run the bridge, retrying a container that failed to start.

        Starting a container can fail for a short time under
        load. The query is read only, so a retry is safe.
        """
        last_error: Exception | None = None
        for attempt in range(_BRIDGE_ATTEMPTS):
            try:
                return self._run(sql, timeout_seconds)
            except RuntimeError as exc:
                last_error = exc
                if "bridge failed" not in str(exc):
                    raise
                time.sleep(_BRIDGE_RETRY_SECONDS * (attempt + 1))
        raise last_error if last_error else RuntimeError("bridge failed")

    def execute(self, sql: str, timeout_seconds: float = 60.0) -> ResultSet:
        """Run SQL through the bridge. Return the result set."""
        assert_read_only(sql)
        output = self._run_with_retry(sql, timeout_seconds)
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"bridge returned bad JSON: {exc}") from exc
        if "error" in payload:
            raise RuntimeError(f"bridge error: {payload['error']}")
        types = payload.get("types") or []
        rows = [
            convert_row(tuple(row), list(types)) if types else tuple(row)
            for row in payload["rows"]
        ]
        if len(rows) > self._row_limit:
            raise ValueError(f"result exceeds row limit of {self._row_limit}")
        return ResultSet(columns=tuple(payload["columns"]), rows=tuple(rows))
