"""The gate: check an AI assistant's draft against the policy in force on a date.

    extract claims -> retrieve clauses as of the date (Db2) -> judge all claims in one call
    -> verbatim-quote rule -> deterministic rule check -> decide -> (rewrite + re-check once)
    -> append to the hash-chained ledger (Db2)

Decisions:
    PASS       every claim SUPPORTED (or no policy claims); the draft goes out with references
    CORRECTED  a claim was CONTRADICTED; the answer was rewritten from clause text and the
               rewrite passed a full re-check
    ESCALATED  a claim is NOT_COVERED and none is CONTRADICTED, the rewrite did not pass, there
               were too many claims, or anything failed; the customer gets a holding reply and a
               person reviews it

The gate fails closed: any exception becomes ESCALATED, and if the ledger cannot record the
decision the answer is withheld.
"""

from __future__ import annotations

import html
import logging
import re
import time
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

import ibm_db_dbi
from langchain_core.embeddings import Embeddings

from . import db, ledger
from .llm import LLMClient, LLMError
from .prompts import PROMPT_VERSION, judge_messages, rewrite_messages, extract_messages
from .redact import redact
from .retriever import RetrievedClause, clauses_as_of
from .rules import RuleClause, check as rule_check
from .schemas import MAX_CLAIMS, ExtractionResult, JudgeResult, RewriteResult

log = logging.getLogger(__name__)

Decision = Literal["PASS", "CORRECTED", "ESCALATED"]
HOLDING_REPLY = ("Thanks for your patience. A specialist will confirm what our policy says for your dates "
                 "and get back to you shortly.")
MIN_QUOTE_CHARS = 12
MAX_REWRITE_CHARS = 3500
_CAP = {"text": 400, "quote": 400, "reason": 200, "detail": 200}


class TooManyClaims(Exception):
    pass


@dataclass(frozen=True)
class GateRequest:
    question: str
    draft_answer: str
    as_of: date
    doc_id: str
    channel: str = "api"


@dataclass
class ClaimOutcome:
    claim_no: int
    text: str
    area: str
    claim_type: str
    verdict: str
    llm_verdict: str | None
    rule_check: str
    rule_details: list[str]
    clause: RetrievedClause | None
    quoted_span: str | None
    reason: str
    candidates: list[RetrievedClause] = field(default_factory=list)

    def as_json(self, pass_no: int) -> dict[str, Any]:
        c = self.clause
        return {
            "pass": pass_no, "claim_no": self.claim_no, "text": self.text[: _CAP["text"]], "area": self.area,
            "claim_type": self.claim_type, "verdict": self.verdict, "llm_verdict": self.llm_verdict,
            "rule_check": self.rule_check, "rule_details": [d[: _CAP["detail"]] for d in self.rule_details[:3]],
            "clause_id": c.clause_id if c else None, "clause_version": c.version_label if c else None,
            "clause_bus_start": c.bus_start.isoformat() if c else None,
            "clause_sys_start": c.sys_start.isoformat(sep=" ") if c else None,
            "distance": round(c.distance, 6) if c else None,
            "quoted_span": self.quoted_span[: _CAP["quote"]] if self.quoted_span else None,
            "reason": self.reason[: _CAP["reason"]],
        }


@dataclass
class GateResult:
    request_id: str
    decision: Decision
    reason_code: str
    final_answer: str
    claims: list[ClaimOutcome]
    rewrite_claims: list[ClaimOutcome]
    rewrite: str | None
    latency_ms: int
    model_info: str
    ledger_id: int | None = None
    row_hash: str | None = None
    released: bool = True
    error: str | None = None


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", html.unescape(text))
    text = text.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-"}))
    text = re.sub(r"\s+", " ", text).strip().strip("\"'").rstrip(".,;:!?…").strip()
    return text.casefold()


def quote_is_verbatim(span: str | None, clause_text: str) -> bool:
    """The judge's quote must be a real substring of the clause (case and spacing aside)."""
    if not span:
        return False
    s = normalise(span)
    return len(s) >= MIN_QUOTE_CHARS and s in normalise(clause_text)


def clause_sentences(clauses) -> list[str]:
    """Every sentence of the given clauses, the only quotes a grammar-constrained judge may give."""
    out: list[str] = []
    for c in clauses:
        for sentence in re.split(r"(?<=[.!?])\s+", c.clause_text.strip()):
            if len(sentence) >= MIN_QUOTE_CHARS and sentence not in out:
                out.append(sentence)
    return out


