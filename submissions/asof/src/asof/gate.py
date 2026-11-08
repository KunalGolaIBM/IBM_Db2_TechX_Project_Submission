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
import unicodedata
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

import ibm_db_dbi
from langchain_core.embeddings import Embeddings

from . import db, ledger
from .anchor import AnchorLog
from .domains import AIRLINE, DOMAINS, Domain
from .llm import LLMError, ModelClient
from .prompts import extract_messages, judge_messages, rewrite_messages
from .redact import redact
from .retriever import RetrievedClause, clauses_as_of
from .rules import RuleClause, RuleResult, extract_quantities, situation_conflicts
from .rules import _close as same_amount
from .rules import check as rule_check
from .schemas import MAX_CLAIMS, ClaimVerdict, ExtractedClaim, JudgeResult, RewriteResult

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
    requested_by: str | None = None  # the API user, when ASOF_AUTH=users; recorded in the hashed verdicts
    route: dict[str, Any] | None = None  # how the router chose doc_id (asof/router.py), when the caller asked it to


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
    investigation: list[dict[str, Any]] = field(default_factory=list)  # the agent's tool calls, if any
    unchecked: list[str] = field(default_factory=list)  # details in the draft that no extracted claim stated
    redactions: dict[str, dict[str, int]] = field(default_factory=dict)  # what redaction removed, per field


# "Feel free to call" and "toll-free" are not prices. Found when the demo assistant's "feel free to reach
# out" was held as an unchecked $0; the rule checker still reads "the bag is free" as $0. An allow-list,
# not every "<word>-free": "fee-free", "charge-free" and "penalty-free" are price claims and must be checked.
NOT_A_PRICE = re.compile(r"\bfeel free\b|\b(?:toll|hands|worry|hassle|care|stress|trouble)-free\b", re.I)


def unchecked_details(text: str, claim_texts: Sequence[str], context: str = "") -> list[str]:
    """Amounts, percentages, durations and counts in `text` that no extracted claim states.

    Extraction is a model call, so it can skip a detail (or be talked into skipping one). This is
    the deterministic backstop: every number the draft states must reach the claim check, unless it
    only repeats the customer's own question (`context`), such as "your flight was 4 hours late".
    """
    text = NOT_A_PRICE.sub(" ", text)
    stated = [f for c in claim_texts for q in extract_quantities(c) for f in q.forms]
    stated += [f for q in extract_quantities(context) for f in q.forms]
    return [q.text for q in extract_quantities(text)
            if not any(u == su and same_amount(v, sv, u) for u, v in q.forms for su, sv in stated)]


def invented_details(text: str, claim_texts: Sequence[str]) -> list[str]:
    """Amounts, percentages, durations and counts that a claim states differently from `text`.

    The extractor is told to keep the answer's own numbers and never correct anything. A claim whose
    number differs from every number of the same kind in the answer, such as the customer's own "11 kg"
    in place of the answer's "under 8 kg", is no longer a claim of the answer, so its verdict says
    nothing about what the answer tells the customer. Only numbers of a kind the answer also states are
    compared: "a pet" written as "one pet", or "thirty days" as "30 days", is a paraphrase, not a change.
    Deterministic, and only ever a reason to hold the answer for a person.
    """
    said = [f for q in extract_quantities(NOT_A_PRICE.sub(" ", text)) for f in q.forms]
    kinds = {u for u, _ in said}
    out = []
    for claim in claim_texts:
        for q in extract_quantities(NOT_A_PRICE.sub(" ", claim)):
            if not any(u in kinds for u, _ in q.forms):
                continue
            if not any(u == su and same_amount(v, sv, u) for u, v in q.forms for su, sv in said):
                out.append(f"{q.text} (in a claim, not in the answer)")
    return out


# A premise the answer states about this customer: "because the delay was caused by weather", "since your
# bag weighs 27 kg". The judge can only test it against the question if a claim carries it.
_PREMISE = re.compile(
    r"\b(?:because(?:\s+of)?|since|given\s+that|now\s+that|seeing\s+that|due\s+to|owing\s+to)\s+(?P<body>[^.;:!?,]+)"
    r"|(?:^|[.!?]\s+|,\s*)as\s+(?P<as_body>(?:you|your|the|this|it|she|he|they)\b[^.;:!?,]+)", re.I)
