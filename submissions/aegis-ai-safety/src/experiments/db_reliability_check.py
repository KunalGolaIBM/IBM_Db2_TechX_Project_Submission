#!/usr/bin/env python3
"""Real IBM Db2 reliability checks for AEGIS."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.core.errors import DatabaseOperationError, DatabaseUnavailableError  # noqa: E402
from app.db.connection import execute, insert_returning_id, query_all, transaction  # noqa: E402
from app.db.repository import Db2Repository  # noqa: E402
from app.services.documents import DocumentService  # noqa: E402

OUT = ROOT / "reports" / "db2_reliability_results.json"
PYTHON = ROOT / ".venv" / "bin" / "python"


def main() -> int:
    results = {}
    settings = get_settings()
    repository = Db2Repository(settings)

    # 1. Live health and six tables.
    health = repository.health()
    results["health"] = {
        "passed": health["connected"] and not health["missing_tables"],
        "tables": health["tables"],
        "missing": health["missing_tables"],
    }

    # 2. Constraints and indexes.
    with transaction() as connection:
        constraints = query_all(
            connection,
            "SELECT COUNT(*) AS N FROM SYSCAT.TABCONST WHERE TABSCHEMA = ? AND TYPE IN ('P','F','U','K')",
            ("AEGIS",),
        )[0]["n"]
        indexes = query_all(
            connection,
            "SELECT COUNT(*) AS N FROM SYSCAT.INDEXES WHERE TABSCHEMA = ?",
            ("AEGIS",),
        )[0]["n"]
        columns = query_all(
            connection,
            "SELECT COLNAME FROM SYSCAT.COLUMNS WHERE TABSCHEMA = 'AEGIS' AND TABNAME = 'DOCUMENTS'",
        )
    names = {row["colname"] for row in columns}
    results["schema"] = {
        "passed": constraints >= 10 and indexes >= 7 and {"EXTERNAL_ID", "PROCESSING_STATUS"} <= names,
        "constraints": int(constraints),
        "indexes": int(indexes),
        "documents_columns": sorted(names),
    }

    # 3. Idempotent init script, run twice.
    first = subprocess.run(
        [str(PYTHON), "database/init_db.py", "--stats"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    second = subprocess.run(
        [str(PYTHON), "database/init_db.py", "--stats"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    results["idempotent_init"] = {
        "passed": first.returncode == 0 and second.returncode == 0,
        "first_exit": first.returncode,
        "second_exit": second.returncode,
        "second_tail": second.stdout.strip().splitlines()[-1] if second.stdout else "",
    }

    # 4. Duplicate upload by content hash.
    marker = f"reliability-check-{time.time_ns()}"
    service = DocumentService(repository)
    first_upload = service.ingest_pasted(
        f"{marker}. SolarCell-X achieved 92% efficiency in a controlled trial.",
        title=f"Reliability duplicate check {marker}",
    )
    second_upload = service.ingest_pasted(
        f"{marker}. SolarCell-X achieved 92% efficiency in a controlled trial.",
        title=f"Reliability duplicate check {marker}",
    )
    with transaction() as connection:
        count = query_all(
            connection,
            "SELECT COUNT(*) AS N FROM DOCUMENTS WHERE TITLE = ?",
            (f"Reliability duplicate check {marker}",),
        )[0]["n"]
    results["duplicate_upload"] = {
        "passed": (
            first_upload["document_id"] == second_upload["document_id"]
            and second_upload["already_existed"] is True
            and int(count) == 1
        ),
        "first_id": first_upload["document_id"],
        "second_id": second_upload["document_id"],
        "already_existed": second_upload["already_existed"],
        "rows": int(count),
    }
    with transaction() as connection:
        execute(connection, "DELETE FROM DOCUMENTS WHERE DOCUMENT_ID = ?", (first_upload["document_id"],))

    # 5. Transaction rollback on an invalid foreign key.
    rollback_marker = f"rollback-check-{time.time_ns()}"
    orphans = -1
    try:
        with transaction() as connection:
            insert_returning_id(
                connection,
                (
                    "INSERT INTO DOCUMENTS (TITLE, FILENAME, CONTENT_HASH, SOURCE_TYPE, PROCESSING_STATUS) "
                    "VALUES (?, ?, ?, 'text', 'READY')"
                ),
                (rollback_marker, "rollback.txt", "0" * 64),
            )
            # Force a failure after the document insert; the transaction must roll
            # back the document as well as the invalid passage.
            insert_returning_id(
                connection,
                "INSERT INTO PASSAGES (DOCUMENT_ID, PASSAGE_TEXT, PAGE_NUMBER, PASSAGE_INDEX) VALUES (?, ?, ?, ?)",
                (999999999, "orphan", 1, 0),
            )
        rollback_passed = False
    except DatabaseOperationError:
        with transaction() as connection:
            rows = query_all(
                connection,
                "SELECT COUNT(*) AS N FROM DOCUMENTS WHERE TITLE = ?",
                (rollback_marker,),
            )
            orphans = query_all(
                connection,
                "SELECT COUNT(*) AS N FROM PASSAGES WHERE DOCUMENT_ID = 999999999",
            )[0]["n"]
        rollback_passed = int(rows[0]["n"]) == 0 and int(orphans) == 0
    results["transaction_rollback"] = {"passed": rollback_passed, "orphan_passages": int(orphans)}
    with transaction() as connection:
        execute(connection, "DELETE FROM DOCUMENTS WHERE TITLE = ?", (rollback_marker,))

    # 6. Failed session state.
    session_id = repository.create_session("failed session check", "test/model")
    repository.mark_session_failed(session_id, "simulated failure", 12)
    failed = repository.get_session(session_id)
    results["failed_session"] = {
        "passed": failed["status"] == "FAILED" and failed["error_message"] == "simulated failure",
        "status": failed["status"],
        "duration_ms": failed["duration_ms"],
    }
    with transaction() as connection:
        execute(connection, "DELETE FROM VERIFICATION_SESSIONS WHERE SESSION_ID = ?", (session_id,))

    # 7. Concurrent reads.
    started = time.monotonic()
    def read() -> bool:
        return bool(repository.get_document(121)) and len(repository.list_documents(limit=5)) >= 1

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda _: read(), range(16)))
    results["concurrent_reads"] = {
        "passed": all(outcomes),
        "requests": len(outcomes),
        "seconds": round(time.monotonic() - started, 3),
    }

    # 8. Connection failure behavior.
    broken = settings.model_copy(update={"db2_port": 59999})
    try:
        Db2Repository(broken).health()
        connection_failed = False
    except DatabaseUnavailableError:
        connection_failed = True
    results["connection_failure"] = {"passed": connection_failed, "raised_safe_error": connection_failed}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
