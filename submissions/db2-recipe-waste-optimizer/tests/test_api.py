"""Integration tests for FastAPI endpoints with live IBM Db2."""
from fastapi.testclient import TestClient
from recipe_waste_optimizer.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"]["status"] == "connected"
    assert data["database"]["dbms_name"] == "DB2/LINUXX8664"


def test_inventory_list_and_create():
    # 1. Fetch current inventory
    response = client.get("/api/v1/inventory")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)

    # 2. Add an item
    new_item = {
        "ingredient_name": "cucumber",
        "quantity": 2.0,
        "unit": "pieces",
        "storage_location": "fridge"
    }
    create_res = client.post("/api/v1/inventory", json=new_item)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["ingredient_name"] == "cucumber"
    assert created["quantity"] == 2.0


def test_recommendation_endpoint():
    req = {
        "message": "Quick dinner with greens and tomatoes",
        "servings": 2,
        "dietary_preferences": ["vegetarian"]
    }
    response = client.post("/api/v1/recipes/recommend", json=req)
    assert response.status_code == 200
    data = response.json()
    assert "top_candidates" in data
    assert len(data["top_candidates"]) > 0
    top = data["top_candidates"][0]
    assert "total_score" in top
    assert top["total_score"] > 0
    assert data["selected_recipe"] is not None
    assert data["selected_recipe"]["recipe_name"] != ""


def test_cooking_history_endpoint():
    response = client.get("/api/v1/history")
    assert response.status_code == 200
    data = response.json()
    assert "cooking_events" in data
    assert "event_summary" in data
    assert data["event_summary"]["consumed"] >= 1
