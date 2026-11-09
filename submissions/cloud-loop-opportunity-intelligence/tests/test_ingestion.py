from fastapi.testclient import TestClient
from backend.main import app
from backend.app.core.config import settings

client = TestClient(app)

def test_ingestion_unauthorized():
    response = client.post("/api/v1/ingestion", json={"source": "test", "items": []})
    assert response.status_code == 422 or response.status_code == 403

def test_ingestion_valid_key():
    headers = {"X-Admin-Key": settings.ADMIN_API_KEY}
    payload = {
        "source": "UnitTest Provider",
        "items": [
            {
                "id": "test-opp-101",
                "title": "Cloud Computing Fellowship",
                "organization": "IBM Cloud Academy",
                "opportunity_type": "program",
                "category": "Cloud",
                "application_url": "https://ibm.com/training",
                "deadline": "2027-01-01"
            }
        ]
    }
    response = client.post("/api/v1/ingestion", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["inserted"] >= 1

