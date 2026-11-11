import math
import unittest
from pathlib import Path

from shipsafe.knowledge import HashingEmbeddings, parse_policy_file

POLICIES = Path(__file__).resolve().parents[1] / "policies"


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))


class TestKnowledge(unittest.TestCase):
    def test_embeddings_are_deterministic_and_normalised(self):
        emb = HashingEmbeddings(dimension=384)
        v1 = emb.embed_query("parameterized SQL in IBM Db2")
        v2 = emb.embed_query("parameterized SQL in IBM Db2")
        self.assertEqual(v1, v2)
        self.assertEqual(len(v1), 384)
        self.assertAlmostEqual(math.sqrt(sum(x * x for x in v1)), 1.0, places=6)

    def test_related_text_is_closer_than_unrelated(self):
        emb = HashingEmbeddings()
        q = emb.embed_query("SQL injection from an f-string query")
        sql_doc = emb.embed_query("Every SQL statement must use parameter markers to prevent SQL injection")
        dep_doc = emb.embed_query("PyYAML must be upgraded to fix a known CVE")
        self.assertGreater(cosine(q, sql_doc), cosine(q, dep_doc))

    def test_policy_files_have_front_matter(self):
        files = sorted(POLICIES.glob("*.md"))
        self.assertGreaterEqual(len(files), 5)
        ids = {parse_policy_file(f)["doc_id"] for f in files}
        self.assertIn("POL-DB2-001", ids)


if __name__ == "__main__":
    unittest.main()
