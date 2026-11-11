import asyncio
import pytest
from app.services.match_service import match_service
from app.ai.vector_search import cosine_similarity
from app.ai.embeddings import generate_embedding

def test_cosine_similarity_properties():
    v1 = generate_embedding("python developer react nextjs")
    v2 = generate_embedding("python developer react nextjs")
    sim = cosine_similarity(v1, v2)
    assert round(sim, 3) == 1.0

    v3 = generate_embedding("completely unrelated medical biology term")
    sim_diff = cosine_similarity(v1, v3)
    assert sim_diff < 0.9

def test_deterministic_why_builder():
    why_1 = match_service._build_deterministic_why(
        opportunity_title="Frontend Engineer",
        opportunity_org="Adobe",
        matched_skills=["React"],
        user_skills=["React", "Node.js"],
        year="2026"
    )
    assert "React" in why_1
    assert "Adobe" in why_1

    why_multi = match_service._build_deterministic_why(
        opportunity_title="Cloud Engineer",
        opportunity_org="IBM",
        matched_skills=["Python", "SQL", "Docker"],
        user_skills=["Python", "SQL", "Docker", "Git"],
        year="2026"
    )
    assert "Python, SQL, Docker" in why_multi

def test_match_opportunities_execution():
    res = asyncio.run(
        match_service.match_opportunities(
            skills=["Python", "TypeScript", "React"],
            interests=["Full Stack", "Cloud"],
            year="2026",
            limit=3
        )
    )
    assert "matches" in res
    assert len(res["matches"]) <= 3
    for m in res["matches"]:
        assert 25.0 <= m["match_percentage"] <= 99.0
        assert len(m["why"]) > 0
        assert m["explanation_mode"] in ("llm", "deterministic")
