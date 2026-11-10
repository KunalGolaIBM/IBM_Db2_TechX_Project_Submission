"""
Unit tests for Db2 Vector Column & VECTOR_DISTANCE similarity retrieval.
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.policy_retriever import retrieve_policies


def test_vector_retrieval_policies():
    query = "Customer has a damaged box with broken screen"
    hits = retrieve_policies(query, top_k=2)
    assert len(hits) > 0, "Vector retrieval should return policy documents"
    assert "score" in hits[0], "Result should include similarity score"
    assert "distance" in hits[0], "Result should include distance metric"
    # Should rank Damaged policy high
    titles = [h["policy_title"] for h in hits]
    assert "Damaged, Defective, or Wrong Items" in titles or "Standard Return and Refund Window" in titles


if __name__ == "__main__":
    print("Running Vector Retrieval Unit Tests...")
    test_vector_retrieval_policies()
    print("✅ Vector search unit tests passed successfully!")

