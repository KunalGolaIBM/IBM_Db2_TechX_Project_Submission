"""Claim extraction tests (no external services)."""

from __future__ import annotations

import pytest

from app.services.claim_extraction import ClaimExtractionService, find_span
from tests.fakes import ScriptedLLM, extraction_response

TEXT = (
    "SolarCell-X achieved 92% conversion efficiency under standard test conditions. "
    "The coating reduced manufacturing cost by 15% compared with the baseline."
)


def make_service(claims: list[dict], max_claims: int = 25) -> ClaimExtractionService:
    return ClaimExtractionService(
        ScriptedLLM(lambda system, user: extraction_response(claims)), max_claims=max_claims
    )


def test_extracts_atomic_claims_and_spans():
    service = make_service(
        [
            {
                "original_claim": "SolarCell-X achieved 92% conversion efficiency under standard test conditions.",
                "normalized_claim": "SolarCell-X achieved 92% conversion efficiency.",
                "claim_type": "NUMERICAL",
            },
            {
                "original_claim": "The coating reduced manufacturing cost by 15% compared with the baseline.",
                "normalized_claim": "The coating reduced manufacturing cost by 15%.",
                "claim_type": "numerical",
            },
        ]
    )
    claims = service.extract(TEXT)
    assert len(claims) == 2
    assert claims[0].claim_type == "NUMERICAL"
    assert claims[0].position_start == 0
    assert claims[0].position_end == len(claims[0].original_claim)
    assert claims[1].claim_type == "NUMERICAL"


def test_deduplicates_and_rejects_short_or_unknown_types():
    service = make_service(
        [
            {"original_claim": "Method A achieved 92% accuracy on the benchmark.", "claim_type": "MADE_UP"},
            {"original_claim": "Method A achieved 92% accuracy on the benchmark.", "claim_type": "NUMERICAL"},
            {"original_claim": "too short", "claim_type": "FACTUAL"},
        ]
    )
    claims = service.extract("Method A achieved 92% accuracy on the benchmark.")
    assert len(claims) == 1
    assert claims[0].claim_type == "FACTUAL"


def test_respects_max_claims():
    items = [
        {"original_claim": f"Claim number {index} states a factual result.", "claim_type": "FACTUAL"}
        for index in range(1, 8)
    ]
    text = " ".join(item["original_claim"] for item in items)
    claims = make_service(items, max_claims=3).extract(text)
    assert len(claims) == 3


def test_parses_fenced_json_and_claim_type_alias():
    def handler(system: str, user: str) -> str:
        return '```json\n{"claims": [{"claim": "Aegis test claim number one.", "claim_type": "factual"}]}\n```'

    claims = ClaimExtractionService(ScriptedLLM(handler)).extract(
        "Aegis test claim number one is present here."
    )
    assert len(claims) == 1
    assert claims[0].normalized_claim == "Aegis test claim number one."


def test_find_span_handles_case_and_whitespace():
    assert find_span("The Method achieved 92%.", "method achieved") == (4, 19)
    assert find_span("one   two", "one two") == (None, None)


def test_raises_on_unparseable_model_output():
    def handler(system: str, user: str) -> str:
        return "I think there are three claims, but I will not return JSON."

    with pytest.raises(ValueError):
        ClaimExtractionService(ScriptedLLM(handler)).extract(TEXT)
