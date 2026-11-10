"""
Vector retrieval module for policy documents using Db2 VECTOR_DISTANCE and fastembed.
"""
import os
import sys
from typing import List, Dict, Any
from fastembed import TextEmbedding

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db import get_connection, execute_query
import ibm_db

# Singleton embedding model
_EMBED_MODEL = None


def get_embed_model():
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        _EMBED_MODEL = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _EMBED_MODEL


def retrieve_policies(query_text: str, top_k: int = 2) -> List[Dict[str, Any]]:
    """
    Embed the query text and retrieve the closest policy documents from Db2
    using native VECTOR_DISTANCE with COSINE metric.
    """
    model = get_embed_model()
    embeddings = list(model.embed([query_text]))
    query_vec = [round(float(x), 6) for x in embeddings[0].tolist()]
    vec_str = str(query_vec)

    sql = f"""
    SELECT 
        policy_id,
        policy_title,
        category,
        content,
        VECTOR_DISTANCE(embedding, VECTOR('{vec_str}', 384, FLOAT32), COSINE) AS distance
    FROM POLICIES
    ORDER BY distance ASC
    FETCH FIRST {top_k} ROWS ONLY
    """

    conn = get_connection()
    try:
        results = execute_query(conn, sql)
        # Convert distance to similarity score: similarity = 1 - distance
        for r in results:
            dist = float(r.get("distance", 1.0))
            r["score"] = round(1.0 - dist, 4)
            r["distance"] = round(dist, 4)
        return results
    finally:
        ibm_db.close(conn)


if __name__ == "__main__":
    test_queries = [
        "Customer wants refund on opened headphones after 20 days",
        "Gold member asking for instant refund under 100 dollars",
        "Coffee arrived spoiled and crushed box",
    ]
    for q in test_queries:
        print(f"\nQuery: {q}")
        hits = retrieve_policies(q, top_k=2)
        for h in hits:
            print(f"  [{h['score']:.4f}] Policy #{h['policy_id']}: {h['policy_title']}")

