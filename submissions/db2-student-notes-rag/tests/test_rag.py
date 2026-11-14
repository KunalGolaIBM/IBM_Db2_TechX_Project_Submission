"""
Automated Unit and Integration Tests for IBM Db2 Student Notes RAG.
Verifies chunking, metadata extraction, vector store operations,
and question-answering workflows.
"""

import sys
import unittest
from pathlib import Path

# Add src to path
src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))

from config import Db2RAGConfig
from chunker import StudentNotesChunker
from rag_engine import StudentNotesRAG
from db2_client import MockVectorStoreFallback, get_or_create_vector_store


class TestDb2StudentNotesRAG(unittest.TestCase):

    def setUp(self):
        self.chunker = StudentNotesChunker(chunk_size=400, chunk_overlap=80)
        self.sample_markdown = """# Wireless Communication Exam Notes

## 1. FRIIS TRANSMISSION EQUATION

The Friis Transmission Equation describes received power in free space:
$$P_r = P_t \\cdot G_t \\cdot G_r \\cdot \\left(\\frac{\\lambda}{4\\pi d}\\right)^2$$

Where $P_t$ is transmitted power in Watts, and $d$ is distance in meters.
In decibel form:
$$P_r(dBm) = P_t(dBm) + G_t(dB) + G_r(dB) - FSPL(dB)$$

## 2. DIVERSITY COMBINING

Selection combining chooses the branch with highest SNR.
Maximal Ratio Combining (MRC) weights all branches proportionally to SNR."""

    def test_01_config_connection_string(self):
        """Test Db2 connection string formatting."""
        conn_str = Db2RAGConfig.get_connection_string()
        self.assertIn("DATABASE=", conn_str)
        self.assertIn("HOSTNAME=", conn_str)
        self.assertIn("PORT=", conn_str)
        self.assertIn("PROTOCOL=", conn_str)

    def test_02_formula_detection(self):
        """Test formula and math pattern detection in notes."""
        math_text = "$$P_r = P_t \\cdot (\\lambda / 4\\pi d)^2$$ with 20 dB gain"
        prose_text = "This is a simple historical explanation of communications."
        self.assertTrue(StudentNotesChunker.detect_formulas(math_text))
        self.assertFalse(StudentNotesChunker.detect_formulas(prose_text))

    def test_03_chunker_processing(self):
        """Test header extraction and document chunk generation."""
        sections = StudentNotesChunker.extract_sections(self.sample_markdown)
        self.assertGreaterEqual(len(sections), 2)
        titles = [s["title"] for s in sections]
        self.assertIn("1. FRIIS TRANSMISSION EQUATION", titles)
        self.assertIn("2. DIVERSITY COMBINING", titles)

    def test_04_vector_store_similarity(self):
        """Test vector similarity search on mock/Db2 vector store."""
        sections = StudentNotesChunker.extract_sections(self.sample_markdown)
        from chunker import Document
        docs = [
            Document(page_content=s["content"], metadata={"section_title": s["title"], "topic": "Wireless"})
            for s in sections
        ]

        store = get_or_create_vector_store(documents=docs)
        results = store.similarity_search("How to calculate received power?", k=1)
        self.assertEqual(len(results), 1)
        self.assertIn("FRIIS", results[0].metadata.get("section_title", "").upper())

    def test_05_rag_engine_end_to_end(self):
        """Test end-to-end question answering pipeline."""
        from chunker import Document
        docs = [
            Document(
                page_content="Friis equation calculates received power Pr = Pt * Gt * Gr * (lambda / 4pi d)^2.",
                metadata={"section_title": "Friis Equation", "topic": "Propagation", "has_formula": True}
            )
        ]
        store = get_or_create_vector_store(documents=docs)
        rag = StudentNotesRAG(vector_store=store)
        res = rag.answer_question("What does Friis equation calculate?")

        self.assertIn("question", res)
        self.assertIn("answer", res)
        self.assertGreaterEqual(res["retrieved_count"], 1)
        self.assertTrue(len(res["sources"]) > 0)


if __name__ == "__main__":
    unittest.main()

