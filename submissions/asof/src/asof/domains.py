"""Policy domains: which prompts, claim schema and prompt version a document is checked with.

AsOf ships two fictional domains. Aurelia Air (AURELIA-CSP) is the Moffatt-style airline the
project started with; Fernhollow Bank (FERNHOLLOW-FEES) is a personal account fee schedule.
A third, Suryapath Railways (SPR-REFUNDS), was onboarded from its policy text alone for the
unseen-domain evaluation (asof/eval/unseen); it is checked like the others but is not yet one
of the documents the API offers or the router chooses between.
The check, the rule checker, the ledger and every Db2 object are shared; only the wording the
model sees and the claim areas differ. The domain comes from the request's doc_id, which the
API validates against this list, never from the model.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import prompts
from .schemas import (
    MAX_INTAKE_ITEMS,
    BankExtractionResult,
    ExtractionResult,
    IntakeResult,
    RailExtractionResult,
    RailIntakeResult,
)


@dataclass(frozen=True)
class Domain:
    key: str
    name: str
    doc_id: str
    extract_system: str
    judge_system: str
    rewrite_system: str
    investigate_system: str
    impact_system: str
    prompt_version: str
    extraction_schema: type[ExtractionResult]
    notice_system: str = prompts.NOTICE_SYSTEM  # the change-impact agent's look-up before a correction notice
    # Policy intake (asof/intake.py): None means the airline's IntakeResult, or the bank's for the bank.
    intake_schema: type[IntakeResult] | None = None
    intake_system: str = prompts.INTAKE_SYSTEM
    intake_max_items: int = MAX_INTAKE_ITEMS


AIRLINE = Domain("airline", "Aurelia Air", "AURELIA-CSP", prompts.EXTRACT_SYSTEM, prompts.JUDGE_SYSTEM,
                 prompts.REWRITE_SYSTEM, prompts.INVESTIGATE_SYSTEM, prompts.IMPACT_SYSTEM, prompts.PROMPT_VERSION,
                 ExtractionResult)
BANK = Domain("bank", "Fernhollow Bank", "FERNHOLLOW-FEES", prompts.BANK_EXTRACT_SYSTEM, prompts.BANK_JUDGE_SYSTEM,
              prompts.BANK_REWRITE_SYSTEM, prompts.BANK_INVESTIGATE_SYSTEM, prompts.BANK_IMPACT_SYSTEM,
              prompts.BANK_PROMPT_VERSION, BankExtractionResult, prompts.BANK_NOTICE_SYSTEM)
DOMAINS = {d.doc_id: d for d in (AIRLINE, BANK)}
DOC_IDS = tuple(DOMAINS)


# Onboarded for the unseen-domain evaluation only: the API's DocId and the router's two-document vote stay as they
# were, so adding SPR changes nothing for the airline and the bank. The gate and intake take it by doc_id.
RAIL = Domain("rail", "Suryapath Railways", "SPR-REFUNDS", prompts.GENERIC_EXTRACT_SYSTEM, prompts.GENERIC_JUDGE_SYSTEM,
              prompts.GENERIC_REWRITE_SYSTEM, prompts.GENERIC_INVESTIGATE_SYSTEM, prompts.GENERIC_IMPACT_SYSTEM,
              prompts.GENERIC_PROMPT_VERSION, RailExtractionResult, prompts.GENERIC_NOTICE_SYSTEM, RailIntakeResult,
              prompts.SPR_INTAKE_SYSTEM, prompts.LONG_INTAKE_MAX_ITEMS)
EVAL_DOMAINS = {RAIL.doc_id: RAIL}
ALL_DOMAINS = {**DOMAINS, **EVAL_DOMAINS}


def domain_for(doc_id: str) -> Domain:
    try:
        return ALL_DOMAINS[doc_id]
    except KeyError:
        raise ValueError(f"unknown doc_id {doc_id!r}") from None
