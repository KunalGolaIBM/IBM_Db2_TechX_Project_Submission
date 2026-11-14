"""Agent loop tests with a scripted fake Gemini (no network)."""
import json

import pytest
from langchain_core.tools import StructuredTool

import llm
from agent import Investigator
from risk import RiskEngine, ScreenRequest


def scripted(responses):
    calls = []

    def fake_post(body, model=None):
        calls.append(body)
        return responses[len(calls) - 1]

    return fake_post, calls


def test_investigator_uses_db2_tools_and_can_only_raise(monkeypatch, repo, embedder):
    final = {"summary": "This seller matches reported Friends & Family scams.", "advice": ["Use Goods & Services"],
             "escalate": True, "extra_risk": 50, "escalation_reason": "seen before"}
    fake, calls = scripted([
        {"candidates": [{"content": {"role": "model", "parts": [
            {"functionCall": {"name": "lookup_entity", "args": {"entity_type": "email", "value": "fastdeals.ng@mail.example"}}}]}}]},
        {"candidates": [{"content": {"role": "model", "parts": [{"text": "```json\n" + json.dumps(final) + "\n```"}]}}]},
    ])
    monkeypatch.setattr(llm, "_post", fake)
    engine = RiskEngine(repo, embedder)
    req = ScreenRequest(merchant="FastDeals", payee_email="x@mail.example", amount=50, message="hello")
    res = engine.screen(req)
    out = Investigator(repo, embedder, engine).explain(req, res)
    assert out["mode"] == "gemini"
    assert out["extra_risk"] == 20  # clamped
    assert out["trace"][0]["tool"] == "lookup_entity" and "BLOCKED" in out["trace"][0]["result_preview"]
    # the tool result was sent back to the model as a functionResponse
    assert calls[1]["contents"][-1]["parts"][0]["functionResponse"]["name"] == "lookup_entity"


def test_investigator_falls_back_on_llm_error(monkeypatch, repo, embedder):
    def boom(body, model=None):
        raise llm.LLMUnavailable("down")

    monkeypatch.setattr(llm, "_post", boom)
    engine = RiskEngine(repo, embedder)
    req = ScreenRequest(merchant="Shop", payee_email="", amount=10, message="buy gift cards and send codes")
    res = engine.screen(req)
    out = Investigator(repo, embedder, engine).explain(req, res)
    assert out["mode"] == "rules" and out["summary"].startswith("Stop")


@pytest.mark.parametrize("model_extra, expected", [(-50, 0), (0, 0), (99, 20)])
def test_langchain_chain_never_returns_negative_risk(monkeypatch, repo, embedder, model_extra, expected):
    final = {"summary": "Evidence checked.", "extra_risk": model_extra, "escalate": True}
    fake, _ = scripted([{"candidates": [{"content": {"parts": [{"text": json.dumps(final)}]}}]}])
    monkeypatch.setattr(llm, "_post", fake)
    engine = RiskEngine(repo, embedder)
    req = ScreenRequest(message="Send your OTP now")
    result = engine.screen(req)
    out = Investigator(repo, embedder, engine).explain(req, result)
    assert out["mode"] == "gemini" and out["extra_risk"] == expected
    assert result.risk_score >= 70 and result.verdict == "BLOCK"


def test_investigator_dispatches_example_search_through_langchain(monkeypatch, repo, embedder):
    from load_scam_examples import load_examples, read_examples

    load_examples(repo, embedder)
    query = read_examples()[0]["text"]
    fake, _ = scripted([
        {"candidates": [{"content": {"role": "model", "parts": [
            {"functionCall": {"name": "search_scam_examples", "args": {"query": query}}}]}}]},
        {"candidates": [{"content": {"parts": [{"text": json.dumps({"summary": "Bank phishing example found."})}]}}]},
    ])
    monkeypatch.setattr(llm, "_post", fake)
    invoked = []
    original = StructuredTool.invoke

    def track(self, *args, **kwargs):
        invoked.append(self.name)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(StructuredTool, "invoke", track)
    engine = RiskEngine(repo, embedder)
    req = ScreenRequest(message=query)
    result = Investigator(repo, embedder, engine).explain(req, engine.screen(req))
    assert invoked == ["search_scam_examples"]
    assert result["mode"] == "gemini"
    assert "bank_phishing" in result["trace"][0]["result_preview"]
