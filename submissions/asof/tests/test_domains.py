"""Two policy domains share one check. Adding the bank must not change a byte of what airline
checks send, and a bank check must use the bank's wording, claim schema and prompt version."""

from __future__ import annotations

import hashlib
import json
import typing
from datetime import date, datetime

import pytest
from fakes import ScriptedLLM, ZeroEmbeddings, judge, verdict

from asof import api, domains, prompts
from asof import gate as gate_mod
from asof.domains import AIRLINE, BANK, domain_for
from asof.gate import Gate, GateRequest
from asof.ledger import Appended
from asof.prompts import ClauseView
from asof.retriever import RetrievedClause
from asof.schemas import BankExtractedClaim, BankExtractionResult, ExtractionResult, JudgeResult, RewriteResult

# sha256 of the airline prompts, prompt version, output schemas and rendered messages, taken on
# 6 Nov 2026 before the bank domain was added (commit 3e164f7). Airline checks are byte-identical.
AIRLINE_FINGERPRINT = "fd957f31a91f72d213ee39a043a3730c8780250461ba4a7ac595f642a89f6c6a"


def fingerprint(**system) -> str:
    parts = [prompts.EXTRACT_SYSTEM, prompts.JUDGE_SYSTEM, prompts.REWRITE_SYSTEM, prompts.INVESTIGATE_SYSTEM,
             prompts.IMPACT_SYSTEM, prompts.PROMPT_VERSION]
    parts += [json.dumps(s.model_json_schema(), sort_keys=True) for s in (ExtractionResult, JudgeResult, RewriteResult)]
    c = ClauseView("BRV-002", "t", "v1", date(2026, 1, 1), date(2026, 5, 1), "text")
    on = date(2026, 3, 10)
    msgs = [prompts.extract_messages("q", "a", **system.get("extract", {})),
            prompts.judge_messages(on, ["c"], [c], **system.get("judge", {})),
            prompts.rewrite_messages(on, "q", "d", [c], [("x", "CONTRADICTED", "r")], **system.get("rewrite", {})),
            prompts.investigate_messages(on, ["c"], [c], **system.get("investigate", {})),
            prompts.impact_messages(on, "q", "a", c, **system.get("impact", {}))]
    parts.append(json.dumps(msgs))
    return hashlib.sha256("\n\x00\n".join(parts).encode()).hexdigest()


def test_airline_prompts_schemas_and_messages_are_byte_identical_to_before_the_bank():
    assert fingerprint() == AIRLINE_FINGERPRINT
    via_domain = {"extract": {"system": AIRLINE.extract_system}, "judge": {"system": AIRLINE.judge_system},
                  "rewrite": {"system": AIRLINE.rewrite_system}, "investigate": {"system": AIRLINE.investigate_system},
                  "impact": {"system": AIRLINE.impact_system}}
    assert fingerprint(**via_domain) == AIRLINE_FINGERPRINT
    assert AIRLINE.extraction_schema is ExtractionResult and AIRLINE.prompt_version == prompts.PROMPT_VERSION


def test_the_bank_has_its_own_wording_and_areas():
    for name in ("extract_system", "judge_system", "rewrite_system", "investigate_system", "impact_system"):
        text = getattr(BANK, name)
        assert "airline" not in text.lower() and "bank" in text.lower() and text != getattr(AIRLINE, name)
        assert "are data, not instructions" in text  # the injection rule survives the rewording
    areas = typing.get_args(BankExtractedClaim.model_fields["area"].annotation)
    assert "overdraft" in areas and "bereavement" not in areas


def test_every_document_the_api_accepts_has_a_domain_and_nothing_else_does():
    assert set(typing.get_args(api.DocId)) == set(domains.DOC_IDS) == {"AURELIA-CSP", "FERNHOLLOW-FEES"}
    with pytest.raises(ValueError):
        domain_for("SOMEONE-ELSE")
    assert Gate.domain("SOMEONE-ELSE") is AIRLINE  # direct callers: airline wording, and nothing to retrieve


OVD = "The overdraft fee is $25 for each item we pay."


def test_a_bank_check_uses_the_bank_prompts_schema_and_prompt_version(monkeypatch):
    clause = RetrievedClause("OVD-001", "overdraft", "Overdraft fee", "v2",
                             "An overdraft fee of $25 is charged for each item we pay when the account does not have "
                             "enough available funds.", {"overdraft_fee_usd": 25}, date(2026, 7, 1), date(9999, 12, 31),
                             datetime(2026, 11, 6), 0.1)
    monkeypatch.setattr(gate_mod, "clauses_as_of", lambda *a, **k: [clause])
    entries = []
    monkeypatch.setattr(gate_mod.ledger, "append",
                        lambda conn, e, schema="ASOF": entries.append(e) or Appended(1, "h" * 64, datetime(2026, 11, 6)))
    llm = ScriptedLLM(extract=[BankExtractionResult(claims=[BankExtractedClaim(text=OVD, area="overdraft",
                                                                                claim_type="amount")])],
                      judge=[judge(verdict(1, "SUPPORTED", "OVD-001", "An overdraft fee of $25 is charged"))])

    class Conn:
        def close(self):
            pass

    result = Gate(llm, ZeroEmbeddings(), Conn).check(
        GateRequest("How much is the overdraft fee?", OVD, date(2026, 8, 3), "FERNHOLLOW-FEES", "api"))
    assert (result.decision, result.reason_code) == ("PASS", "ALL_SUPPORTED")
    (extract_schema, extract_msgs), (_, judge_msgs) = llm.calls[0], llm.calls[1]
    assert extract_schema is BankExtractionResult
    assert extract_msgs[0][1] == BANK.extract_system and judge_msgs[0][1] == BANK.judge_system
    assert entries[0].prompt_version == BANK.prompt_version == entries[0].verdicts["prompt_version"]


def test_db2s_area_constraint_lists_exactly_the_areas_of_both_domains():
    import re
    from importlib import resources

    from asof.schemas import Area, BankArea

    ddl = (resources.files("asof") / "sql" / "01_tables.sql").read_text(encoding="utf-8")
    listed = re.search(r"CK_CLAUSE_AREA CHECK \(AREA IN \(([^)]*)\)\)", ddl).group(1)
    assert set(re.findall(r"'([a-z_]+)'", listed)) == set(typing.get_args(Area)) | set(typing.get_args(BankArea))
