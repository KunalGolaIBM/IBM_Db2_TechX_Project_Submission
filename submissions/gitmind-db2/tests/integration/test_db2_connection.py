"""
Integration tests for IBM Db2 Connection Manager, Version Parsing, and Capabilities
"""

import unittest
from data.db2.connection import Db2Capabilities, Db2ConnectionManager, parse_db2_version, sanitize_conn_str


class TestDb2Connection(unittest.TestCase):

    def test_parse_db2_version(self):
        # Db2 12.1.2
        self.assertEqual(parse_db2_version("12.01.0200"), (12, 1, 2))
        # Db2 12.1.5 (ANN Vector Index)
        self.assertEqual(parse_db2_version("12.01.0500"), (12, 1, 5))
        # Db2 11.5.8
        self.assertEqual(parse_db2_version("11.05.0800"), (11, 5, 8))
        # Short format
        self.assertEqual(parse_db2_version("12.1.2"), (12, 1, 2))

    def test_sanitize_connection_string(self):
        raw = "DATABASE=BLUDB;HOSTNAME=db2.cloud;PORT=50001;UID=db2admin;PWD=SuperSecretPassword123;"
        sanitized = sanitize_conn_str(raw)
        self.assertNotIn("SuperSecretPassword123", sanitized)
        self.assertIn("PWD=********", sanitized)

    def test_connection_args_for_db2vs(self):
        mgr = Db2ConnectionManager(
            database="TESTDB",
            host="myhost.ibm.com",
            port=50001,
            username="user1",
            password="pwd",
            ssl=True,
        )
        args = mgr.get_connection_args()
        self.assertEqual(args["database"], "TESTDB")
        self.assertEqual(args["host"], "myhost.ibm.com")
        self.assertEqual(args["port"], "50001")
        self.assertEqual(args["username"], "user1")
        self.assertTrue(args["security"])

    def test_capabilities_version_evaluation(self):
        caps = Db2Capabilities()
        caps.parsed_version = (12, 1, 2)
        major, minor, fix = caps.parsed_version
        caps.native_vector_supported = (major >= 13) or (major == 12 and (minor > 1 or (minor == 1 and fix >= 2)))
        caps.vector_index_supported = (major >= 13) or (major == 12 and (minor > 1 or (minor == 1 and fix >= 5)))

        self.assertTrue(caps.native_vector_supported)
        self.assertFalse(caps.vector_index_supported)

        # 12.1.5 supports both
        caps.parsed_version = (12, 1, 5)
        major, minor, fix = caps.parsed_version
        caps.native_vector_supported = (major >= 13) or (major == 12 and (minor > 1 or (minor == 1 and fix >= 2)))
        caps.vector_index_supported = (major >= 13) or (major == 12 and (minor > 1 or (minor == 1 and fix >= 5)))
        self.assertTrue(caps.native_vector_supported)
        self.assertTrue(caps.vector_index_supported)


if __name__ == "__main__":
    unittest.main()

