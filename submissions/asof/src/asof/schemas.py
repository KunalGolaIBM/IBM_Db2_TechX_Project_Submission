"""Typed contracts for everything an LLM returns.

Each model is strict-mode friendly: every field is required (nullable where it may be
absent), extra keys are forbidden, and enums are closed. Limits such as the claim cap
are enforced in code after parsing, because providers differ in which JSON Schema
keywords they honour.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Area = Literal[
    "bereavement",
    "cancellation",
    "change_fee",
    "baggage",
    "refund",
    "delay",
    "travel_credit",
    "pets",
    "other",
]
# The second, fictional domain: a bank's personal account fee schedule. Its claims get their
# own schema, so the airline's requests stay byte for byte what they were.
BankArea = Literal[
    "overdraft",
    "fee_refund",
    "monthly_fee",
    "foreign_transaction",
    "wire_transfer",
    "atm",
    "dispute",
    "account_closure",
    "checks",
    "other",
]
AnyArea = Literal[Area, BankArea]
ClaimType = Literal["eligibility", "amount", "deadline", "procedure", "other"]
Verdict = Literal["SUPPORTED", "CONTRADICTED", "NOT_COVERED"]

MAX_CLAIMS = 8


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExtractedClaim(_Strict):
    text: str = Field(
        description="One atomic policy claim, worded as closely as possible to the answer."
    )
    area: Area = Field(description="The policy area the claim is about.")
    claim_type: ClaimType = Field(
        description="eligibility: who or what qualifies or is allowed. amount: a price, fee, "
        "discount or compensation. deadline: a time limit or processing time. procedure: "
        "how or where to do something, or what documents are needed."
    )


class ExtractionResult(_Strict):
    claims: list[ExtractedClaim] = Field(
        description="Policy claims found in the answer. Empty if there are none."
    )


class BankExtractedClaim(ExtractedClaim):
    area: BankArea = Field(description="The fee schedule area the claim is about.")  # type: ignore[assignment]


class BankExtractionResult(ExtractionResult):
    claims: list[BankExtractedClaim] = Field(  # type: ignore[assignment]
        description="Policy claims found in the answer. Empty if there are none."
    )


class ClaimVerdict(_Strict):
    claim_no: int = Field(description="The number of the claim being judged, as given.")
    verdict: Verdict
    clause_id: str | None = Field(
        description="ID of the clause that decides the verdict. Null only for NOT_COVERED."
    )
    quoted_span: str | None = Field(
        description="Exact text copied character for character from that clause that "
        "decides the verdict. Null only for NOT_COVERED."
    )
    situation_conflict: bool = Field(
        description="True if the claim assumes something about this customer (such as their cabin, the cause "
        "or length of a delay, a weight, an account's age or balance, or how many refunds they have had) that "
        "the question states differently. False if the question agrees or does not say."
    )
    reason: str = Field(description="One short sentence explaining the verdict.")


class JudgeResult(_Strict):
    verdicts: list[ClaimVerdict] = Field(description="Exactly one verdict per claim, in order.")


class RewriteResult(_Strict):
    answer: str = Field(description="The corrected answer for the customer.")


# "Ask the ledger" (asof/askledger.py). The SQL is only a proposal: it runs only if the
# SQLGlot gate accepts it, and then only as the read-only analyst.
class LedgerSql(_Strict):
    sql: str = Field(description="Exactly one Db2 SELECT statement over the views given.")
    explanation: str = Field(description="One short sentence: what the query counts or lists.")


class LedgerAnswer(_Strict):
    answer: str = Field(description="The answer to the question, written only from the rows returned.")


# Policy intake (asof/intake.py): a policy document becomes proposed clause versions. Every value
# here is a proposal; deterministic checks run on it, and an editor approves it, before anything
# reaches POLICY_CLAUSE.
MAX_INTAKE_ITEMS = 12


class IntakeRuleParam(_Strict):
    key: str = Field(
        description="snake_case name. End it with the unit where there is one: _usd, _pct, _hours, _days, "
        "_business_days, _months, _kg. Start a limit with max_ or min_. End a yes/no permission with _allowed "
        "or _required."
    )
    number: float | None = Field(description="The value if it is a number, else null.")
    flag: bool | None = Field(description="The value if it is yes or no, else null.")
    items: list[str] | None = Field(
        description="The values if it is a list of words or phrases copied from the clause text, else null."
    )


class IntakeClause(_Strict):
    existing_clause_id: str | None = Field(
        description="ID of the existing clause this section replaces or restates, from <existing_clauses>. "
        "Null for a section that adds a rule no existing clause covers."
    )
    area: Area = Field(description="The policy area of the section.")
    title: str = Field(description="A short title for the section.")
    clause_text: str = Field(
        description="The section's policy text, copied character for character from the document, complete. "
        "Leave out the section number, the heading and any sentence that only says when the section takes effect."
    )
    effective_from: str = Field(description="The date the section takes effect, as YYYY-MM-DD.")
    effective_to: str | None = Field(
        description="The date the section stops applying, as YYYY-MM-DD, only if the document states one; else null."
    )
    date_quote: str = Field(
        description="The sentence of the document that states effective_from, copied character for character."
    )
    rule: list[IntakeRuleParam] = Field(
        description="Every checkable value the clause text states: amounts, percentages, time limits, weights, "
        "counts and yes/no permissions."
    )


class IntakeResult(_Strict):
    clauses: list[IntakeClause] = Field(description="One proposal per policy section, in document order.")


class BankIntakeClause(IntakeClause):
    area: BankArea = Field(description="The fee schedule area of the section.")  # type: ignore[assignment]


class BankIntakeResult(IntakeResult):
    clauses: list[BankIntakeClause] = Field(  # type: ignore[assignment]
        description="One proposal per policy section, in document order."
    )
