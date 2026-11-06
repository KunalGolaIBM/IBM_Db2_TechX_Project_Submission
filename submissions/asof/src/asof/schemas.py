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
