"""LLM layer: deadlines, capped retries and schema validation, with no network calls."""

from __future__ import annotations

import time

import pytest
from pydantic import ValidationError

from asof.config import ConfigError, Settings
from asof.llm import LLMClient, LLMError, build_llm
from asof.schemas import ExtractionResult, JudgeResult


class StubRunnable:
    def __init__(self, behaviours):
        self.behaviours = list(behaviours)
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        behaviour = self.behaviours.pop(0)
        if isinstance(behaviour, BaseException):
            raise behaviour
        if callable(behaviour):
            return behaviour()
        return behaviour


class StubChatModel:
    def __init__(self, runnable):
        self.runnable = runnable
        self.structured_kwargs = None

    def with_structured_output(self, schema, **kwargs):
        self.structured_kwargs = kwargs
        return self.runnable


def client(behaviours, provider="openrouter", deadline=5.0):
    runnable = StubRunnable(behaviours)
    chat = StubChatModel(runnable)
    return LLMClient(chat, provider, "stub-model", attempts=2, deadline_s=deadline), runnable, chat


def ok(claims=()):
    return {"raw": None, "parsed": ExtractionResult(claims=list(claims)), "parsing_error": None}


def test_valid_output_is_returned():
    llm, runnable, _ = client([ok()])
    result = llm.structured(ExtractionResult, [("human", "x")])
    assert result.value.claims == []
    assert result.attempts == 1 and runnable.calls == 1


def test_malformed_output_is_retried_once_then_fails():
    bad = {"raw": None, "parsed": None, "parsing_error": ValueError("not json")}
    llm, runnable, _ = client([bad, bad])
    with pytest.raises(LLMError, match="no valid ExtractionResult"):
        llm.structured(ExtractionResult, [("human", "x")])
    assert runnable.calls == 2


def test_wrong_schema_type_is_rejected():
    wrong = {"raw": None, "parsed": {"claims": []}, "parsing_error": None}
    llm, _, _ = client([wrong, wrong])
    with pytest.raises(LLMError):
        llm.structured(ExtractionResult, [("human", "x")])


def test_transport_error_then_success():
    llm, runnable, _ = client([ConnectionError("reset"), ok()])
    result = llm.structured(ExtractionResult, [("human", "x")])
    assert result.attempts == 2 and runnable.calls == 2


def test_deadline_is_hard_and_not_retried():
    def slow():
        time.sleep(3)
        return ok()

    llm, runnable, _ = client([slow, ok()], deadline=0.3)
    started = time.monotonic()
    with pytest.raises(LLMError, match="did not answer within"):
        llm.structured(ExtractionResult, [("human", "x")])
    assert time.monotonic() - started < 1.5
    assert runnable.calls == 1  # a timeout is final


def test_strict_json_schema_for_hosted_providers():
    llm, _, chat = client([ok()], provider="openrouter")
    llm.structured(ExtractionResult, [("human", "x")])
    assert chat.structured_kwargs == {"method": "json_schema", "include_raw": True, "strict": True}


def test_ollama_gets_a_length_bounded_grammar():
    """A local model looped inside quoted_span until the output cap; maxLength stops that."""
    from asof.llm import bounded_schema

    schema = bounded_schema(JudgeResult)
    verdict = schema["$defs"]["ClaimVerdict"]["properties"]
    assert {"type": "string", "maxLength": 400} in verdict["quoted_span"]["anyOf"]
    assert verdict["reason"]["maxLength"] == 400
    assert "maxLength" not in verdict["verdict"]  # enums stay as they are


def test_ollama_reply_is_parsed_and_validated():
    from types import SimpleNamespace

    class StubOllama:
        def __init__(self, content):
            self.content, self.formats = content, []

        def bind(self, **kwargs):
            self.formats.append(kwargs["format"])
            return SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=self.content, usage_metadata={}))

    good = StubOllama('{"claims": []}')
    result = LLMClient(good, "ollama", "stub", attempts=2, deadline_s=5).structured(ExtractionResult, [("human", "x")])
    assert result.value.claims == [] and good.formats
    bad = StubOllama('{"claims": [{"text": "unterminated')
    with pytest.raises(LLMError, match="no valid ExtractionResult"):
        LLMClient(bad, "ollama", "stub", attempts=2, deadline_s=5).structured(ExtractionResult, [("human", "x")])


def test_openrouter_requires_key():
    with pytest.raises(ConfigError, match="OPENROUTER_API_KEY"):
        build_llm(Settings(_env_file=None, openrouter_api_key=None), provider="openrouter")


def test_providers_get_output_cap_and_no_default_temperature():
    s = Settings(_env_file=None, openrouter_api_key="sk-or-test", llm_max_output_tokens=900)
    hosted = build_llm(s, provider="openrouter")
    assert hosted.chat_model.max_tokens == 900
    assert hosted.chat_model.temperature is None
    local = build_llm(s, provider="ollama")
    assert local.chat_model.num_predict == 900


def test_schemas_forbid_extra_keys_and_unknown_verdicts():
    with pytest.raises(ValidationError):
        JudgeResult.model_validate({"verdicts": [], "note": "extra"})
    with pytest.raises(ValidationError):
        JudgeResult.model_validate({"verdicts": [{"claim_no": 1, "verdict": "PROBABLY", "clause_id": None,
                                                  "quoted_span": None, "reason": "x"}]})


def test_ollama_requests_are_not_streamed():
    """A streamed reply keeps the read timeout from firing while a model loops; one response does not."""
    from langchain_core.messages import HumanMessage

    local = build_llm(Settings(_env_file=None), provider="ollama")
    params = local.chat_model._chat_params([HumanMessage("hi")])
    assert params["stream"] is False
    assert params["options"]["num_predict"] == Settings(_env_file=None).llm_max_output_tokens


def test_choices_restrict_fields_in_the_ollama_grammar():
    from asof.llm import bounded_schema

    schema = bounded_schema(JudgeResult, choices={"clause_id": ["BRV-002"], "quoted_span": ["A sentence.", "Another one."]})
    props = schema["$defs"]["ClaimVerdict"]["properties"]
    assert props["clause_id"]["anyOf"] == [{"type": "string", "enum": ["BRV-002"]}, {"type": "null"}]
    assert props["quoted_span"]["anyOf"][0]["enum"] == ["A sentence.", "Another one."]
    assert props["reason"]["maxLength"] == 400


def test_hosted_providers_ignore_choices():
    llm, _, chat = client([ok()], provider="openrouter")
    llm.structured(ExtractionResult, [("human", "x")], choices={"text": ["x"]})
    assert chat.structured_kwargs == {"method": "json_schema", "include_raw": True, "strict": True}
