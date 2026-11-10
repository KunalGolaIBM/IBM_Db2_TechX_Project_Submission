from types import SimpleNamespace
import sys
from unittest.mock import patch
import pytest
from src.database.connection import DatabaseUnavailable, connect, query_dataframe


def test_connection_failure_is_sanitized():
    fake = SimpleNamespace(connect=lambda *_: False)
    with patch.dict(sys.modules, {"ibm_db": fake}):
        with pytest.raises(DatabaseUnavailable, match="rejected the connection"):
            connect()


def test_missing_driver_is_handled():
    with patch.dict("sys.modules", {"ibm_db": None}):
        with pytest.raises(DatabaseUnavailable):
            connect()


def test_empty_dataframe_result():
    pd = pytest.importorskip("pandas", reason="Pandas native modules are blocked by this machine's application-control policy", exc_type=ImportError)
    with patch("src.database.connection.connection") as mocked:
        fake = SimpleNamespace(prepare=lambda *_: object(), execute=lambda *_: True, num_fields=lambda *_: 1,
                               field_name=lambda *_: "N", fetch_tuple=lambda *_: False)
        with patch.dict(sys.modules, {"ibm_db": fake}):
            mocked.return_value.__enter__.return_value = object()
            frame, _ = query_dataframe("SELECT N FROM CUSTOMERS")
        assert isinstance(frame, pd.DataFrame)
        assert frame.empty
