"""Create the demo schema and deterministic sample data in IBM Db2."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.database.initialization import initialize_database

if __name__ == "__main__":
    try:
        counts = initialize_database()
        print("Db2Ops AI schema ready. Records:")
        for table, count in counts.items():
            print(f"  {table}: {count}")
    except Exception as exc:
        print(f"Database setup failed ({type(exc).__name__}). Check the local Db2 connection settings and server status.")
        raise SystemExit(1)
