import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(scope="session", autouse=True)
def fresh_db():
    """Every test run starts from a freshly seeded Db2 (real database, no mocks)."""
    import seed
    seed.main()
    yield