# Who or what the premise is about: the customer, their booking, their account. A claim that keeps the
# premise keeps this reference; "Delays caused by weather are ..." has dropped it.
_ABOUT_CUSTOMER = re.compile(r"\b(?:you|your|yours|it|she|he|they|his|her|their)\b"
                             r"|\bthe\s+(?:delay|flight|booking|ticket|trip|bag|pet|cat|dog|account|card|wire|transfer"
                             r"|withdrawal|balance|purchase|cancellation|fare)\b", re.I)
# A sentence worth judging states something a policy decides: a number or a policy term. "Since you asked,
# here is what we found" and "As you know, we value your business" do not, and would only be held.
_POLICY_SUBSTANCE = re.compile(
    r"\d|\$|%|\b(?:fees?|fares?|charged?|charges|costs?|price|pay|paid|free|refunds?|refunded|compensation|compensated"
    r"|eligible|ineligible|entitled|qualif\w*|allowed|permitted|accepted|apply|applies|waived?|credits?|vouchers?"
    r"|cancel\w*|change[sd]?|transfer\w*|cabin|bags?|baggage|luggage|kg|weigh\w*|overdraft|wire|atm|statements?"
    r"|interest|limit|deadline|within|days?|hours?|months?|business\s+class|economy|bereavement|immediate\s+family"
    r"|documents?|certificate|control|delay(?:ed|s)?|cancelled|closure|close|balance|maintenance)\b", re.I)


def policy_terms(text: str) -> list[str]:
    """What in `text` a policy decides (fees, refunds, eligibility, deadlines), lower-cased; "amounts" for any number,
    "$" or "%". Empty when the text states nothing a policy decides."""
    found = {m.group(0).lower() for m in _POLICY_SUBSTANCE.finditer(text)}
    words = sorted(w for w in found if any(ch.isalpha() for ch in w))
    return words + (["amounts"] if any(not any(ch.isalpha() for ch in w) for w in found) else [])


# "since 1 May", "since May 2026", "since then": time, not a premise. Months only as dates, so "Mark" or
# "decisions" still start a premise.
_MONTHS = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?"
           r"|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
_NOT_A_PREMISE = re.compile(rf"^(?:{_MONTHS}\.?\s+\d|\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTHS}\b|\d{{4}}\b|then\b"
                            r"|(?:last|this|next)\s+(?:week|month|year|time)\b|yesterday\b|today\b)", re.I)
_CONTRACTIONS = ((r"\b(you|we|they)'re\b", r"\1 are"), (r"\b(it|that|there|he|she)'s\b", r"\1 is"),
                 (r"\bcan't\b", "cannot"), (r"\bwon't\b", "will not"), (r"n't\b", " not"),
                 (r"\b(you|we|they)'ve\b", r"\1 have"), (r"\b(you|we|they)'ll\b", r"\1 will"))


def _plain(text: str) -> str:
    """Lower case, straight quotes, contractions spelled out, punctuation and spacing collapsed."""
    t = normalise(text)
    for pattern, repl in _CONTRACTIONS:
        t = re.sub(pattern, repl, t)
    return " ".join(re.sub(r"[^0-9a-z$%.']+", " ", t).split())


def unstated_premises(text: str, claim_texts: Sequence[str]) -> list[str]:
    """Sentences of `text` holding a premise that no claim keeps, each copied whole from `text`.

    The extractor is told to keep what the answer says about this customer in the same claim, never as a
    general rule. When it does not ("Delays caused by weather are outside our control" from "Because the
    delay was caused by weather, ..."), the judge never sees the premise and cannot compare it with the
    question. Each such sentence is then judged as a claim of its own. A claim keeps a premise when it
    states the premise's words and still refers to the customer or their case. Every premise found is
    returned, never a capped few: the caller holds the answer if they will not all fit.
    """
    claims = [(_plain(c), bool(_ABOUT_CUSTOMER.search(c))) for c in claim_texts]
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]
    out: list[str] = []
    for sentence in sentences:
        if not _ABOUT_CUSTOMER.search(sentence) or not _POLICY_SUBSTANCE.search(sentence):
            continue
        for m in _PREMISE.finditer(sentence):
            body = (m.group("body") or m.group("as_body") or "").strip()
            if not body or _NOT_A_PREMISE.match(body) or len(body.split()) < 2:
                continue
            if any(_plain(body) in c and refers for c, refers in claims):
                continue
            if sentence not in out:
                out.append(sentence)
            break
    return out


