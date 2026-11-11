import pytest
from app.schemas.opportunity import OpportunityBase, OpportunityResponse, OpportunityListResponse
from app.schemas.search import SemanticSearchRequest, SemanticSearchResponse
from app.schemas.match import MatchRequest, MatchResponse
from app.schemas.tracking import TrackRequest
from app.schemas.newsletter import NewsletterSubscribeRequest
from app.schemas.stats import DashboardStatsResponse

def test_opportunity_schema_normalization():
    raw = {
        "id": "adobe-test",
        "slug": "adobe-test",
        "title": "Software Engineer",
        "org": "Adobe",
        "kind": "job",
        "skills": "React, TypeScript, CSS",
        "apply_url": "https://adobe.com/careers"
    }
    opp = OpportunityResponse(**raw)
    assert opp.id == "adobe-test"
    assert opp.kind == "job"
    assert opp.skills == ["React", "TypeScript", "CSS"]
    assert opp.location == "India / Remote"

def test_semantic_search_request_schema():
    req = SemanticSearchRequest(query="machine learning internship", kind="internship", top_k=5)
    assert req.query == "machine learning internship"
    assert req.kind == "internship"
    assert req.top_k == 5

def test_match_request_schema():
    req = MatchRequest(skills=["Python", "SQL", "Docker"], interests=["Cloud", "Backend"], year="2026")
    assert "Python" in req.skills
    assert req.year == "2026"
    assert req.limit == 6

def test_track_request_schema():
    req = TrackRequest(user_id="user_123", opportunity_id="adobe-test", status="Applied", bookmarked=True)
    assert req.status == "Applied"
    assert req.bookmarked is True

def test_newsletter_request_schema():
    req = NewsletterSubscribeRequest(email="student@university.edu")
    assert req.email == "student@university.edu"

    with pytest.raises(Exception):
        NewsletterSubscribeRequest(email="not-an-email")
