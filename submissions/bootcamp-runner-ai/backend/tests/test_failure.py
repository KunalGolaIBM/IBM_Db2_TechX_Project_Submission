import pytest

from backend.db import DatabaseUnavailable, Db2Client


def test_missing_db2_is_explicitly_offline():
    with pytest.raises(DatabaseUnavailable):
        Db2Client(None).connect()
