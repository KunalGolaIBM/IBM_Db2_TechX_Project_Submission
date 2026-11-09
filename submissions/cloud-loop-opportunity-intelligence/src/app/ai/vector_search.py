import math
from typing import List, Dict, Any, Tuple
from backend.app.ai.embeddings import generate_embedding
from backend.app.repositories.opportunity_repository import opportunity_repo

def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))

def semantic_search_opportunities(
    query: str,
    limit: int = 10,
    opp_type: str = None
) -> List[Tuple[Dict[str, Any], float]]:
    """
    Ranks opportunities by semantic similarity to user query.
    """
    if not query or not query.strip():
        items, _ = opportunity_repo.list_opportunities(opp_type=opp_type, limit=limit)
        return [(item, 1.0) for item in items]

    query_vec = generate_embedding(query)
    all_items, _ = opportunity_repo.list_opportunities(opp_type=opp_type, limit=250)

    scored = []
    for item in all_items:
        # Create rich semantic text representation
        skills_str = " ".join(item.get("skills") or [])
        doc_text = f"{item.get('title', '')} {item.get('organization', '')} {item.get('category', '')} {skills_str} {item.get('description', '')}"
        doc_vec = generate_embedding(doc_text)
        score = cosine_similarity(query_vec, doc_vec)
        scored.append((item, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]

