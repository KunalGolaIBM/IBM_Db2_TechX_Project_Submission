from fastapi.testclient import TestClient
from main import app
from app.core.config import settings

client = TestClient(app)
AUTH_HEADERS = {"x-internal-key": settings.INTERNAL_API_KEY}

def test_health_check_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "db2" in data
    assert "haystack" in data

def test_opportunities_pagination():
    res = client.get("/api/v1/opportunities?page=1&limit=5", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "items" in data
    assert len(data["items"]) <= 5
    if data["items"]:
        first = data["items"][0]
        assert "id" in first
        assert "kind" in first
        assert "apply_url" in first

def test_semantic_search_endpoint():
    payload = {
        "query": "cloud computing software engineer",
        "top_k": 3
    }
    res = client.post("/api/v1/search/semantic", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "results" in data
    assert len(data["results"]) <= 3

def test_match_endpoint():
    payload = {
        "skills": ["React", "TypeScript", "Node.js"],
        "interests": ["Full Stack", "Web Development"],
        "year": "2026",
        "limit": 3
    }
    res = client.post("/api/v1/match", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "matches" in data
    assert len(data["matches"]) <= 3
    if data["matches"]:
        first = data["matches"][0]
        assert "why" in first
        assert "match_percentage" in first
        assert first["explanation_mode"] in ("llm", "deterministic")

def test_tracking_lifecycle():
    # 1. Update tracking
    track_payload = {
        "user_id": "test_student_user",
        "opportunity_id": "crud-operations-mongodb",
        "status": "Applied",
        "bookmarked": True
    }
    put_res = client.put("/api/v1/tracking", json=track_payload, headers=AUTH_HEADERS)
    assert put_res.status_code == 200
    assert put_res.json()["ok"] is True

    # 2. Retrieve tracking
    get_res = client.get("/api/v1/tracking?user_id=test_student_user", headers=AUTH_HEADERS)
    assert get_res.status_code == 200
    items = get_res.json()["items"]
    assert any(it["opportunity_id"] == "crud-operations-mongodb" for it in items)

def test_newsletter_subscription():
    payload = {"email": "evaluator@ibm.com"}
    res = client.post("/api/v1/newsletter", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 200
    assert res.json()["ok"] is True

def test_dashboard_stats():
    res = client.get("/api/v1/stats", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "counts_per_kind" in data
    assert "total_active" in data
    assert "closing_within_7_days" in data
