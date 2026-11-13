"""Test doubles: a scripted LLM and fixed embeddings, so the gate runs with no network."""

from __future__ import annotations

from datetime import date, datetime

from asof.corpus import ClauseVersion, Corpus, load_corpus
from asof.llm import LLMError, LLMResult
from asof.retriever import RetrievedClause
from asof.schemas import ClaimVerdict, ExtractedClaim, ExtractionResult, JudgeResult, LedgerAnswer, LedgerSql, RewriteResult


class ScriptedLLM:
    """Returns queued replies per schema, in order. An Exception in the queue is raised."""

    info = "scripted:test"

    def __init__(self, extract=(), judge=(), rewrite=(), tools=(), sql=(), answer=()):
        self.queues = {ExtractionResult: list(extract), JudgeResult: list(judge), RewriteResult: list(rewrite),
                       LedgerSql: list(sql), LedgerAnswer: list(answer)}
        self.tool_replies = list(tools)  # AIMessages for the investigate agent; none queued means "no tool calls"
        self.calls: list[tuple[type, list]] = []

    def tool_round(self, messages, tools):
        from langchain_core.messages import AIMessage

        self.calls.append(("tools", messages))
        if not self.tool_replies:
            return AIMessage(content="nothing to search")
        reply = self.tool_replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply

    def structured(self, schema, messages, choices=None):
        self.calls.append((schema, messages))
        queue = self.queues[ExtractionResult if issubclass(schema, ExtractionResult) else schema]  # bank schema too
        if not queue:
            raise LLMError(f"no scripted reply left for {schema.__name__}")
        reply = queue.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return LLMResult(reply, 5, 10, 10, 1)


class ZeroEmbeddings:
    """384 zeros for everything; retrieval is patched or ordering does not matter."""

    def embed_query(self, text):
        return [0.0] * 384

    def embed_documents(self, texts):
        return [[0.0] * 384 for _ in texts]


def claims(*items) -> ExtractionResult:
    return ExtractionResult(claims=[ExtractedClaim(text=t, area=a, claim_type=k) for t, a, k in items])


def verdict(no, v, clause_id=None, quote=None, reason="r", conflict=False) -> ClaimVerdict:
    return ClaimVerdict(claim_no=no, verdict=v, clause_id=clause_id, quoted_span=quote, situation_conflict=conflict,
                        reason=reason)


def judge(*vs) -> JudgeResult:
    return JudgeResult(verdicts=list(vs))


def version_in_force(corpus: Corpus, clause_id: str, on: date) -> ClauseVersion | None:
    """Pure-Python reference for the Db2 as-of query: the clause version in force on a date, for tests and eval checks."""
    c = next((x for x in corpus.clauses if x.clause_id == clause_id), None)
    if c is None:
        return None
    return next((v for v in c.versions if v.bus_start <= on < v.bus_end), None)


def clause(clause_id: str, on: date, distance: float = 0.3) -> RetrievedClause:
    corpus = load_corpus()
    c = next(x for x in corpus.clauses if x.clause_id == clause_id)
    v = version_in_force(corpus, clause_id, on)
    return RetrievedClause(clause_id, c.area, c.title, v.version_label, v.clause_text, v.rule, v.bus_start,
                           v.bus_end, datetime(2026, 11, 6, 4, 0, 0), distance)
