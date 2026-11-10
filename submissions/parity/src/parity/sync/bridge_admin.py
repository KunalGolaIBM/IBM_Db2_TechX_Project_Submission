"""Db2 admin client through the Linux bridge.

The Windows ibm_db driver cannot reach a Db2 server, so a
write from the host has to go through the bridge container.
This client sends the statement and its parameters, and the
container binds the parameters with the driver.

The parameters are never pasted into the SQL text. That
keeps the same rule as the direct client: user data never
becomes SQL.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Sequence
from typing import Any

_DEFAULT_IMAGE = "parity-bridge:latest"


class Db2BridgeAdmin:
    """Run DDL and DML on Db2 through the bridge container."""

    def __init__(self, settings, image: str = _DEFAULT_IMAGE) -> None:
        settings.require_complete("Db2")
        self._settings = settings
        self._image = image

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

    def execute(
        self, sql: str, params: Sequence[Any] = ()
    ) -> tuple[list[str], list[tuple]]:
        """Run one statement with bound parameters.

        Return the column names and the rows. A statement
        without a result set gives empty lists.
        """
        request = json.dumps({"sql": sql, "params": list(params)})
        completed = subprocess.run(
            self._docker_command(),
            input=request,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()[:300]
            raise RuntimeError(
                f"bridge failed (exit {completed.returncode}): {detail}"
            )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"bridge returned bad JSON: {exc}") from exc
        if "error" in payload:
            raise RuntimeError(f"bridge error: {payload['error']}")
        rows = [tuple(row) for row in payload.get("rows", [])]
        return list(payload.get("columns", [])), rows

    def execute_ddl(self, sql: str) -> None:
        """Run one DDL statement. Raise on error."""
        self.execute(sql)

    def insert_rows(
        self, table: str, columns: tuple[str, ...], rows: list[tuple]
    ) -> None:
        """Insert rows with bound parameters.

        Every row gets its own set of markers, so the
        parameter count always matches the statement.
        """
        if not rows:
            return
        col_sql = ", ".join(f'"{c.upper()}"' for c in columns)
        one_row = ", ".join("?" for _ in columns)
        values = ", ".join(f"({one_row})" for _ in rows)
        sql = f'INSERT INTO "{table.upper()}" ({col_sql}) VALUES {values}'
        params = [value for row in rows for value in row]
        self.execute(sql, params)
