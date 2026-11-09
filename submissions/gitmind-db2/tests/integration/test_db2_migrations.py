"""
Integration tests for IBM Db2 Schema Migrations and Relational Structure
"""

import unittest
from data.db2.migrations import ALL_MIGRATIONS, SchemaMigrationManager


class TestDb2Migrations(unittest.TestCase):

    def test_migration_sequence_valid(self):
        ids = [m.migration_id for m in ALL_MIGRATIONS]
        self.assertEqual(ids, ["001_core_schema", "002_agent_memory_and_findings", "003_audit_trail", "004_vector_store"])

    def test_migration_sqls_contain_mandatory_tables(self):
        all_sqls = []
        for m in ALL_MIGRATIONS:
            all_sqls.extend(m.up_sqls)
        combined = "\n".join(all_sqls).upper()

        # Phase Two required tables:
        self.assertIn("GITMIND_REPOSITORIES", combined)
        self.assertIn("GITMIND_ARTIFACTS", combined)
        self.assertIn("GITMIND_RELATIONS", combined)
        self.assertIn("GITMIND_INDEX_RUNS", combined)
        self.assertIn("GITMIND_AGENT_RUNS", combined)
        self.assertIn("GITMIND_FINDINGS", combined)
        self.assertIn("GITMIND_FINDING_EVIDENCE", combined)
        self.assertIn("GITMIND_AUDIT_EVENTS", combined)
        self.assertIn("GITMIND_VECTORS", combined)

        # Knowledge Graph relations
        self.assertIn("RELATION_TYPE", combined)
        self.assertIn("SOURCE_ARTIFACT_ID", combined)
        self.assertIn("TARGET_ARTIFACT_ID", combined)
        self.assertIn("FOREIGN KEY", combined)
        self.assertIn("ON DELETE CASCADE", combined)


if __name__ == "__main__":
    unittest.main()
