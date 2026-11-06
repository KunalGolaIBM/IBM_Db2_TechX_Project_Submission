import json
from dataclasses import replace

import pytest

from src.agent import llm


@pytest.fixture
def mock_mode(monkeypatch):
    monkeypatch.setattr(llm, "settings", replace(
        llm.settings, llm_provider="mock", llm_api_key=""))


def context(label):
    return {
        "scheme_id": "s1",
        "name": "Test Scheme",
        "label": label,
        "benefit_summary": "A cash benefit.",
        "rules": [
            {
                "scheme_id": "s1",
                "rule_id": 1,
                "criterion_code": "income_annual",
                "verdict": "PASS" if label != "NEAR_MISS" else "FAIL",
                "mandatory": 1,
                "observed_value": "180000",
                "threshold": "max 2.5 lakh",
                "rule_op": "lte",
                "clause_ref": "Para 2",
                "value_num": 250000,
                "value_text": None,
            }
        ],
        "clauses": [
            {"chunk_id": "c1", "clause_ref": "Para 2", "text": "Income must not exceed 2.5 lakh."},
            {"chunk_id": "c2", "clause_ref": "Para 3", "text": "Other conditions apply."},
        ],
    }


def test_mock_narration_cites_only_retrieved_clauses(mock_mode):
    for label in ["ELIGIBLE", "NEAR_MISS", "CLARIFY", "NOT_ELIGIBLE"]:
        result = llm.narrate([context(label)])["s1"]
        allowed = {"c1", "c2"}
        assert result["cited_chunk_ids"], label
        assert set(result["cited_chunk_ids"]).issubset(allowed)
        assert result["narrative"]


def test_near_miss_names_the_threshold(mock_mode):
    result = llm.narrate([context("NEAR_MISS")])["s1"]
    assert "2.5 lakh" in result["narrative"]


def test_invented_citation_is_dropped(monkeypatch):
    monkeypatch.setattr(llm, "settings", replace(llm.settings, llm_provider="openai_compatible", llm_api_key="sk-test"))
    payload = {"schemes": [{"scheme_id": "s1", "narrative": "Grounded text.",
                            "cited_chunk_ids": ["does-not-exist"]}]}
    monkeypatch.setattr(llm, "_post", lambda messages, json_mode: json.dumps(payload))

    result = llm.narrate([context("ELIGIBLE")])["s1"]
    assert result["cited_chunk_ids"] == ["c1"]
    assert result["narrative"] == "Grounded text."


def test_llm_transport_failure_degrades_to_mock(monkeypatch):
    monkeypatch.setattr(llm, "settings", replace(llm.settings, llm_provider="openai_compatible", llm_api_key="sk-test"))

    def boom(messages, json_mode):
        raise llm.LLMError("quota exceeded")

    monkeypatch.setattr(llm, "_post", boom)
    result = llm.narrate([context("ELIGIBLE")])["s1"]
    assert result["narrative"]
    assert result["cited_chunk_ids"] == ["c1"]


def test_normalisation_falls_back_to_the_deterministic_extractor(monkeypatch):
    monkeypatch.setattr(llm, "settings", replace(llm.settings, llm_provider="openai_compatible", llm_api_key="sk-test"))

    def boom(messages, json_mode):
        raise llm.LLMError("network down")

    monkeypatch.setattr(llm, "_post", boom)
    profile = llm.normalize_profile("I am a 34-year-old widow farmer in UP.")
    assert profile.facts["age"] == 34
    assert any("deterministic extractor" in note for note in profile.notes)

