from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_recommendations_endpoint():
    payload = {
        "user_id": "test_user_student_1",
        "limit": 4,
        "include_ai_explanation": True
    }
    response = client.post("/api/v1/recommendations", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "recommendations" in data
    assert len(data["recommendations"]) <= 4
    if data["recommendations"]:
        first = data["recommendations"][0]
        assert "match_score" in first
        assert "explanation" in first
        assert first["match_score"] >= 0.0

