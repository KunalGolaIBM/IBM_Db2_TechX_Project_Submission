"""Agent loop tests with a scripted fake Gemini (no network)."""
import json

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
