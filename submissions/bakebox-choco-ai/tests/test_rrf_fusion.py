"""
Module: tests/test_rrf_fusion.py
Comprehensive Offline Tests for 3-Way Reciprocal Rank Fusion (Dense + BM25 + TF-IDF).
Validates mathematical formula precision, channel dominance, tie-breaking, and boundary limits.
Zero external network or database dependencies.
"""
import os
import sys
import unittest

_pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from src.retriever import compute_rrf_score, SimpleBM25

class TestRRFFusion(unittest.TestCase):
    def test_01_rrf_top_rank_formula(self):
        """Test RRF score formula: RRF(d) = sum(1 / (k + rank + 1)) for k=60 at rank 0."""
        score = compute_rrf_score([0, 0, 0], k=60)
        expected = 3 * (1.0 / 61.0)
        self.assertAlmostEqual(score, expected, places=5)

    def test_02_rrf_single_channel_score(self):
        """Test RRF score when document appears in only one channel."""
        score = compute_rrf_score([0, None, None], k=60)
        expected = 1.0 / 61.0
        self.assertAlmostEqual(score, expected, places=5)

    def test_03_rrf_decay_with_increasing_rank(self):
        """Verify score monotonically decreases as rank increases."""
        score_rank_0 = compute_rrf_score([0], k=60)
        score_rank_1 = compute_rrf_score([1], k=60)
        score_rank_5 = compute_rrf_score([5], k=60)
        self.assertGreater(score_rank_0, score_rank_1)
        self.assertGreater(score_rank_1, score_rank_5)

    def test_04_dense_and_lexical_fusion_superiority(self):
        """Multi-channel agreement (dense + BM25) strictly outscores single channel."""
        score_single = compute_rrf_score([0, None, None], k=60)
        score_multi = compute_rrf_score([2, 1, None], k=60)
        self.assertGreater(score_multi, score_single)

    def test_05_rrf_empty_channels(self):
        """Verify empty or all-None channel input returns 0.0."""
        self.assertEqual(compute_rrf_score([]), 0.0)
        self.assertEqual(compute_rrf_score([None, None, None]), 0.0)

    def test_06_rrf_custom_k_parameter(self):
        """Verify configurable k parameter shifts rank sensitivity."""
        score_k60 = compute_rrf_score([0], k=60)
        score_k10 = compute_rrf_score([0], k=10)
        self.assertAlmostEqual(score_k60, 1.0 / 61.0, places=5)
        self.assertAlmostEqual(score_k10, 1.0 / 11.0, places=5)
        self.assertGreater(score_k10, score_k60)

    def test_07_bm25_exact_term_matching(self):
        """Okapi BM25 accurately ranks documents matching salient search tokens."""
        corpus = [
            "Pure veg eggless red velvet with cream cheese",
            "Classic pineapple fruit glaze cake",
            "Dark chocolate Belgian gateau"
        ]
        bm25 = SimpleBM25(corpus)
        scores = bm25.score("eggless red velvet")
        self.assertGreater(scores[0], scores[1])
        self.assertGreater(scores[0], scores[2])

    def test_08_bm25_empty_query_handling(self):
        """BM25 returns zero scores gracefully for queries with no matching terms."""
        corpus = ["Fresh pineapple cake", "Black forest gateau"]
        bm25 = SimpleBM25(corpus)
        scores = bm25.score("xyznonexistentterm123")
        self.assertEqual(scores, [0.0, 0.0])

    def test_09_bm25_term_frequency_saturation(self):
        """Verify Okapi BM25 term frequency saturation behavior."""
        corpus = [
            "chocolate cake",
            "chocolate chocolate chocolate chocolate chocolate cake"
        ]
        bm25 = SimpleBM25(corpus)
        scores = bm25.score("chocolate")
        # Due to length normalization and saturation, doc 1 should not score 5x doc 0
        ratio = scores[1] / (scores[0] or 1e-6)
        self.assertLess(ratio, 3.0)

    def test_10_tie_breaking_consistency(self):
        """Identical rank profiles produce identical deterministic scores."""
        score_a = compute_rrf_score([1, 2, 3], k=60)
        score_b = compute_rrf_score([1, 2, 3], k=60)
        self.assertEqual(score_a, score_b)


if __name__ == "__main__":
    unittest.main()