def references(claims: list[ClaimOutcome]) -> str:
    seen: dict[str, RetrievedClause] = {}
    for c in claims:
        if c.clause and c.clause.clause_id not in seen:
            seen[c.clause.clause_id] = c.clause
    if not seen:
        return ""
    refs = ", ".join(f"{c.clause_id} {c.version_label} (in effect from {c.bus_start.isoformat()})" for c in seen.values())
    return f"\n\nPolicy references: {refs}."


class Gate:
    def __init__(self, llm: LLMClient, embeddings: Embeddings, connect: Callable[[], ibm_db_dbi.Connection],
                 schema: str = db.SCHEMA, k: int = 4):
        self.llm = llm
        self.embeddings = embeddings
        self.connect = connect
        self.schema = schema
        self.k = k

    # ---- one full check of a text -------------------------------------------------------
    def evaluate(self, question: str, answer: str, as_of: date, doc_id: str) -> list[ClaimOutcome]:
        extracted = self.llm.structured(ExtractionResult, extract_messages(question, answer)).value.claims
        if len(extracted) > MAX_CLAIMS:
            raise TooManyClaims(f"{len(extracted)} claims")
        if not extracted:
            return []
        vectors = self.embeddings.embed_documents([c.text for c in extracted])
        conn = self.connect()
        try:
            per_claim = [clauses_as_of(conn, v, as_of, doc_id, self.k, schema=self.schema) for v in vectors]
        finally:
            conn.close()

        pool: dict[str, RetrievedClause] = {}
        for found in per_claim:
            for c in found:
                pool.setdefault(c.clause_id, c)
        if not pool:
            return [ClaimOutcome(i, c.text, c.area, c.claim_type, "NOT_COVERED", None, "NOT_APPLICABLE", [], None,
                                 None, f"no policy clause is in force on {as_of.isoformat()}")
                    for i, c in enumerate(extracted, start=1)]

        judged = self.llm.structured(JudgeResult, judge_messages(as_of, [c.text for c in extracted],
                                                                 [c.view() for c in pool.values()]),
                                     choices={"clause_id": list(pool), "quoted_span": clause_sentences(pool.values())}).value
        by_no = {v.claim_no: v for v in judged.verdicts}
        outcomes = []
        for i, (claim, found) in enumerate(zip(extracted, per_claim, strict=True), start=1):
            outcomes.append(self._settle(i, claim, found, pool, by_no.get(i)))
        return outcomes

    def _settle(self, no, claim, found, pool, v) -> ClaimOutcome:
        base = dict(claim_no=no, text=claim.text, area=claim.area, claim_type=claim.claim_type, candidates=found)
        if v is None:
            return ClaimOutcome(**base, verdict="NOT_COVERED", llm_verdict=None, rule_check="NOT_APPLICABLE",
                                rule_details=[], clause=None, quoted_span=None, reason="the judge returned no verdict")
        clause = pool.get(v.clause_id) if v.clause_id else None
        verdict, reason, span = v.verdict, v.reason, v.quoted_span
        if verdict != "NOT_COVERED":
            if clause is None:
                verdict, reason = "NOT_COVERED", f"cited clause {v.clause_id!r} was not among the clauses in force"
            elif not quote_is_verbatim(span, clause.clause_text):
                verdict, reason = "NOT_COVERED", "the quoted text does not appear in the cited clause"
        if verdict == "NOT_COVERED":
            return ClaimOutcome(**base, verdict="NOT_COVERED", llm_verdict=v.verdict, rule_check="NOT_APPLICABLE",
                                rule_details=[], clause=None, quoted_span=None, reason=reason)

        candidates = [RuleClause(c.clause_id, c.rule) for c in found] + [RuleClause(clause.clause_id, clause.rule)]
        rule = rule_check(claim.text, RuleClause(clause.clause_id, clause.rule), candidates)
        if rule.clause_id and rule.clause_id in pool:
            clause, span = pool[rule.clause_id], None
        if rule.status == "MISMATCH":
            if verdict == "SUPPORTED":
                reason = "rule check overrides the judge: " + "; ".join(rule.details)
            verdict = "CONTRADICTED"
        return ClaimOutcome(**base, verdict=verdict, llm_verdict=v.verdict, rule_check=rule.status,
                            rule_details=list(rule.details), clause=clause, quoted_span=span, reason=reason)

    # ---- the decision ---------------------------------------------------------------------
    def check(self, req: GateRequest) -> GateResult:
        started = time.monotonic()
        request_id = str(uuid.uuid4())
        q = redact(req.question)
        d = redact(req.draft_answer)
        first: list[ClaimOutcome] = []
        second: list[ClaimOutcome] = []
        rewrite: str | None = None
        error: str | None = None
        try:
            first = self.evaluate(q.text, d.text, req.as_of, req.doc_id)
            decision, reason, final = self._decide(first, req.draft_answer)
            if decision == "REWRITE":
                rewrite = self._rewrite(q.text, d.text, req.as_of, first)
                second = self.evaluate(q.text, rewrite, req.as_of, req.doc_id)
                if second and all(c.verdict == "SUPPORTED" for c in second):
                    decision, reason, final = "CORRECTED", "CORRECTED_FROM_CLAUSES", rewrite + references(second)
                else:
                    decision, reason, final = "ESCALATED", "CORRECTION_FAILED", HOLDING_REPLY
        except TooManyClaims as exc:
            decision, reason, final, error = "ESCALATED", "TOO_MANY_CLAIMS", HOLDING_REPLY, str(exc)
        except (LLMError, db.DatabaseError) as exc:
            decision, reason, final, error = "ESCALATED", "ERROR_FAIL_CLOSED", HOLDING_REPLY, str(exc)[:300]
            log.warning("gate failed closed (%s): %s", type(exc).__name__, error)
        except Exception as exc:  # noqa: BLE001 - anything unexpected must still fail closed
            decision, reason, final, error = "ESCALATED", "ERROR_FAIL_CLOSED", HOLDING_REPLY, type(exc).__name__
            log.exception("gate failed closed on an unexpected error")

        result = GateResult(request_id, decision, reason, final, first, second, rewrite,
                            int((time.monotonic() - started) * 1000), self.llm.info, error=error)
        self._record(req, q.text, d.text, result, q.counts, d.counts)
        return result

    def _decide(self, claims: list[ClaimOutcome], draft: str) -> tuple[str, str, str]:
        """A contradiction means the clauses hold the right answer, so try a rewrite from them
        (it may only use clause facts, which also drops unsupported details) and release it
        only if it passes a full re-check. Claims no clause covers, with nothing contradicted,
        mean the policy does not answer the question: a person has to."""
        if not claims:
            return "PASS", "NO_POLICY_CLAIMS", draft
        if any(c.verdict == "CONTRADICTED" for c in claims):
            return "REWRITE", "", ""
        if any(c.verdict == "NOT_COVERED" for c in claims):
            return "ESCALATED", "NOT_COVERED", HOLDING_REPLY
        return "PASS", "ALL_SUPPORTED", draft + references(claims)

    def _rewrite(self, question: str, draft: str, as_of: date, claims: list[ClaimOutcome]) -> str:
        clauses: dict[str, RetrievedClause] = {}
        for c in claims:
            if c.clause:
                clauses.setdefault(c.clause.clause_id, c.clause)
        problems = [(c.text, c.verdict, c.reason) for c in claims if c.verdict != "SUPPORTED"]
        text = self.llm.structured(RewriteResult, rewrite_messages(as_of, question, draft,
                                                                   [c.view() for c in clauses.values()],
                                                                   problems)).value.answer.strip()
        if not text or len(text) > MAX_REWRITE_CHARS:
            raise LLMError("rewrite was empty or too long")
        return text

    def _record(self, req: GateRequest, q_red: str, d_red: str, result: GateResult, q_counts, d_counts) -> None:
        verdicts = {
            "version": 1, "prompt_version": PROMPT_VERSION, "as_of": req.as_of.isoformat(),
            "claims": [c.as_json(1) for c in result.claims] + [c.as_json(2) for c in result.rewrite_claims],
            "rewrite": result.rewrite[:MAX_REWRITE_CHARS] if result.rewrite else None,
            "redactions": {"question": q_counts, "draft": d_counts},
            "error": result.error,
        }
        entry = ledger.LedgerEntry(
            request_id=result.request_id, channel=req.channel, doc_id=req.doc_id, as_of=req.as_of,
            # The caller gets the answer as written; the ledger keeps the redacted form.
            question_redacted=q_red, draft_redacted=d_red, final_answer=redact(result.final_answer).text[:4000],
            decision=result.decision, reason_code=result.reason_code, model_info=result.model_info[:200],
            prompt_version=PROMPT_VERSION, latency_ms=result.latency_ms, verdicts=verdicts,
        )
        try:
            conn = self.connect()
            try:
                appended = ledger.append(conn, entry, self.schema)
            finally:
                conn.close()
            result.ledger_id, result.row_hash = appended.ledger_id, appended.row_hash
        except Exception as exc:  # noqa: BLE001 - no record, no release
            log.error("ledger append failed; answer withheld: %s", exc)
            result.released = False
            result.decision, result.reason_code, result.final_answer = "ESCALATED", "LEDGER_UNAVAILABLE", HOLDING_REPLY
            result.error = f"ledger unavailable: {str(exc)[:200]}"
