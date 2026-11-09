"""Guard-rail tests for the bounded agent loop using a scripted chat-model TEST DOUBLE.
They prove the loop's limits, allow-list and validation logic; they do not prove LLM quality."""

import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from civiclens.agent import runner
from civiclens.domain.errors import AgentError, AgentStepLimitError, AgentTimeoutError
from civiclens.domain.investigation_models import RecommendationDraft
from tests.scripted_llm import ScriptedChatModel, ai_calls, tool_call

LIMITS = runner.Limits(max_steps=4, timeout_s=30)


class _Args(BaseModel):
    days: int = Field(default=7, ge=1, le=30)


class Spy:
    def __init__(self):
        self.executed = []

    def tool(self, name="search_complaints"):
        def fn(days=7):
            self.executed.append((name, days))
            return {
                "ok": True,
                "data": [{"complaint_id": 11, "title": "a"}, {"complaint_id": 12, "title": "b"}],
            }

        return StructuredTool.from_function(func=fn, name=name, description="d", args_schema=_Args)


FINAL = json.dumps({"recommendations": [{
    "summary": "Fix the cluster", "rationale": "Complaints 11 and 12 describe it.",
    "priority": 2, "confidence": 0.8, "evidence_ids": [11, 12], "status": "APPROVED"}]})  # fmt: skip


def run(responder, spy=None, limits=LIMITS, clock=None):
    spy = spy or Spy()
    audits = []
    model = ScriptedChatModel(responder=responder)
    kwargs = {"clock": clock} if clock else {}
    result = runner.run_llm_loop(
        model, {"search_complaints": spy.tool()}, "q?", limits,
        lambda a, p, s, ok: audits.append((a, ok)), **kwargs)  # fmt: skip
    return result, spy, audits, model


def test_happy_path_tool_then_final_answer_and_status_is_dropped():
    def responder(msgs, n):
        return ai_calls(tool_call("search_complaints", {"days": 7})) if n == 1 else AIMessage(content=FINAL)

    result, spy, _, model = run(responder)
    assert spy.executed == [("search_complaints", 7)]
    assert result.seen_ids == {11, 12} and result.steps == 2 and result.tool_calls == 1
    assert isinstance(result.drafts[0], RecommendationDraft)
    assert not hasattr(result.drafts[0], "status")  # model-supplied status never survives parsing
    assert model.bound_tool_names == ["search_complaints"]


def test_tool_outside_allow_list_is_refused_and_not_executed():
    def responder(msgs, n):
        return (
            ai_calls(tool_call("execute_sql", {"query": "DROP TABLE X"}))
            if n == 1
            else AIMessage(content=FINAL)
        )

    result, spy, audits, _ = run(responder)
    assert spy.executed == [] and result.rejected_calls == 1
    assert ("TOOL_REFUSED", False) in audits


def test_invalid_tool_arguments_are_rejected_before_execution():
    def responder(msgs, n):
        return (
            ai_calls(tool_call("search_complaints", {"days": 9999})) if n == 1 else AIMessage(content=FINAL)
        )

    result, spy, audits, _ = run(responder)
    assert spy.executed == [] and ("TOOL_ARGS_REJECTED", False) in audits


def test_a_provider_failure_becomes_a_structured_error_that_does_not_leak_the_provider_text():
    """Wrong key, unknown model, rate limit, network: whatever the SDK raises, the loop reports a coded error
    naming only the exception class (the SDK's message can carry request details)."""

    def responder(messages, n):
        raise RuntimeError("Incorrect API key provided: sk-FAKE-0123456789")

    with pytest.raises(AgentError) as exc:
        run(responder)
    assert exc.value.code == "LLM_PROVIDER_ERROR"
    assert exc.value.details == {"reason": "RuntimeError"}
    assert "sk-FAKE" not in str(exc.value) and "sk-FAKE" not in repr(exc.value.to_detail())
    assert exc.value.__cause__ is None  # the original exception (and its text) is not chained either


def test_step_limit_is_enforced():
    with pytest.raises(AgentStepLimitError) as exc:
        run(lambda m, n: ai_calls(tool_call("search_complaints", {}, f"c{n}")))
    assert exc.value.code == "AGENT_STEP_LIMIT"


def test_timeout_is_enforced_with_a_fake_clock():
    ticks = iter([0.0, 0.0, 100.0, 100.0, 100.0, 100.0])
    with pytest.raises(AgentTimeoutError):
        run(lambda m, n: ai_calls(tool_call("search_complaints", {}, f"c{n}")),
            limits=runner.Limits(5, 10), clock=lambda: next(ticks))  # fmt: skip


@pytest.mark.parametrize(
    "content", ["not json", "{}", '{"recommendations": "x"}', '{"recommendations":[{"summary":"x"}]}']
)
def test_invalid_model_output_is_a_structured_error(content):
    with pytest.raises(AgentError) as exc:
        run(lambda m, n: AIMessage(content=content))
    assert exc.value.code == "INVALID_MODEL_OUTPUT"


def test_parses_fenced_json_and_provider_content_blocks():
    blocks = [{"type": "text", "text": "```json\n" + FINAL + "\n```"}]
    drafts = runner.parse_final(blocks)
    assert drafts[0].evidence_ids == [11, 12]


def test_too_many_recommendations_rejected():
    item = json.loads(FINAL)["recommendations"][0]
    with pytest.raises(AgentError):
        runner.parse_final(json.dumps({"recommendations": [item] * 6}))


def test_grounding_rejects_ids_never_returned_by_a_tool():
    draft = RecommendationDraft(summary="Fabricated", rationale="Cites ids it never saw.", priority=1,
                                confidence=0.9, evidence_ids=[11, 999999])  # fmt: skip
    ok = RecommendationDraft(summary="Grounded", rationale="Cites only seen ids.", priority=1,
                             confidence=0.9, evidence_ids=[11])  # fmt: skip
    accepted, rejected = runner.ground_drafts([draft, ok], {11, 12})
    assert accepted == [ok] and rejected == [(draft, [999999])]


def test_tool_message_payload_is_truncated():
    big = StructuredTool.from_function(
        func=lambda days=7: {"ok": True, "data": [{"complaint_id": 1, "x": "y" * 50_000}]},
        name="search_complaints", description="d", args_schema=_Args)  # fmt: skip
    seen_payloads = []

    def responder(msgs, n):
        if n == 1:
            return ai_calls(tool_call("search_complaints", {}))
        seen_payloads.extend(m.content for m in msgs if isinstance(m, ToolMessage))
        return AIMessage(content=FINAL)

    runner.run_llm_loop(ScriptedChatModel(responder=responder), {"search_complaints": big}, "q", LIMITS,
                        lambda *a: None)  # fmt: skip
    assert len(seen_payloads[0]) < runner.MAX_TOOL_MESSAGE_CHARS + 50


def test_collect_complaint_ids_is_recursive_and_type_safe():
    data = {
        "a": [{"complaint_id": 5}, {"x": {"complaint_id": 6}}],
        "complaint_id": "7",
        "b": {"complaint_id": True},
    }
    assert runner.collect_complaint_ids(data) == {5, 6}
