import json
import pytest
from app import create_app
from config import Config

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_index_page(client):
    """Test workspace main page loads successfully with developer interface."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "CodeFix" in html
    assert "Intelligent Coding Agent" in html
    assert "Write Code" in html
    assert "Debug Code" in html

def test_api_status(client):
    """Test system health and status API endpoint."""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "online"
    assert "model" in data
    assert "ollama_online" in data
    assert "db2_configured" in data

def test_generate_code_valid(client):
    """Test valid code generation request."""
    payload = {
        "mode": "write",
        "language": "python",
        "prompt": "Create a calculator that supports addition and subtraction."
    }
    response = client.post("/generate", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["mode"] == "write"
    assert data["language"] == "python"
    assert "generated_code" in data
    assert "explanation" in data
    assert "id" in data

def test_generate_code_missing_prompt(client):
    """Test validation rejection when prompt is empty or missing."""
    payload = {
        "mode": "write",
        "language": "python",
        "prompt": ""
    }
    response = client.post("/generate", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "Missing required parameter" in data["error"]

def test_generate_code_invalid_language(client):
    """Test validation rejection when an unsupported language is requested."""
    payload = {
        "mode": "write",
        "language": "unsupported_lang_xyz",
        "prompt": "Write hello world."
    }
    response = client.post("/generate", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "Unsupported language" in data["error"]

def test_analyze_code_validation(client):
    """Test validation for debug/analyze endpoint."""
    # Missing code should fail
    response = client.post("/analyze", json={"mode": "debug", "language": "python", "code": ""})
    assert response.status_code == 400

    # Valid code should succeed
    payload = {
        "mode": "debug",
        "language": "python",
        "code": "def test():\n    return 42",
        "error_message": "None"
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["mode"] == "debug"
    assert "diagnostics" in data

def test_analyze_code_static_ast_syntax_error(client):
    """Test analyze route reporting syntax error via static AST."""
    bad_code = "def broken(\n    return 123"
    payload = {
        "mode": "debug",
        "language": "python",
        "code": bad_code,
        "static_only": True
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["is_valid_syntax"] is False
    assert any("SyntaxError" in d for d in data["diagnostics"])
    assert data["model_name"] == "Deterministic Python AST"

def test_improve_and_explain_endpoints(client):
    """Test improve and explain endpoints return 200 for valid input."""
    sample_code = "for i in range(10): print(i)"
    
    # Improve
    res_imp = client.post("/improve", json={"mode": "improve", "language": "python", "code": sample_code})
    assert res_imp.status_code == 200
    assert res_imp.get_json()["mode"] == "improve"

    # Explain
    res_exp = client.post("/explain", json={"mode": "explain", "language": "python", "code": sample_code})
    assert res_exp.status_code == 200
    assert res_exp.get_json()["mode"] == "explain"

def test_chat_followup(client):
    """Test conversational follow-up endpoint with graceful offline / online contract."""
    payload = {
        "message": "Can you add comments to this code?",
        "current_code": "def add(a, b): return a + b",
        "language": "python"
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    # Verifies contract: returns structured reply and preserved code
    assert "reply" in data or "error" in data
    assert "generated_code" in data

def test_input_size_limit_rejection(client):
    """Test that requests exceeding MAX_INPUT_CHARS are rejected."""
    huge_prompt = "x" * (Config.MAX_INPUT_CHARS + 100)
    payload = {
        "mode": "write",
        "language": "python",
        "prompt": huge_prompt
    }
    response = client.post("/generate", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert "exceeds maximum character limit" in data["error"]

def test_history_workflow(client):
    """Test history recording, single record view, and deletion."""
    # 1. Generate an item
    gen_res = client.post("/generate", json={
        "mode": "write",
        "language": "python",
        "prompt": "Test calculator"
    })
    rec_id = gen_res.get_json()["id"]

    # 2. View history page
    hist_page = client.get("/history")
    assert hist_page.status_code == 200
    assert "Test calculator" in hist_page.data.decode("utf-8")

    # 3. View individual record
    rec_page = client.get(f"/history/{rec_id}")
    assert rec_page.status_code == 200
    assert "Test calculator" in rec_page.data.decode("utf-8")

    # 4. Delete individual record
    del_res = client.post(f"/history/{rec_id}/delete")
    assert del_res.status_code == 200
    assert del_res.get_json()["success"] is True

    # 5. Accessing deleted record should return 404
    missing_page = client.get(f"/history/{rec_id}")
    assert missing_page.status_code == 404

def test_not_found_page(client):
    """Test custom 404 error handler."""
    response = client.get("/non-existent-route-404")
    assert response.status_code == 404
    assert "Page Not Found" in response.data.decode("utf-8")

