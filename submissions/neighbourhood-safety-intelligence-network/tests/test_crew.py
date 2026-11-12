"""CrewAI multi-agent briefing on IBM Granite (Ollama) grounded in IBM Db2. Real calls, no mocks."""
from backend.app.ai.crewai.crew import format_protocols, granite_embedding, is_grounded, protocol_search_tool
from backend.app.core.config import settings

API = "/api/v1"


def test_ibm_db2_vector_search_tool_finds_protocol_passages():
    tool = protocol_search_tool()
    assert type(tool).__name__ == "DB2VectorSearchTool"          # IBM's tool from crewai-tools
    out = tool.run(query="elderly neighbour not answering the door")
    assert "senior" in out.lower() or "elder" in out.lower(), out[:300]


def test_granite_embedding_dimensions():
    assert len(granite_embedding("streetlight broken")) == settings.EMBEDDING_DIM


def test_format_and_grounding_helpers():
    assert format_protocols([]) == "No approved protocol matched."
    protos = [{"title": "Senior Citizen Wellness Checks and Assistance Procedures", "source": "s", "excerpt": "x"}]
    assert "Senior Citizen Wellness" in format_protocols(protos)
    assert is_grounded("1. Visit. Source: Senior Citizen Wellness Checks and Assistance Procedures", protos)
    assert not is_grounded("1. Do something unrelated.", protos)


def test_crew_briefing_runs_granite_agents_over_db2(client, resident):
    res = client.post(f"{API}/ai/crew-briefing", headers=resident,
                      json={"raw_text": "My elderly neighbour has not answered her door or phone since last night."})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["triage"]["suggested_priority"] == "P2_HIGH"          # rule-based priority stays authoritative
    assert body["briefing_error"] is None, body["briefing_error"]
    b = body["briefing"]
    assert b["model"] == settings.OLLAMA_CHAT_MODEL and b["agents"] == ["Triage Analyst", "Protocol Advisor"]
    assert len(b["summary"]) > 20 and len(b["advice"]) > 20
    assert b["cited_protocols"] and isinstance(b["grounded"], bool)


def test_crew_briefing_degrades_when_llm_is_unreachable(client, resident):
    original = settings.OLLAMA_HOST
    settings.OLLAMA_HOST = "http://127.0.0.1:9"  # nothing listens here: a real connection failure
    try:
        res = client.post(f"{API}/ai/crew-briefing", headers=resident, json={"raw_text": "Streetlight broken on Lane 4"})
    finally:
        settings.OLLAMA_HOST = original
    body = res.json()
    assert res.status_code == 200 and body["briefing"] is None
    assert body["briefing_error"].startswith("LLM briefing unavailable")
    assert body["triage"]["suggested_priority"] == "P3_MODERATE"


def test_crew_briefing_can_be_disabled(client, resident):
    settings.ENABLE_LLM_BRIEFING = False
    try:
        body = client.post(f"{API}/ai/crew-briefing", headers=resident, json={"raw_text": "Open pit near the school gate"}).json()
    finally:
        settings.ENABLE_LLM_BRIEFING = True
    assert body["briefing"] is None and "disabled" in body["briefing_error"]
