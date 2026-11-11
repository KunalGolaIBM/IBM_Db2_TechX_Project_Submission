import time
from fastapi.testclient import TestClient
from main import app
from app.core.config import settings

client = TestClient(app)

def test_ingestion_unauthorized():
    response = client.post("/api/v1/ingestion", json={"source": "test", "items": []})
    assert response.status_code == 422 or response.status_code == 403

def test_ingestion_valid_key():
    headers = {"X-Admin-Key": settings.ADMIN_API_KEY}
    unique_id = f"test-opp-{int(time.time() * 1000)}"
    payload = {
        "source": "UnitTest Provider",
        "items": [
            {
                "id": unique_id,
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
    assert (data["inserted"] + data["updated"]) >= 1

