"""Deterministic numerical consistency checks."""

from __future__ import annotations

from app.models.domain import PassageCandidate
from app.services.numerical_verifier import analyze_numerics, extract_mentions


def passage(text: str, page: int = 1, pid: int = 10) -> PassageCandidate:
    return PassageCandidate(
        passage_id=pid,
        document_id=1,
        document_title="Source paper",
        filename="paper.pdf",
        passage_text=text,
        page_number=page,
        passage_index=0,
        retrieval_score=4.0,
    )


def test_layer_count_discrepancy_is_reported():
    analysis = analyze_numerics(
        "The Transformer encoder consists of 8 identical layers.",
        [passage("The encoder is composed of a stack of N = 6 identical layers.")],
    )
    assert analysis is not None
    assert "8 identical layers" in analysis
    assert "6 identical layers" in analysis


def test_matching_bleu_value_is_reported_as_consistent():
    analysis = analyze_numerics(
        "The model achieves 28.4 BLEU on the translation task.",
        [passage("Our model achieves 28.4 BLEU on the WMT 2014 English-to-German task.")],
    )
    assert analysis is not None
    assert "matching value" in analysis.lower()


def test_parameter_entity_mismatch_is_reported():
    source = (
        "BERTBASE (L=12, H=768, A=12, Total Parameters=110M) and "
        "BERTLARGE (L=24, H=1024, A=16, Total Parameters=340M)."
    )
    analysis = analyze_numerics("BERT-base contains 340 million parameters.", [passage(source)])
    assert analysis is not None
    assert "340" in analysis
    assert "110" in analysis


def test_missing_numeric_unit_is_reported():
    analysis = analyze_numerics(
        "The method improves accuracy by 50%.",
        [passage("The method improves BLEU by 2.1 points.")],
    )
    assert analysis is not None
    assert "50%" in analysis
    assert "no matching percent" in analysis.lower()


def test_no_numbers_returns_none():
    assert analyze_numerics("The model uses attention.", [passage("Attention is used.")]) is None


def test_extract_mentions_normalizes_parameter_counts():
    mentions = extract_mentions("BERTBASE has 110M parameters.")
    assert any(item.unit == "million parameters" and item.value == 110 for item in mentions)
