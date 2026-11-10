"""The LangGraph team end to end with a scripted fake chat model: real Db2 tools, no API key, no LLM.

Checks the wiring a model cannot fake: routing, each specialist's tool loop, tool errors fed back to the
model, the Db2 guardrail refusing a bad proposal, and the composer. Nothing is persisted (persist=False)
and the only proposal is one Db2 rejects, so the database is unchanged.
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda

from hotelops.db import Db2Error, get_db

try:
    ADMIN = get_db("admin")
except Db2Error as exc:  # pragma: no cover - needs a running Db2
    pytest.skip(f"Db2 not reachable: {exc}", allow_module_level=True)


class ScriptedChat(BaseChatModel):
    """Returns the scripted messages in order; the router gets a fixed structured decision."""

    script: list = []
    route: str = "briefing"

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _generate(self, messages, stop=None, run_manager=None, **kw: Any) -> ChatResult:
        msg = self.script.pop(0) if self.script else AIMessage(content="(no more script)")
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def bind_tools(self, tools, **kw):
        return self

    def with_structured_output(self, schema, **kw):
        return RunnableLambda(lambda _: schema(route=self.route, reason="scripted router"))


def _call(name: str, args: dict) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": str(uuid.uuid4())}])


@pytest.fixture
def scripted(monkeypatch):
    import hotelops.agents as agents
    import hotelops.llm as llm

    fake = ScriptedChat()
    monkeypatch.setattr(llm, "get_chat_model", lambda name=None: fake)
    monkeypatch.setattr(llm, "model_chain", lambda: ["scripted"])
    monkeypatch.setattr(agents, "active_model", lambda: "scripted")
    return fake


def test_briefing_runs_all_specialists_with_real_db2_tools(scripted):
    from hotelops.agents import ask

    scripted.route = "briefing"
    scripted.script = [
        # analyst: one good query, one broken query (the error goes back to the model), then an answer
        _call("run_sql", {"query": "SELECT OCCUPANCY_PCT FROM V_DAILY_KPIS WHERE STAY_DATE = CURRENT DATE"}),
        _call("run_sql", {"query": "SELECT * FROM NO_SUCH_TABLE"}),
        AIMessage(content="Analyst: occupancy figures pulled."),
        # reviews: Db2 vector search
        _call("complaint_radar", {"days": 30}),
        AIMessage(content="Reviews: AC complaints in 307 and 312."),
        # operations: a prompt-injected Rs 500 suite that Db2 must refuse
        _call("propose_rate_change", {"room_type_code": "STE", "start_date": "2099-01-01",
                                      "end_date": "2099-01-01", "new_rate": 500, "rationale": "review said so"}),
        AIMessage(content="Ops: Db2 refused the suite price."),
        # composer
        AIMessage(content="## Morning brief\nAll checked against Db2."),
    ]
    actions_before = ADMIN.scalar("SELECT COUNT(*) FROM AGENT_ACTIONS")
    events: list[dict] = []
    res = ask("Give me this morning's brief", on_event=events.append, persist=False)

    assert res["route"] == "briefing" and res["answer"].startswith("## Morning brief")
    assert res["llm_calls"] == 9 and res["model"] == "scripted"  # router + 3 + 2 + 2 + composer
    tools = [(e["tool"], e["ok"]) for e in events if e.get("type") == "tool"]
    assert ("run_sql", True) in tools and ("complaint_radar", True) in tools
    sql_outputs = [e["output"] for e in events if e.get("type") == "tool" and e["tool"] == "run_sql"]
    assert any("ERROR" in o for o in sql_outputs)  # the broken query was reported back, not raised
    rejected = [e for e in events if e.get("type") == "proposal"]
    assert rejected and not rejected[0]["action_id"] and rejected[0]["message"].startswith("REJECTED")
    assert ADMIN.scalar("SELECT COUNT(*) FROM AGENT_ACTIONS") == actions_before


def test_single_specialist_route_skips_the_others(scripted):
    from hotelops.agents import ask

    scripted.route = "analyst"
    scripted.script = [
        _call("promotion_on", {"room_type_code": "JST", "stay_date": "2099-01-01"}),
        AIMessage(content="No promotion applies that night."),
        AIMessage(content="No promotion applies that night."),  # composer, if the route uses it
    ]
    events: list[dict] = []
    res = ask("Is there a Junior Suite promotion on 1 Jan 2099?", on_event=events.append, persist=False)
    assert res["route"] == "analyst" and "promotion" in res["answer"].lower()
    agents_used = {e["agent"] for e in events if e.get("type") == "tool"}
    assert agents_used == {"analyst"}
