"""Lexical retrieval tests with a fake repository."""

from __future__ import annotations

from app.models.domain import ExtractedClaim, PassageCandidate
from app.services.evidence_retrieval import LexicalRetrievalBackend, expand_tokens, tokenize


class FakeRepository:
    def __init__(self, candidates: list[PassageCandidate]) -> None:
        self.candidates = candidates
        self.calls: list[tuple[list[int], list[str]]] = []

    def candidate_passages(
        self,
        document_ids: list[int] | None,
        tokens: list[str],
        limit: int = 500,
        source_type: str | None = None,
    ):
        self.calls.append((document_ids, tokens))
        return self.candidates


CLAIM = ExtractedClaim(
    original_claim="The coating reduced manufacturing cost by 15%.",
    normalized_claim="The coating reduced manufacturing cost by 15%.",
    claim_type="NUMERICAL",
)


def candidate(pid: int, text: str) -> PassageCandidate:
    return PassageCandidate(
        passage_id=pid,
        document_id=1,
        document_title="Study",
        filename="study.txt",
        passage_text=text,
        page_number=1,
        passage_index=pid,
    )


def test_tokenize_removes_stopwords_and_duplicates():
    tokens = tokenize("The coating, the coating and manufacturing cost by 15%")
    assert tokens == ["coating", "manufacturing", "cost", "15%"]


def test_expansion_terms_survive_the_prefilter_cap():
    claim = ExtractedClaim(
        original_claim="LoRA stores a complete fine-tuned model copy for every task.",
        normalized_claim="LoRA stores a complete fine-tuned model copy for every task.",
        claim_type="FACTUAL",
    )
    repository = FakeRepository([])
    LexicalRetrievalBackend(repository, top_k=3).retrieve(claim, [1])
    _, tokens = repository.calls[0]
    assert "checkpoint" in tokens or "weights" in tokens
    assert len(tokens) <= 16


def test_retrieval_ranks_relevant_passage_first():
    repository = FakeRepository(
        [
            candidate(1, "Unrelated text about solar panel installation."),
            candidate(2, "The dual-layer coating reduced manufacturing cost by 15% versus baseline."),
            candidate(3, "Costs were measured in a controlled production study."),
        ]
    )
    backend = LexicalRetrievalBackend(repository, top_k=2)
    results = backend.retrieve(CLAIM, [1])
    assert results[0].passage_id == 2
    assert results[0].retrieval_score > 0
    assert len(results) <= 2


def test_retrieval_returns_empty_without_documents_or_tokens():
    backend = LexicalRetrievalBackend(FakeRepository([]), top_k=3)
    assert backend.retrieve(CLAIM, []) == []
    empty_claim = ExtractedClaim(original_claim="the of", normalized_claim="the of", claim_type="FACTUAL")
    assert backend.retrieve(empty_claim, [1]) == []
