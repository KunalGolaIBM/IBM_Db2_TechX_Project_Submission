"""Gemini request compatibility checks without external API calls."""
from types import SimpleNamespace

import pytest

import llm


@pytest.mark.parametrize("override", [None, "gemini-4-hydrogen"])
def test_gemini4_omits_sampling_and_preserves_structured_output(monkeypatch, override):
    monkeypatch.setattr(llm, "settings", SimpleNamespace(
        gemini_api_key="test-key", gemini_model="gemini-4-hydrogen" if override is None else "gemini-2.5-flash"))
    schema = {"type": "OBJECT", "properties": {"summary": {"type": "STRING"}}}
    body = {
        "contents": [{"role": "user", "parts": [{"text": "Check this payment"}]}],
        "generationConfig": {"temperature": 0.1, "topP": 0.9, "topK": 40,
                             "responseMimeType": "application/json", "responseSchema": schema},
    }
    requests = []

    def fake_post(url, **kwargs):
        requests.append((url, kwargs))
        return SimpleNamespace(status_code=200, json=lambda: {"candidates": []})

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    llm._post(body, model=override)
    url, request = requests[0]
    assert url.endswith("/gemini-4-hydrogen:generateContent")
    assert request["json"]["generationConfig"] == {
        "responseMimeType": "application/json", "responseSchema": schema}
    assert request["json"]["contents"] == body["contents"]
    assert body["generationConfig"]["temperature"] == 0.1


def test_tool_loop_preserves_thought_signatures(monkeypatch):
    model_turn = {"role": "model", "parts": [
        {"functionCall": {"name": "lookup_entity", "args": {"value": "seller@example.com"}},
         "thoughtSignature": "opaque-signature"}]}
    requests = []

    def fake_post(body, model=None):
        requests.append(body)
        content = model_turn if len(requests) == 1 else {"role": "model", "parts": [{"text": "Checked."}]}
        return {"candidates": [{"content": content}]}

    monkeypatch.setattr(llm, "_post", fake_post)
    answer, trace = llm.run_tool_agent("Check the seller", "Use evidence", [],
                                       {"lookup_entity": lambda value: {"status": "SUSPECT"}})
    assert answer == "Checked."
    assert trace[0]["tool"] == "lookup_entity"
    assert requests[1]["contents"][1] == model_turn
    assert requests[1]["contents"][2]["parts"][0]["functionResponse"]["response"] == {
        "result": {"status": "SUSPECT"}}
