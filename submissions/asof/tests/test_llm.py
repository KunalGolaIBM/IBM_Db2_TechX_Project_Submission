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


def test_strict_json_schema_for_hosted_providers_only():
    llm, _, chat = client([ok()], provider="openrouter")
    llm.structured(ExtractionResult, [("human", "x")])
    assert chat.structured_kwargs == {"method": "json_schema", "include_raw": True, "strict": True}

    llm, _, chat = client([ok()], provider="ollama")
    llm.structured(ExtractionResult, [("human", "x")])
    assert "strict" not in chat.structured_kwargs


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
