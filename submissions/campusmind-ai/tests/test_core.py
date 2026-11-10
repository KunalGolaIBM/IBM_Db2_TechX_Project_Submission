import unittest

from campusmind.main import extractive_answer
from campusmind.retrieval import CampusMindRetriever


class TestCampusMind(unittest.TestCase):

    def setUp(self):
        self.retriever = CampusMindRetriever()

    def test_primary_key_answer(self):
        passage = (
            "A primary key is a field that uniquely identifies each record. "
            "It cannot contain duplicate or NULL values."
        )
        answer = extractive_answer("What is a primary key?", passage)
        self.assertIn("uniquely identifies each record", answer)

    def test_foreign_key_answer(self):
        passage = (
            "A foreign key is a field in one table that refers to the "
            "primary key in another table. It establishes a relationship."
        )
        answer = extractive_answer("Explain foreign key", passage)
        self.assertIn("refers to the primary key", answer)

    def test_primary_key_retrieval_ranking(self):
        self.retriever.add_chunks("dbms.pdf", [
            {"page": 1, "text": "A primary key is a field that uniquely identifies each record."},
            {"page": 2, "text": "A foreign key refers to the primary key in another table."},
            {"page": 3, "text": "Revision question: What is a primary key? Explain its importance."}
        ])
        results = self.retriever.search("What is a primary key?")
        self.assertEqual(results[0].meta["page"], 1)

    def test_foreign_key_retrieval_ranking(self):
        self.retriever.add_chunks("dbms.pdf", [
            {"page": 1, "text": "A primary key uniquely identifies each row."},
            {"page": 2, "text": "A foreign key references a key in another table and maintains referential integrity."},
            {"page": 3, "text": "Quick revision question: Explain foreign key."}
        ])
        results = self.retriever.search("Explain foreign key")
        self.assertEqual(results[0].meta["page"], 2)

    def test_duplicate_document_upload(self):
        chunks = [
            {"page": 1, "text": "A primary key uniquely identifies each record."}
        ]
        self.retriever.add_chunks("dbms.pdf", chunks)
        self.retriever.add_chunks("dbms.pdf", chunks)
        results = self.retriever.search("What is a primary key?")
        self.assertTrue(results)
        self.assertEqual(results[0].meta["filename"], "dbms.pdf")

    def test_source_metadata(self):
        self.retriever.add_chunks("dbms.pdf", [
            {"page": 4, "text": "A primary key uniquely identifies each record."}
        ])
        results = self.retriever.search("What is a primary key?")
        self.assertTrue(results)
        self.assertEqual(results[0].meta["filename"], "dbms.pdf")
        self.assertEqual(results[0].meta["page"], 4)
        self.assertIn("bm25_score", results[0].meta)
        self.assertIn("combined_relevance_score", results[0].meta)


if __name__ == "__main__":
    unittest.main()
