from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_list_opportunities():
    response = client.get("/api/v1/opportunities?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert len(data["items"]) <= 5

def test_filter_opportunities_by_type():
    response = client.get("/api/v1/opportunities?type=job&limit=3")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["opportunity_type"].lower() == "job"

def test_get_nonexistent_opportunity():
    response = client.get("/api/v1/opportunities/non-existent-opportunity-id-999")
    assert response.status_code == 404