def _premise_claim(sentence: str, extracted: Sequence[Any]) -> Any:
    """The premise sentence as a claim of the extractor's own type, in the area of the claim it overlaps
    most, or "other" when it overlaps none."""
    words = set(_plain(sentence).split())
    closest = max(extracted, key=lambda c: len(words & set(_plain(c.text).split())))
    shared = words & set(_plain(closest.text).split())
    return type(closest)(text=sentence, area=closest.area if shared else "other", claim_type=closest.claim_type)


_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-"})


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", html.unescape(text))
    text = text.translate(_QUOTES)
    text = re.sub(r"\s+", " ", text).strip().strip("\"'").rstrip(".,;:!?…").strip()
    return text.casefold()


def quote_is_verbatim(span: str | None, clause_text: str) -> bool:
    """The judge's quote must be a real substring of the clause (case and spacing aside)."""
    if not span:
        return False
    s = normalise(span)
    return len(s) >= MIN_QUOTE_CHARS and s in normalise(clause_text)


MIN_SHORT_QUOTE_CHARS = 3


def sentence_holding(span: str | None, clause_text: str) -> str | None:
    """The clause sentence that contains the quote exactly (case and spacing aside), for a quote too short
    to stand on its own, such as "$35" or "60 days"."""
    if not span:
        return None
    s = normalise(span)
    if len(s) < MIN_SHORT_QUOTE_CHARS or not re.search(r"[0-9a-z]", s):
        return None
    return next((sentence for sentence in re.split(r"(?<=[.!?])\s+", clause_text.strip())
                 if s in normalise(sentence)), None)


def contradiction_ground(span: str | None, claim_text: str, clause: RetrievedClause,
                         found: Sequence[RetrievedClause]) -> tuple[str | None, str] | None:
    """Grounds a CONTRADICTED verdict whose quote failed the verbatim rule, or returns None.

    Only for contradictions, which never release a draft: they lead to a rewrite that must pass a full
    re-check (where SUPPORTED needs a full verbatim quote again) or to ESCALATED. Grounded either by the
    cited clause's sentence that holds the judge's short exact quote, or, when the quote is not in the
    clause at all, by the deterministic rule check finding a mismatch with that clause's RULE_JSON.
    """
    sentence = sentence_holding(span, clause.clause_text)
    if sentence is not None:
        return sentence, "the judge's short quote, extended to its clause sentence"
    cited = RuleClause(clause.clause_id, clause.rule)
    rule = rule_check(claim_text, cited, [RuleClause(c.clause_id, c.rule) for c in found] + [cited])
    if rule.status == "MISMATCH" and rule.clause_id in (None, clause.clause_id):
        return None, "quote not in the clause; the rule check confirms the contradiction"
    return None


def clause_sentences(clauses: Iterable[RetrievedClause]) -> list[str]:
    """Every sentence of the given clauses, the only quotes a grammar-constrained judge may give."""
    out: list[str] = []
    for c in clauses:
        for sentence in re.split(r"(?<=[.!?])\s+", c.clause_text.strip()):
            if len(sentence) >= MIN_QUOTE_CHARS and sentence not in out:
                out.append(sentence)
    return out


