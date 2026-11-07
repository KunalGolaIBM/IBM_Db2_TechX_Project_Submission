"""Db2-backed lexical evidence retrieval.

The retrieval interface is intentionally narrow so a native Db2 vector search
backend can be added later without changing the verification pipeline.
"""

from __future__ import annotations

import math
import re
from typing import Protocol

from app.db.repository import Db2Repository
from app.models.domain import ExtractedClaim, PassageCandidate

_TOKEN = re.compile(r"[a-z0-9]+(?:[.\-/%][a-z0-9]+)*%?")
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by",
    "can", "could", "did", "do", "does", "for", "from", "had", "has", "have",
    "how", "in", "into", "is", "it", "its", "may", "might", "more", "most",
    "not", "of", "on", "or", "our", "than", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "to", "was", "we",
    "were", "what", "when", "where", "which", "while", "who", "will", "with",
    "would", "using", "used", "use", "study", "paper", "results", "also",
}

# Small, explainable expansion map for evaluation/retrieval. It targets terms
# where claims use a different surface form from the paper.
_QUERY_EXPANSION = {
    "scratch": ("fine-tune", "pre-train", "initialized"),
    "store": ("checkpoint", "storage", "weights"),
    "stores": ("checkpoint", "storage", "weights"),
    "stored": ("checkpoint", "storage", "weights"),
    "copy": ("checkpoint", "weights", "parameters"),
    "copies": ("checkpoint", "weights", "parameters"),
    "complete": ("full",),
    "full": ("complete",),
    "reduce": ("reduction", "lower"),
    "reduces": ("reduction", "lower"),
    "improve": ("improvement", "better"),
    "improves": ("improvement", "better"),
    "convolutional": ("convolution", "convolutions"),
    "convolution": ("convolutional", "convolutions"),
    "convolutions": ("convolution", "convolutional"),
    "objective": ("objectives",),
    "objectives": ("objective",),
}


class RetrievalBackend(Protocol):
    def retrieve(
        self,
        claim: ExtractedClaim,
        document_ids: list[int],
        *,
        corpus_wide: bool = False,
        source_type: str | None = None,
        top_k: int | None = None,
    ) -> list[PassageCandidate]: ...


def tokenize(text: str) -> list[str]:
    tokens = [token for token in _TOKEN.findall(text.lower()) if len(token) >= 3]
    seen: set[str] = set()
    ordered: list[str] = []
    for token in tokens:
        if token in _STOPWORDS or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered


def expand_tokens(tokens: list[str]) -> list[str]:
    expanded = list(tokens)
    seen = set(tokens)
    for token in tokens:
        for extra in _QUERY_EXPANSION.get(token, ()):
            for part in _TOKEN.findall(extra.lower()):
                if part not in seen and len(part) >= 3:
                    seen.add(part)
                    expanded.append(part)
    return expanded


def _bm25_scores(claim_tokens: list[str], passages: list[list[str]]) -> list[float]:
    if not passages:
        return []
    total_docs = len(passages)
    avg_len = sum(len(doc) for doc in passages) / total_docs or 1.0
    document_frequency = {
        token: sum(1 for doc in passages if token in doc) for token in claim_tokens
    }
    k1, b = 1.5, 0.75
    scores: list[float] = []
    for doc in passages:
        length = len(doc) or 1
        score = 0.0
        for token in claim_tokens:
            frequency = doc.count(token)
            if frequency == 0:
                continue
            df = document_frequency[token]
            idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
            denominator = frequency + k1 * (1 - b + b * length / avg_len)
            score += idf * (frequency * (k1 + 1)) / denominator
        scores.append(score)
    return scores


class LexicalRetrievalBackend:
    """BM25 over passages retrieved from Db2 with a SQL lexical prefilter."""

    def __init__(self, repository: Db2Repository, top_k: int = 6) -> None:
        self.repository = repository
        self.top_k = top_k

    def retrieve(
        self,
        claim: ExtractedClaim,
        document_ids: list[int],
        *,
        corpus_wide: bool = False,
        source_type: str | None = None,
        top_k: int | None = None,
    ) -> list[PassageCandidate]:
        tokens = expand_tokens(
            tokenize(f"{claim.original_claim} {claim.normalized_claim}")
        )
        if not tokens or (not corpus_wide and not document_ids):
            return []
        # Keep expansion terms inside the prefilter cap; they are appended to the
        # claim tokens and would otherwise be truncated for longer claims.
        candidates = self.repository.candidate_passages(
            None if corpus_wide else document_ids,
            tokens[:16],
            source_type=source_type,
        )
        if not candidates:
            return []
        tokenized = [tokenize(candidate.passage_text) for candidate in candidates]
        scores = _bm25_scores(tokens, tokenized)
        ranked = sorted(
            zip(candidates, scores), key=lambda item: item[1], reverse=True
        )
        limit = top_k or self.top_k
        results: list[PassageCandidate] = []
        for candidate, score in ranked:
            if score <= 0:
                continue
            candidate.retrieval_score = float(score)
            results.append(candidate)
            if len(results) >= limit:
                break
        return results


def build_retrieval_backend(repository: Db2Repository, settings) -> RetrievalBackend:
    backend = settings.aegis_retrieval_backend.lower()
    if backend != "lexical":
        raise ValueError(
            f"Unsupported retrieval backend '{backend}'. Only 'lexical' is implemented."
        )
    return LexicalRetrievalBackend(repository, top_k=settings.llm_evidence_top_k)
