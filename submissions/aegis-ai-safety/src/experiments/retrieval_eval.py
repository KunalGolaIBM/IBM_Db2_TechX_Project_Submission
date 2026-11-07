"""Full-corpus BM25 index for reproducible SciFact evaluation.

The production API uses a Db2 SQL prefilter to bound query work. For a 5k-document
benchmark, loading the dataset passages from Db2 once and ranking them in memory
is faster and avoids prefilter misses. The passages still originate from Db2.
"""

from __future__ import annotations

import time

from app.db.repository import Db2Repository
from app.models.domain import ExtractedClaim, PassageCandidate
from app.services.evidence_retrieval import _bm25_scores, expand_tokens, tokenize


class CorpusBM25Index:
    def __init__(self, repository: Db2Repository, source_type: str) -> None:
        started = time.monotonic()
        self.passages: list[PassageCandidate] = repository.passages_for_source(source_type)
        self.tokens = [tokenize(passage.passage_text) for passage in self.passages]
        self.load_seconds = time.monotonic() - started

    def retrieve(self, claim: ExtractedClaim, top_k: int = 10) -> list[PassageCandidate]:
        claim_tokens = expand_tokens(
            tokenize(f"{claim.original_claim} {claim.normalized_claim}")
        )
        if not claim_tokens or not self.passages:
            return []
        scores = _bm25_scores(claim_tokens, self.tokens)
        ranked = sorted(zip(self.passages, scores), key=lambda item: item[1], reverse=True)
        results: list[PassageCandidate] = []
        for passage, score in ranked:
            if score <= 0:
                continue
            passage.retrieval_score = float(score)
            results.append(passage)
            if len(results) >= top_k:
                break
        return results
