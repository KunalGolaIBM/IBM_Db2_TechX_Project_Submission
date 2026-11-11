"""Make the `backend` package importable when running `pytest tests/` from the submission root."""
import os
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

# Tests always run against an isolated, auto-seeded SQLite file unless a mode is set explicitly.
os.environ.setdefault("DATABASE_MODE", "sqlite")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{SRC_DIR / 'test_neighbourhood_safety.db'}")
