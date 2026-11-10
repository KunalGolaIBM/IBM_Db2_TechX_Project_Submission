"""Create every Db2 object PortProof needs.

Run once:  ``python -m src.setup_db``

The scripts in ``sql/`` are applied by the schema owner. The WLM leash needs
WLMADM, so it is applied on a best-effort basis and PortProof works without it.
"""
from __future__ import annotations

import sys
from pathlib import Path

from . import db
from .config import setup_config

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"

#: ``(filename, required)`` -- a non-required script may fail without stopping setup.
#: The DB2VS fix-memory table is created between the two groups, because
#: ``03_grants.sql`` grants on it.
SCRIPTS_BEFORE_VECTOR: list[tuple[str, bool]] = [
    ("01_schema.sql", True),
    ("02_procedures.sql", True),
]
SCRIPTS_AFTER_VECTOR: list[tuple[str, bool]] = [
    ("03_grants.sql", True),
    ("04_wlm_leash.sql", False),
]

#: DROP statements are expected to fail the first time a database is set up.
_IGNORABLE_ON_DROP = {-204, -205, -206, -478, -575}


def _leading_keyword(statement: str) -> str:
    """The statement's first SQL word, ignoring any leading comment lines."""
    for line in statement.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("--"):
            return stripped.split(None, 1)[0].upper()
    return ""


def _apply(conn, path: Path, required: bool) -> tuple[int, int, list[str]]:
    applied = skipped = 0
    problems: list[str] = []
    for statement in db.split_script(path.read_text(encoding="utf-8")):
        first_word = _leading_keyword(statement)
        try:
            db.execute(conn, statement)
            applied += 1
        except db.Db2Error as exc:
            benign_drop = first_word == "DROP" and exc.sqlcode in _IGNORABLE_ON_DROP
            already_there = exc.sqlcode in (-601,)  # object already exists
            if benign_drop or already_there:
                skipped += 1
                continue
            label = " ".join(statement.split())[:90]
            problems.append(f"SQLCODE={exc.sqlcode} on [{label}]: {exc.message[:160]}")
            if required:
                raise
    return applied, skipped, problems


def main(argv: list[str] | None = None) -> int:
    cfg = setup_config()
    print(f"PortProof setup -> {cfg.redacted()}")

    try:
        conn = db.connect(cfg, role="setup")
    except db.Db2Error as exc:
        print(f"  FAILED to connect: {exc}", file=sys.stderr)
        print(
            "  Is Db2 running? Try: docker ps | grep db2   "
            "and check DB2_* values in your .env",
            file=sys.stderr,
        )
        return 2

    try:
        user, _ = db.current_identity(conn)
        db.execute(conn, f"SET CURRENT SCHEMA {cfg.schema}")
        print(f"  connected as {user} (schema set to {cfg.schema}) on Db2 {db.server_version(conn)}")

        def run_group(group: list[tuple[str, bool]]) -> int | None:
            for filename, required in group:
                path = SQL_DIR / filename
                if not path.is_file():
                    print(f"  !! missing {path}")
                    return 2
                try:
                    applied, skipped, problems = _apply(conn, path, required)
                except db.Db2Error as exc:
                    print(f"  {filename}: FAILED -- {exc.message[:200]}", file=sys.stderr)
                    return 1
                state = "ok" if not problems else "ok with notes"
                print(f"  {filename}: {applied} applied, {skipped} skipped ({state})")
                for problem in problems:
                    print(f"     {'!' if required else '-'} {problem}")
                if problems and not required:
                    print("     (optional script: PortProof runs without it)")
            return None

        failure = run_group(SCRIPTS_BEFORE_VECTOR)
        if failure is not None:
            return failure

        # The official LangChain integration creates its own table.
        from .embeddings import LocalEmbeddings
        from .fixmemory import ensure_table, ensure_vector_index

        print("  fix memory: creating FIX_MEMORY via langchain-db2 DB2VS ...")
        shape = ensure_table(conn, embeddings=LocalEmbeddings())
        print(f"    FIX_MEMORY columns: {shape}")
        # Only the embedding column had an index before this: the table's PK.
        # Every recall therefore distanced every row, while the engine has had
        # an approximate vector index since 12.1.
        print(f"    {ensure_vector_index(conn)}")

        failure = run_group(SCRIPTS_AFTER_VECTOR)
        if failure is not None:
            return failure

        _report(conn, cfg.schema)
    finally:
        try:
            import ibm_db

            ibm_db.close(conn)
        except Exception:  # pragma: no cover
            pass

    print("\nSetup complete. Next: python -m src.seed")
    return 0


def _report(conn, schema: str) -> None:
    tables = db.fetch_all(
        conn,
        "SELECT TABNAME, TYPE FROM SYSCAT.TABLES WHERE TABSCHEMA = ? ORDER BY TABNAME",
        (schema,),
    )
    routines = db.fetch_all(
        conn,
        "SELECT ROUTINENAME FROM SYSCAT.ROUTINES WHERE ROUTINESCHEMA = ? ORDER BY ROUTINENAME",
        (schema,),
    )
    indexes = db.fetch_all(
        conn,
        "SELECT INDNAME FROM SYSCAT.INDEXES WHERE INDSCHEMA = ? ORDER BY INDNAME",
        (schema,),
    )
    print(f"\n  objects in {schema}:")
    print("    tables   : " + ", ".join(f"{t.strip()}({k})" for t, k in tables))
    print("    routines : " + ", ".join(r[0].strip() for r in routines))
    print("    indexes  : " + ", ".join(i[0].strip() for i in indexes))


if __name__ == "__main__":
    raise SystemExit(main())
