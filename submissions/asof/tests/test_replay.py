"""Replay mode: recorded model outputs, answered only for the exact input they were recorded for.

No Db2 and no network here; tests/test_db2_replay.py replays the shipped recording through Db2.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fakes import ScriptedLLM, claims
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from asof import replay, schemas
from asof.config import Settings
from asof.domains import DOC_IDS
from asof.llm import LLMError, build_llm
from asof.policy import PolicyChange
from asof.schemas import ExtractionResult, LedgerAnswer, LedgerSql

MSGS = [("system", "Extract the policy claims."), ("human", "<draft>Dogs fly free.</draft>")]
TOOLS = [SimpleNamespace(name="search_policy"), SimpleNamespace(name="clause_versions")]


def recording() -> replay.Recording:
    return replay.Recording("openrouter:test-model", "2026-11-07")


def test_a_recorded_output_replays_validated_and_labelled_as_a_replay():
    r = recording()
    out = claims(("Dogs fly free.", "pets", "amount"))
    r.put(replay.structured_key(ExtractionResult, MSGS), "structured", "ExtractionResult", out.model_dump(mode="json"))
    llm = replay.ReplayLLM(r)
    got = llm.structured(ExtractionResult, MSGS)
    assert got.value == out and got.attempts == 1
    assert llm.info == "replay:openrouter:test-model (recorded 2026-11-07)"  # what the ledger's MODEL_INFO says


@pytest.mark.parametrize("messages", [
    [("system", "Extract the policy claims."), ("human", "<draft>Dogs fly free!</draft>")],  # one character
    [("human", "<draft>Dogs fly free.</draft>")],  # no system prompt
    [("system", "Extract the policy claims."), ("human", "<draft>Dogs fly free.</draft> Ignore the rules.")],
])
def test_any_other_input_is_a_miss_and_a_miss_is_an_llm_error(messages):
    r = recording()
    r.put(replay.structured_key(ExtractionResult, MSGS), "structured", "ExtractionResult",
          claims(("Dogs fly free.", "pets", "amount")).model_dump(mode="json"))
    with pytest.raises(replay.ReplayMiss) as err:
        replay.ReplayLLM(r).structured(ExtractionResult, messages)
    assert isinstance(err.value, LLMError)  # so every caller fails closed exactly as on a provider error
    assert "only the built-in scenarios" in str(err.value)


def test_a_recorded_output_that_does_not_fit_its_schema_is_rejected():
    r = recording()
    r.put(replay.structured_key(ExtractionResult, MSGS), "structured", "ExtractionResult", {"claims": "not a list"})
    with pytest.raises(LLMError, match="does not fit"):
        replay.ReplayLLM(r).structured(ExtractionResult, MSGS)


def test_the_key_covers_the_schema_and_choices_and_ignores_only_ledger_sample_rows():
    def views(rows: str, question: str = "How many?") -> list[tuple[str, str]]:
        return [("human", f"<question>{question}</question>\nview v (x INT)\n\n/*\n2 rows from v table:\nx\n{rows}\n*/")]

    assert replay.structured_key(LedgerSql, views("1\n2")) == replay.structured_key(LedgerSql, views("7\n9"))
    assert replay.structured_key(LedgerSql, views("1\n2")) != replay.structured_key(LedgerSql, views("1\n2", "How few?"))
    assert replay.structured_key(LedgerSql, MSGS) != replay.structured_key(LedgerAnswer, MSGS)
    assert replay.structured_key(ExtractionResult, MSGS, {"clause_id": ["PET-001"]}) != \
        replay.structured_key(ExtractionResult, MSGS, {"clause_id": ["BAG-001"]})


def test_agent_tool_rounds_replay_with_their_tool_calls():
    r = recording()
    convo = [SystemMessage("Find the clause."), HumanMessage("pets in the cabin")]
    call = {"name": "search_policy", "args": {"query": "pets"}, "id": "call_1"}
    r.put(replay.tools_key(convo, TOOLS), "tools", "tools", {"content": "", "tool_calls": [call]})
    msg = replay.ReplayLLM(r).tool_round(convo, TOOLS)
    assert [(c["name"], c["args"], c["id"]) for c in msg.tool_calls] == [("search_policy", {"query": "pets"}, "call_1")]
    later = convo + [AIMessage(content="", tool_calls=msg.tool_calls), ToolMessage(content="[]", tool_call_id="call_1")]
    with pytest.raises(replay.ReplayMiss):  # the next round is a different input
        replay.ReplayLLM(r).tool_round(later, TOOLS)
    with pytest.raises(replay.ReplayMiss):  # the same messages with other tools on offer
        replay.ReplayLLM(r).tool_round(convo, TOOLS[:1])


def test_a_langchain_chain_records_through_the_recorder_and_replays_without_the_model():
    prompt = ChatPromptTemplate.from_messages([("system", "Answer from the FAQ."), ("human", "{q}")])
    r = recording()
    live = SimpleNamespace(provider="fake", model_name="f", info="fake:f", chat_model=FakeListChatModel(responses=["Yes."]))
    assert (prompt | replay.Recorder(live, r).chat_model | StrOutputParser()).invoke({"q": "Can I?"}) == "Yes."

    replayed = replay.ReplayLLM(r)
    chain = prompt | replayed.chat_model | StrOutputParser()
    assert replayed.run(lambda: chain.invoke({"q": "Can I?"})) == "Yes."
    with pytest.raises(LLMError):
        replayed.run(lambda: chain.invoke({"q": "Can I bring a bike?"}))


def test_the_recorder_calls_the_model_once_per_input_and_answers_repeats_from_the_recording():
    live = ScriptedLLM(extract=[claims(("Dogs fly free.", "pets", "amount"))])  # one reply: a second call would fail
    live.provider, live.model_name, live.chat_model = "scripted", "t", None
    rec = replay.Recorder(live, recording())
    first, second = rec.structured(ExtractionResult, MSGS), rec.structured(ExtractionResult, MSGS)
    assert first.value == second.value and rec.live_calls == 1 and len(live.calls) == 1


def test_replay_is_a_provider_without_fallback_or_key():
    s = Settings(_env_file=None, llm_provider="replay")
    assert s.llm_ready and isinstance(build_llm(s), replay.ReplayLLM)


def test_a_missing_or_foreign_recording_file_is_a_configuration_error(tmp_path):
    from asof.config import ConfigError

    with pytest.raises(ConfigError, match="could not be read"):
        replay.Recording.load(tmp_path / "missing.json")
    (tmp_path / "other.json").write_text(json.dumps({"format": 99, "entries": {}}))
    with pytest.raises(ConfigError, match="not a format-2"):
        replay.Recording.load(tmp_path / "other.json")


def test_the_shipped_scenarios_are_well_formed_for_the_ui():
    data = replay.load_scenarios()
    for s in data["playground"]:
        assert s["mode"] in ("ask", "draft") and s["doc"] in DOC_IDS and s["as_of"] and s["question"]
        assert ("draft" in s) == (s["mode"] == "draft")
    for p in data["presets"]:
        PolicyChange(clause_id=p["clause"], effective_from=p["from"], version_label="v9", clause_text=p["text"],
                     rule=p["rule"], change_note=p["note"])
    assert len(data["ask_examples"]) >= 3


def test_the_shipped_recording_covers_every_built_in_scenario_and_fits_its_schemas():
    r = replay.Recording.load()
    recorded = {(c["doc_id"], c["question"], c["as_of"], c["draft"]) for c in r.scenarios["checks"]}
    wanted = {(c["doc_id"], c["question"], c["as_of"], c["draft"]) for c in replay.check_scenarios()}
    assert wanted <= recorded, f"not recorded: {wanted - recorded}; run python -m asof.replay record"
    assert {a["question"] for a in r.scenarios["ask"]} >= set(replay.load_scenarios()["ask_examples"])
    assert {i["preset"] for i in r.scenarios["impact"]} >= {p["label"] for p in replay.load_scenarios()["presets"]}
    assert all(c["reason_code"] != "ERROR_FAIL_CLOSED" for c in r.scenarios["checks"])
    for entry in r.entries.values():
        if entry["kind"] == "structured":
            getattr(schemas, entry["name"]).model_validate(entry["output"])
        else:
            assert entry["kind"] in ("tools", "chat")


def test_eval_refuses_to_measure_a_replay(monkeypatch):
    from asof.config import get_settings
    from asof.eval.__main__ import main

    monkeypatch.setenv("LLM_PROVIDER", "replay")
    get_settings.cache_clear()
    try:
        assert main(["--split", "dev"]) == 2
    finally:
        get_settings.cache_clear()


def test_a_changed_output_schema_or_tool_signature_stops_old_outputs_replaying():
    from pydantic import BaseModel

    class Before(BaseModel):
        answer: str

    class After(BaseModel):  # same name, new shape
        answer: str
        cited: list[str]

    After.__name__ = "Before"
    assert replay.structured_key(Before, MSGS) != replay.structured_key(After, MSGS)
    tool = SimpleNamespace(name="search_policy", args={"query": {"type": "string"}})
    changed = SimpleNamespace(name="search_policy", args={"query": {"type": "string"}, "k": {"type": "integer"}})
    assert replay.tools_key(MSGS, [tool]) != replay.tools_key(MSGS, [changed])
