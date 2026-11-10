import os

import pytest

from civiclens.config import get_settings


@pytest.fixture(autouse=True)
def _fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def db2_enabled() -> bool:
    return os.getenv("CIVICLENS_DB2_TESTS") == "1"
