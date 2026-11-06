#!/usr/bin/env python3
"""Write the ASOF schema's DDL, as Db2 itself holds it, to docs/ddl/asof_schema_db2look.sql.

    python scripts/export_ddl.py

Runs IBM's db2look inside the Db2 container (DB2_CONTAINER and DB2_DATABASE from .env), so the
file is what the catalog contains after setup, not a copy of the source SQL. The same DDL can
be exported from the IBM Db2 Developer Extension for VS Code (Generate DDL on schema ASOF).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from asof.config import get_settings  # noqa: E402

OUT = PROJECT / "docs" / "ddl" / "asof_schema_db2look.sql"
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")


def main() -> int:
    s = get_settings()
    container, database = s.db2_container, s.db2_database
    if not (NAME.match(container) and NAME.match(database)):
        print("DB2_CONTAINER or DB2_DATABASE is not a plain name", file=sys.stderr)
        return 1
    tmp = "/tmp/asof_db2look.ddl"
    cmd = ["docker", "exec", "-u", "db2inst1", container, "bash", "-lc",
           f"db2look -d {database} -z ASOF -e -o {tmp} > /dev/null"]
    subprocess.run(cmd, check=True, timeout=300)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["docker", "cp", f"{container}:{tmp}", str(OUT)], check=True, timeout=60)
    subprocess.run(["docker", "exec", container, "rm", "-f", tmp], check=False, timeout=60)
    text = OUT.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^-- Timestamp: .*$", "-- Timestamp: (removed so the file only changes when the schema does)", text)
    if "CREATE VECTOR INDEX" in text:
        text = ("-- NOTE (AsOf): db2look 12.1.5 writes CREATE VECTOR INDEX without its distance metric, in\n"
                "-- SYSCATSPACE and with zero build parameters, so that statement below cannot be replayed as is.\n"
                "-- The real definition (WITH DISTANCE COSINE IN ASOF_TS32K COMPRESSED VECTORS IN ASOF_TS32K) is in\n"
                "-- src/asof/sql/01_tables.sql, and SYSCAT.INDEXES confirms the index is in ASOF_TS32K.\n\n" + text)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(PROJECT)} ({text.count(chr(10))} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
