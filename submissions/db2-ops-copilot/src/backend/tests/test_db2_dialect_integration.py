"""Integration: ibm_db_sa dialect + native ibm_db driver loading.

Opt-in only (marker contract in pyproject.toml, gate in conftest.py): skipped
unless ``ADAPTER_MODE=real`` AND ``RUN_REAL_INTEGRATION=1``. When enabled, a
missing or blocked native driver FAILS this test - a driver that cannot load
is never reported as a successful integration.

Scope: ``create_engine`` loads the dialect and the DBAPI module only; it
opens NO Db2 connection. This proves nothing about a live server.
"""

from __future__ import annotations

import pytest

from db2_fakes import real_settings


@pytest.mark.integration
def test_ibm_db_sa_dialect_loads_with_native_driver():
    from sqlalchemy import create_engine

    from app.database.dsn import sqlalchemy_url

    url = sqlalchemy_url(real_settings())
    try:
        engine = create_engine(url)
    except Exception as exc:  # noqa: BLE001 - any load failure must fail loudly
        raise AssertionError(
            "ibm_db_sa dialect / native ibm_db driver failed to load - "
            f"integration NOT verified: {type(exc).__name__}: {exc}"
        ) from exc
    try:
        assert engine.dialect.name == "ibm_db_sa"
    finally:
        engine.dispose()