def pool_of(per_claim: list[list[RetrievedClause]]) -> dict[str, RetrievedClause]:
    pool: dict[str, RetrievedClause] = {}
    for found in per_claim:
        for c in found:
            pool.setdefault(c.clause_id, c)
    return pool


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
    def __init__(self, llm: ModelClient, embeddings: Embeddings, connect: Callable[[], ibm_db_dbi.Connection],
                 schema: str = db.SCHEMA, k: int = 4, investigate: bool = True, deadline_s: float = 300.0,
                 anchors: AnchorLog | None = None):
        self.llm = llm
        self.embeddings = embeddings
        self.connect = connect
        self.schema = schema
        self.k = k
        self.investigate = investigate  # let the agent look further when a claim matches no clause
        # Whole-check budget on top of the per-call LLM deadlines: no step starts after it, so a slow
        # provider (and its fallback) cannot keep one check going indefinitely. Then it fails closed.
        self.deadline_s = deadline_s
        # Chain-head anchors outside Db2 (asof/anchor.py); None when ASOF_ANCHOR_KEY is not set.
        self.anchors = anchors

    # ---- the steps of one pass (graph nodes call these) ------------------------------------
    @staticmethod
    def domain(doc_id: str) -> Domain:
        """The domain's prompts for a document. An unknown document (the API never lets one through)
        gets the airline wording and retrieves nothing for that doc_id, so it escalates."""
        return DOMAINS.get(doc_id, AIRLINE)

    def extract(self, question: str, text: str, domain: Domain = AIRLINE) -> list[ExtractedClaim]:
        extracted = self.llm.structured(domain.extraction_schema,
                                        extract_messages(question, text, domain.extract_system)).value.claims
        if len(extracted) > MAX_CLAIMS:
            raise TooManyClaims(f"{len(extracted)} claims")
        return extracted

    @staticmethod
    def premise_claims(text: str, extracted: list[ExtractedClaim]) -> list[ExtractedClaim]:
        """Claims for the premise sentences no extracted claim kept (see unstated_premises). Together with the
        extracted claims they stay within MAX_CLAIMS, so a recorded check can never exceed what APPEND_LEDGER
        accepts; more than that holds the answer, like too many extracted claims."""
        if not extracted:
            return []
        added = unstated_premises(text, [c.text for c in extracted])
        if len(extracted) + len(added) > MAX_CLAIMS:
            raise TooManyClaims(f"{len(extracted)} claims and {len(added)} premise sentences")
        if added:
            log.info("judging %d premise sentence(s) no extracted claim kept", len(added))
        return [_premise_claim(sentence, extracted) for sentence in added]

    def retrieve(self, claims: Sequence[ExtractedClaim], as_of: date, doc_id: str) -> list[list[RetrievedClause]]:
        """Db2 tool: the clauses in force on the date, nearest first, for each claim."""
        vectors = self.embeddings.embed_documents([c.text for c in claims])
        conn = self.connect()
        try:
            return [clauses_as_of(conn, v, as_of, doc_id, self.k, schema=self.schema) for v in vectors]
        finally:
            conn.close()

    def judge(self, claims: Sequence[ExtractedClaim], per_claim: list[list[RetrievedClause]],
              pool: dict[str, RetrievedClause], as_of: date,
              numbers: list[int] | None = None, domain: Domain = AIRLINE, question: str = "") -> list[ClaimOutcome]:
        """One batched judge call over `claims`, then the verbatim-quote rule and the rule check. The judge also
        sees the (redacted) customer question, to test situation facts a claim rests on against it."""
        numbers = numbers or list(range(1, len(claims) + 1))
        if not pool:
            return [ClaimOutcome(n, c.text, c.area, c.claim_type, "NOT_COVERED", None, "NOT_APPLICABLE", [], None,
                                 None, f"no policy clause is in force on {as_of.isoformat()}", list(found))
                    for n, c, found in zip(numbers, claims, per_claim, strict=True)]
        judged = self.llm.structured(JudgeResult, judge_messages(as_of, [c.text for c in claims],
                                                                 [c.view() for c in pool.values()], domain.judge_system,
                                                                 question=question),
                                     choices={"clause_id": list(pool), "quoted_span": clause_sentences(pool.values())}).value
        by_no = {v.claim_no: v for v in judged.verdicts}
        return [self._settle(n, claim, found, pool, by_no.get(i), question)
                for i, (n, claim, found) in enumerate(zip(numbers, claims, per_claim, strict=True), start=1)]

    def evaluate(self, question: str, answer: str, as_of: date, doc_id: str) -> list[ClaimOutcome]:
        """One pass without the agent: extract, retrieve, judge, then the quote and rule checks."""
        domain = self.domain(doc_id)
        extracted = self.extract(question, answer, domain)
        if not extracted:
            return []
        per_claim = self.retrieve(extracted, as_of, doc_id)
        return self.judge(extracted, per_claim, pool_of(per_claim), as_of, domain=domain, question=question)

    def _settle(self, no: int, claim: ExtractedClaim, found: list[RetrievedClause], pool: dict[str, RetrievedClause],
                v: ClaimVerdict | None, question: str = "") -> ClaimOutcome:
        base: dict[str, Any] = dict(claim_no=no, text=claim.text, area=claim.area, claim_type=claim.claim_type,
                                    candidates=found)
        if v is None:
            return ClaimOutcome(**base, verdict="NOT_COVERED", llm_verdict=None, rule_check="NOT_APPLICABLE",
                                rule_details=[], clause=None, quoted_span=None, reason="the judge returned no verdict")
        clause = pool.get(v.clause_id) if v.clause_id else None
        verdict, reason, span = v.verdict, v.reason, v.quoted_span
        if verdict == "SUPPORTED" and v.situation_conflict:
            # The clause may say what the claim says, but for a different situation than the customer's: the
            # outcome is wrong for this customer. The flag can only make a verdict stricter, never release.
            verdict, reason = "CONTRADICTED", f"the claim assumes a situation the question states differently: {reason}"
        if verdict != "NOT_COVERED":
            if clause is None:
                verdict, reason = "NOT_COVERED", f"cited clause {v.clause_id!r} was not among the clauses in force"
            elif verdict == "CONTRADICTED" and not quote_is_verbatim(span, clause.clause_text):
                # A contradiction never releases anything: it leads to a rewrite that must pass a full
                # re-check, or to ESCALATED. So it may be grounded more narrowly than a SUPPORTED verdict:
                # by the clause sentence holding the judge's short exact quote ("$35"), or, failing that,
                # by the deterministic rule check finding the mismatch in the clause's RULE_JSON.
                grounded = contradiction_ground(span, claim.text, clause, found)
                if grounded is None:
                    verdict, reason = "NOT_COVERED", "the quoted text does not appear in the cited clause"
                else:
                    span, note = grounded
                    reason = f"{reason} ({note})" if reason else note
            elif not quote_is_verbatim(span, clause.clause_text):
                verdict, reason = "NOT_COVERED", "the quoted text does not appear in the cited clause"
        if verdict == "NOT_COVERED" or clause is None:  # no clause means NOT_COVERED (set above)
            return ClaimOutcome(**base, verdict="NOT_COVERED", llm_verdict=v.verdict, rule_check="NOT_APPLICABLE",
                                rule_details=[], clause=None, quoted_span=None, reason=reason)

        candidates = [RuleClause(c.clause_id, c.rule) for c in found] + [RuleClause(clause.clause_id, clause.rule)]
        rule = rule_check(claim.text, RuleClause(clause.clause_id, clause.rule), candidates)
        # The claim may state this customer's situation ("you arrived 10 hours late") differently from the
        # question ("2 hours late"); then it picks the wrong tier, whatever the judge said.
        conflicts = situation_conflicts(claim.text, question) if question else ()
        if conflicts:
            rule = RuleResult("MISMATCH", (*rule.details, *conflicts), rule.clause_id)
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
        """Run the check graph (see checkgraph.py) for one draft and record the decision."""
        from .checkgraph import run_check

        return run_check(self, req)

    def _decide(self, claims: list[ClaimOutcome], draft: str, unchecked: Sequence[str] = ()) -> tuple[str, str, str]:
        """A contradiction means the clauses hold the right answer, so try a rewrite from them
        (it may only use clause facts, which also drops unsupported details) and release it
        only if it passes a full re-check. A number in the draft that no claim stated was never
        checked, so the draft cannot go out as written. Claims no clause covers, with nothing
        contradicted, mean the policy does not answer the question: a person has to."""
        if any(c.verdict == "CONTRADICTED" for c in claims):
            return "REWRITE", "", ""
        if unchecked:
            return "ESCALATED", "UNCHECKED_DETAILS", HOLDING_REPLY
        if not claims:
            return "PASS", "NO_POLICY_CLAIMS", draft
        if any(c.verdict == "NOT_COVERED" for c in claims):
            return "ESCALATED", "NOT_COVERED", HOLDING_REPLY
        return "PASS", "ALL_SUPPORTED", draft + references(claims)

    def _rewrite(self, question: str, draft: str, as_of: date, claims: list[ClaimOutcome],
                 domain: Domain = AIRLINE) -> str:
        clauses: dict[str, RetrievedClause] = {}
        for c in claims:
            if c.clause:
                clauses.setdefault(c.clause.clause_id, c.clause)
        problems = [(c.text, c.verdict, c.reason) for c in claims if c.verdict != "SUPPORTED"]
        return self._rewrite_from(question, draft, as_of, list(clauses.values()), problems, domain)

    def _rewrite_from(self, question: str, draft: str, as_of: date, clauses: list[RetrievedClause],
                      problems: list[tuple[str, str, str]], domain: Domain = AIRLINE) -> str:
        """Rewrite strictly from the given clause texts (also used by the change-impact agent)."""
        text = self.llm.structured(RewriteResult, rewrite_messages(as_of, question, draft, [c.view() for c in clauses],
                                                                   problems, domain.rewrite_system)).value.answer.strip()
        if not text or len(text) > MAX_REWRITE_CHARS:
            raise LLMError("rewrite was empty or too long")
        return text

    def assess(self, req: GateRequest) -> GateResult:
        """Check a text without recording it or rewriting it (a specialist's reply, asof/review.py)."""
        from .checkgraph import run_check

        return run_check(self, req, record=False)

    def verdicts(self, req: GateRequest, result: GateResult, q_counts: dict[str, int],
                 d_counts: dict[str, int]) -> dict[str, Any]:
        """The verdicts document hashed into the ledger row for a check."""
        verdicts: dict[str, Any] = {
            "version": 1, "prompt_version": self.domain(req.doc_id).prompt_version, "as_of": req.as_of.isoformat(),
            "claims": [c.as_json(1) for c in result.claims] + [c.as_json(2) for c in result.rewrite_claims],
            "rewrite": result.rewrite[:MAX_REWRITE_CHARS] if result.rewrite else None,
            "redactions": {"question": q_counts, "draft": d_counts},
            "investigation": result.investigation[:6],
            "unchecked": result.unchecked[:20],
            "error": result.error,
        }
        if req.requested_by:
            verdicts["requested_by"] = req.requested_by[:40]
        if req.route:
            verdicts["route"] = req.route
        return verdicts

    def hold(self, req: GateRequest, reason_code: str, model_info: str) -> GateResult:
        """Record a decision held before any check ran (the router could not tell which policy applies), so it is in
        the ledger and the specialist inbox like any other held answer."""
        q, d = redact(req.question), redact(req.draft_answer)
        result = GateResult(str(uuid.uuid4()), "ESCALATED", reason_code, HOLDING_REPLY, [], [], None, 0, model_info[:200],
                            released=False)
        self._record(req, q.text, d.text, result, q.counts, d.counts)
        result.released = False  # held: the holding reply goes out, never the draft
        return result

    def _record(self, req: GateRequest, q_red: str, d_red: str, result: GateResult,
                q_counts: dict[str, int], d_counts: dict[str, int]) -> None:
        prompt_version = self.domain(req.doc_id).prompt_version
        verdicts = self.verdicts(req, result, q_counts, d_counts)
        entry = ledger.LedgerEntry(
            request_id=result.request_id, channel=req.channel, doc_id=req.doc_id, as_of=req.as_of,
            # The caller gets the answer as written; the ledger keeps the redacted form.
            question_redacted=q_red, draft_redacted=d_red, final_answer=redact(result.final_answer).text[:4000],
            decision=result.decision, reason_code=result.reason_code, model_info=result.model_info[:200],
            prompt_version=prompt_version, latency_ms=result.latency_ms, verdicts=verdicts,
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
            return
        self.anchor(appended.ledger_id, appended.row_hash)

    def anchor(self, ledger_id: int, row_hash: str) -> None:
        """Anchor a new chain head outside Db2, if anchoring is on."""
        if self.anchors is not None:
            # The decision is recorded either way. A failed anchor write is logged and shows up as unanchored
            # rows in /api/chain/anchors until the next append anchors a later head, which covers them.
            try:
                self.anchors.append(ledger_id, row_hash)
            except Exception as exc:  # noqa: BLE001
                log.error("chain-head anchor not written for ledger row %s: %s", ledger_id, exc)
