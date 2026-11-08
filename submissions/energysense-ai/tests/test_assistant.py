import sys
from types import ModuleType, SimpleNamespace

import pytest

from src import assistant
from src.config import Settings


class FakeStore:
    def recent_telemetry(self, appliance_id, limit=100):
        return [{
            "telemetry_id": "t-1", "equipment_id": "ES-1", "appliance_id": appliance_id,
            "irms_a": 1.5, "vrms_v": 230.0, "apparent_power_va": 345.0,
            "runtime_s": 3600, "temperature_c": 40.0, "vibration_rms": 0.2,
            "source": "synthetic",
        }]

    def list_events(self, appliance_id=None, limit=100):
        return []


def test_langchain_agent_registers_read_only_tools(monkeypatch):
    captured = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(invoke=lambda _payload: {"messages": [SimpleNamespace(content="Grounded answer")]})

    langchain_package = ModuleType("langchain")
    langchain_agents = ModuleType("langchain.agents")
    langchain_agents.create_agent = fake_create_agent
    langchain_openai = ModuleType("langchain_openai")
    langchain_openai.ChatOpenAI = lambda **kwargs: SimpleNamespace(config=kwargs)
    monkeypatch.setitem(sys.modules, "langchain", langchain_package)
    monkeypatch.setitem(sys.modules, "langchain.agents", langchain_agents)
    monkeypatch.setitem(sys.modules, "langchain_openai", langchain_openai)
    monkeypatch.setattr(assistant, "get_settings", lambda: Settings(openai_api_key="test-key"))
    monkeypatch.setitem(sys.modules, "src.langchain_db2", SimpleNamespace(search_maintenance_knowledge=lambda *_args, **_kwargs: ["note"]))

    agent = assistant.build_assistant(FakeStore())
    tool_names = {tool.__name__ for tool in captured["tools"]}
    assert tool_names == {"get_recent_readings", "analyse_appliance", "retrieve_maintenance_notes", "get_recent_events"}
    assert "never proves" in captured["system_prompt"]
    assert agent.invoke({"messages": []})["messages"][-1].content == "Grounded answer"


def test_assistant_requires_api_key(monkeypatch):
    monkeypatch.setattr(assistant, "get_settings", lambda: Settings(openai_api_key=""))
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        assistant.build_assistant(FakeStore())


def test_assistant_rejects_blank_question():
    with pytest.raises(ValueError, match="non-whitespace"):
        assistant.ask_assistant(FakeStore(), "   ")
