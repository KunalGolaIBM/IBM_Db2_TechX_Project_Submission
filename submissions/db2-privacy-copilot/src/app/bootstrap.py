"""Database bootstrap: version check, run SQL files, verify tables exist.

Run after starting the Db2 container and before seeding data.
Self-contained on purpose: it does not use app.db.run_sql_file, whose splitter
dropped statements that were preceded by '--' comments.
"""
import pathlib
import re
import sys

SQL_FILES = [
    "sql/00_schema_clinic.sql",
    "sql/01_app_tables.sql",
    "sql/02_consent_temporal.sql",
]

REQUIRED_TABLES = {
    "PATIENT", "APPOINTMENT", "BILLING", "PRESCRIPTION", "LAB_REPORT",
    "SUPPORT_TICKET", "MARKETING_LIST", "REQUESTS", "AUDIT_LOG",
    "CONSENT", "CONSENT_HISTORY",
}

# SQL0601N: object already exists. Safe to skip so bootstrap can be re-run.
ALREADY_EXISTS = {-601}

MIN_VECTOR_VERSION = (12, 1, 2)


def split_sql(text: str) -> list[str]:
    """Split SQL statements while respecting quoted strings and comments."""
    statements: list[str] = []
    buf: list[str] = []
    i, n = 0, len(text)
    in_str = False

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if in_str:
            buf.append(ch)
            if ch == "'":
                if nxt == "'":
                    buf.append(nxt)
                    i += 1
                else:
                    in_str = False
        elif ch == "'":
            in_str = True
            buf.append(ch)
        elif ch == "-" and nxt == "-":
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif ch == "/" and nxt == "*":
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
            buf.append(" ")
            continue
        elif ch == ";":
            statement = "".join(buf).strip()
            if statement:
                statements.append(statement)
            buf = []
        else:
            buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def parse_version(service_level: str) -> tuple[int, int, int] | None:
    m = re.search(r"v?(\d+)\.(\d+)\.(\d+)", service_level)
    return tuple(int(x) for x in m.groups()) if m else None


def sqlcode_of(err: Exception) -> int | None:
    m = re.search(r"SQLCODE=(-?\d+)", str(err))
    return int(m.group(1)) if m else None


def _connect():
    """Open a Db2 connection using whatever helper app/db.py provides."""
    import app.db as db
    for name in ("conn", "get_connection", "get_conn", "connect", "get_db_connection"):
        fn = getattr(db, name, None)
        if callable(fn):
            return fn()
    raise SystemExit(
        "Could not find a connection function in app/db.py "
        "(looked for conn, get_connection, get_conn, connect, get_db_connection)."
    )


def check_version(c) -> None:
    cur = c.cursor()
    cur.execute("SELECT SERVICE_LEVEL FROM SYSIBMADM.ENV_INST_INFO")
    level = cur.fetchone()[0]
    ver = parse_version(level)
    print(f"   Db2 version: {level}")
    if ver is None:
        print("   WARNING: could not parse the Db2 version")
    elif ver < MIN_VECTOR_VERSION:
        print("   WARNING: vector support needs Db2 12.1.2 or later")
    else:
        print("   OK: vector support available")


def run_file(c, path: str) -> None:
    statements = split_sql(pathlib.Path(path).read_text(encoding="utf-8"))
    print(f"   {len(statements)} statements")
    for i, stmt in enumerate(statements, 1):
        preview = " ".join(stmt.split())[:70]
        try:
            c.cursor().execute(stmt)
            c.commit()
            print(f"   ok   #{i}: {preview}")
        except Exception as e:  # ibm_db_dbi raises several error types
            c.rollback()
            if sqlcode_of(e) in ALREADY_EXISTS:
                print(f"   skip #{i} (already exists): {preview}")
                continue
            print(f"\nBOOTSTRAP FAILED in {path}, statement #{i}:\n  {preview}\n  {e}")
            sys.exit(1)


def verify_tables(c) -> None:
    cur = c.cursor()
    cur.execute("SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = CURRENT SCHEMA")
    present = {row[0] for row in cur.fetchall()}
    missing = REQUIRED_TABLES - present
    if missing:
        print(f"\nBOOTSTRAP FAILED: missing tables after bootstrap: {sorted(missing)}")
        sys.exit(1)
    print(f"   All {len(REQUIRED_TABLES)} required tables present")


def main() -> None:
    print("=" * 60)
    print("Db2 Privacy Copilot - Database Bootstrap")
    print("=" * 60)

    c = _connect()
    try:
        print("\n1. Checking Db2 version...")
        check_version(c)

        for n, path in enumerate(SQL_FILES, start=2):
            print(f"\n{n}. Executing {path}...")
            run_file(c, path)
            print("   Completed")

        print(f"\n{len(SQL_FILES) + 2}. Verifying tables...")
        verify_tables(c)
    finally:
        c.close()

    print("\n" + "=" * 60)
    print("Bootstrap complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Run: python eval/seed.py")
    print("  2. Run: pytest")
    print("  3. Start API: uvicorn app.api:app --reload")
    print()


if __name__ == "__main__":
    main()
