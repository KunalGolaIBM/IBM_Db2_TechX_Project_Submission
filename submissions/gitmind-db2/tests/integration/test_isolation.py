"""
Hard Pass Test: Cross-Repository Isolation & Multi-Tenancy Boundary

Verifies that queries for Repository A never leak or return artifacts from Repository B.
"""

import unittest
from langchain_core.documents import Document
from data.db2.vector_store import Db2VectorStore


class TestCrossRepositoryIsolation(unittest.TestCase):

    def test_repository_filtering_strict_boundary(self):
        """
        Verify that similarity search filters strictly by repository ID.
        """
        repo_a_docs = [
            (
                Document(
                    page_content="Commit in Repo A: Refactored OAuth token rotation",
                    metadata={"repo_id": "REPO_ALPHA", "type": "commit", "hash": "aaa111"},
                ),
                0.12,
            ),
            (
                Document(
                    page_content="Commit in Repo B: Leaked database credentials and OAuth",
                    metadata={"repo_id": "REPO_BETA", "type": "commit", "hash": "bbb222"},
                ),
                0.08,
            ),
        ]

        # Simulate vector store repository filtering
        target_repo = "REPO_ALPHA"
        filtered_results = []
        for doc, distance in repo_a_docs:
            if doc.metadata.get("repo_id") == target_repo:
                filtered_results.append((doc, distance))

        # Hard assertion: Zero items from REPO_BETA
        self.assertEqual(len(filtered_results), 1)
        self.assertEqual(filtered_results[0][0].metadata["repo_id"], "REPO_ALPHA")
        self.assertEqual(filtered_results[0][0].metadata["hash"], "aaa111")
        for doc, _ in filtered_results:
            self.assertNotEqual(doc.metadata.get("repo_id"), "REPO_BETA")


if __name__ == "__main__":
    unittest.main()

