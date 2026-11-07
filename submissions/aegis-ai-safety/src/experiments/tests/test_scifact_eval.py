"""SciFact loader and retrieval-index tests (no Db2 or LLM required)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.models.domain import ExtractedClaim, PassageCandidate
from experiments.retrieval_eval import CorpusBM25Index
from experiments.run_scifact_eval import _select_claims
from experiments.scifact_loader import ScifactClaim, load_scifact_claims, load_scifact_corpus


def test_load_corpus_and_claims(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    claims = tmp_path / "claims.jsonl"
    corpus.write_text(
        "\n".join(
            [
                json.dumps({"doc_id": 1, "title": "Paper one", "abstract": ["A claim.", "More."]}),
                json.dumps({"doc_id": 2, "title": "Paper two", "abstract": "Single string."}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    claims.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": 10,
                        "claim": "Paper one supports this.",
                        "evidence": {"1": [{"label": "SUPPORT", "sentences": [0]}]},
                        "cited_doc_ids": [1],
                    }
                ),
                json.dumps(
                    {
                        "id": 11,
                        "claim": "No evidence here.",
                        "evidence": {},
                        "cited_doc_ids": [2],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    documents = load_scifact_corpus(corpus)
    assert len(documents) == 2
    assert documents[0].text.startswith("Paper one")
    loaded_claims = load_scifact_claims(claims)
    assert loaded_claims[0].gold_label == "SUPPORTED"
    assert loaded_claims[1].gold_label == "INSUFFICIENT_EVIDENCE"
    assert loaded_claims[0].cited_doc_ids == (1,)


def test_subset_selection_does_not_use_gold_labels():
    claims = [
        ScifactClaim(str(i), f"claim {i}", label, (), ())
        for i, label in enumerate(
            ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE", "SUPPORTED"], start=1
        )
    ]
    relabeled = [
        ScifactClaim(claim.claim_id, claim.claim, "INSUFFICIENT_EVIDENCE", (), ())
        for claim in claims
    ]
    assert [c.claim_id for c in _select_claims(claims, 3)] == [
        c.claim_id for c in _select_claims(relabeled, 3)
    ]
    assert [c.claim_id for c in _select_claims(claims, 3)] == ["1", "2", "3"]


def test_corpus_bm25_index_ranks_relevant_passage():
    class FakeRepository:
        def passages_for_source(self, source_type):
            return [
                PassageCandidate(
                    passage_id=1,
                    document_id=1,
                    document_title="A",
                    filename="a",
                    passage_text="The encoder uses six identical layers.",
                    page_number=1,
                    passage_index=0,
                ),
                PassageCandidate(
                    passage_id=2,
                    document_id=2,
                    document_title="B",
                    filename="b",
                    passage_text="A completely unrelated sentence about biology.",
                    page_number=1,
                    passage_index=0,
                ),
            ]

    index = CorpusBM25Index(FakeRepository(), "scifact")
    results = index.retrieve(
        ExtractedClaim(
            original_claim="The encoder uses six identical layers.",
            normalized_claim="The encoder uses six identical layers.",
            claim_type="FACTUAL",
        ),
        top_k=1,
    )
    assert results[0].passage_id == 1
