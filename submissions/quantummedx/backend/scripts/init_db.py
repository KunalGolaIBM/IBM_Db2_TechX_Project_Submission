"""Create the QuantumMedX schema in IBM Db2. Safe to re-run (existing tables are skipped)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.database.db2 import Db2Pool  # noqa: E402

SCHEMA = pathlib.Path(__file__).resolve().parents[2] / "database" / "schema" / "001_schema.sql"


def main() -> None:
    pool = Db2Pool()
    statements = [s.strip() for s in SCHEMA.read_text().split("\n;;\n") if s.strip()]
    created = skipped = 0
    for stmt in statements:
        try:
            pool.execute(stmt)
            created += 1
        except Exception as exc:  # Db2 SQL0601N / SQL0605W = object already exists
            if "SQL0601N" in str(exc) or "SQL0605W" in str(exc):
                skipped += 1
            else:
                raise
    print(f"Schema ready: {created} statement(s) applied, {skipped} already existed.")


if __name__ == "__main__":
    main()
