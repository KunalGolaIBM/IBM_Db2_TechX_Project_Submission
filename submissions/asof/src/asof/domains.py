"""Policy domains: which prompts, claim schema and prompt version a document is checked with.

AsOf ships two fictional domains. Aurelia Air (AURELIA-CSP) is the Moffatt-style airline the
project started with; Fernhollow Bank (FERNHOLLOW-FEES) is a personal account fee schedule.
The check, the rule checker, the ledger and every Db2 object are shared; only the wording the
model sees and the claim areas differ. The domain comes from the request's doc_id, which the
API validates against this list, never from the model.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import prompts
from .schemas import BankExtractionResult, ExtractionResult


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


AIRLINE = Domain("airline", "Aurelia Air", "AURELIA-CSP", prompts.EXTRACT_SYSTEM, prompts.JUDGE_SYSTEM,
                 prompts.REWRITE_SYSTEM, prompts.INVESTIGATE_SYSTEM, prompts.IMPACT_SYSTEM, prompts.PROMPT_VERSION,
                 ExtractionResult)
BANK = Domain("bank", "Fernhollow Bank", "FERNHOLLOW-FEES", prompts.BANK_EXTRACT_SYSTEM, prompts.BANK_JUDGE_SYSTEM,
              prompts.BANK_REWRITE_SYSTEM, prompts.BANK_INVESTIGATE_SYSTEM, prompts.BANK_IMPACT_SYSTEM,
              prompts.BANK_PROMPT_VERSION, BankExtractionResult, prompts.BANK_NOTICE_SYSTEM)
DOMAINS = {d.doc_id: d for d in (AIRLINE, BANK)}
DOC_IDS = tuple(DOMAINS)


def domain_for(doc_id: str) -> Domain:
    try:
        return DOMAINS[doc_id]
    except KeyError:
        raise ValueError(f"unknown doc_id {doc_id!r}") from None
