import unittest

from src.api import query_account_balance


class RecordingCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        return (100,)


class TestVulnerableService(unittest.TestCase):
    def test_account_query_uses_parameter_markers(self):
        # Fails on purpose: the fixture builds SQL with an f-string instead of '?' markers.
        cur = RecordingCursor()
        query_account_balance(cur, "ACC-1")
        sql, params = cur.calls[0]
        self.assertIn("?", sql)
        self.assertEqual(params, ("ACC-1",))


if __name__ == "__main__":
    unittest.main()
