"""
Tests for vector embeddings and similarity search against Db2 AML typologies.
"""

import pytest
from src.db.connection import get_db_manager
from src.db.schema import initialize_schema
from src.db.seed_data import seed_database
from src.utils.embeddings import get_embedding_service


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    initialize_schema()
    seed_database(force=True)


def test_embedding_generation():
    service = get_embedding_service()
    vec = service.embed_text("Structuring multiple deposits below threshold")
    assert len(vec) == 384
    assert any(x != 0.0 for x in vec)


def test_cosine_similarity():
    service = get_embedding_service()
    v1 = service.embed_text("Money laundering structuring split cash")
    v2 = service.embed_text("Structuring cash deposits to evade CTR")
    v3 = service.embed_text("Completely unrelated baking recipe strawberry cake")

    sim_related = service.cosine_similarity(v1, v2)
    sim_unrelated = service.cosine_similarity(v1, v3)

    assert sim_related > sim_unrelated
    assert sim_related > 0.25


def test_vector_search_typologies():
    db = get_db_manager()
    service = get_embedding_service()
    query_vec = service.embed_text("Split invoices under $10,000 threshold to evade reporting")

    matches = db.vector_search_typologies(query_vec, top_k=2, min_similarity=0.25)
    assert len(matches) > 0
    top_match = matches[0]
    assert "STRUCTURING" in top_match["CODE"]
