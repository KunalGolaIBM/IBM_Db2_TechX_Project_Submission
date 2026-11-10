"""Run the real IBM Db2 connectivity smoke query."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.database.connection import test_connection

if __name__ == "__main__":
    try:
        print(test_connection())
    except Exception as exc:
        print(f"Db2 connection failed ({type(exc).__name__}). Check the local Db2 connection settings and server status.")
        raise SystemExit(1)
