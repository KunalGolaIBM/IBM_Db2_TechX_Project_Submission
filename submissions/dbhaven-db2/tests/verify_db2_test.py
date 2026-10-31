#!/usr/bin/env python3
"""
Unit tests for IBM Db2 integration in dbhaven.
Zero external dependencies (uses standard library unittest).
"""

import unittest
import sys
import os

# Include python_client path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "python_client")))
from db2_backup_helper import parse_db2_dsn, format_db2_cli_backup

class TestDb2HavenIntegration(unittest.TestCase):
    def test_parse_valid_dsn(self):
        dsn = "db2://db2inst1:s3cr3t@10.0.0.5:50000/FINANCE"
        info = parse_db2_dsn(dsn)
        self.assertEqual(info["user"], "db2inst1")
        self.assertEqual(info["password"], "s3cr3t")
        self.assertEqual(info["host"], "10.0.0.5")
        self.assertEqual(info["port"], 50000)
        self.assertEqual(info["database"], "FINANCE")

    def test_parse_default_port(self):
        dsn = "db2://db2inst1:pass@localhost/SAMPLE"
        info = parse_db2_dsn(dsn)
        self.assertEqual(info["port"], 50000)
        self.assertEqual(info["database"], "SAMPLE")

    def test_invalid_scheme(self):
        with self.assertRaises(ValueError):
            parse_db2_dsn("postgres://user:pass@localhost:5432/db")

    def test_online_backup_command(self):
        info = {"database": "SAMPLE"}
        cmd = format_db2_cli_backup(info, "/var/backups", online=True)
        expected = ["db2", "-v", "backup database SAMPLE online to /var/backups"]
        self.assertEqual(cmd, expected)

    def test_offline_backup_command(self):
        info = {"database": "ANALYTICS"}
        cmd = format_db2_cli_backup(info, "/tmp/db2", online=False)
        expected = ["db2", "-v", "backup database ANALYTICS to /tmp/db2"]
        self.assertEqual(cmd, expected)

if __name__ == "__main__":
    unittest.main()
