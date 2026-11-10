"""Seed corpus validation and configuration safety."""

from __future__ import annotations

from datetime import date

import pytest
from fakes import version_in_force
from pydantic import ValidationError

from asof.config import ConfigError, Settings
from asof.corpus import Clause, load_corpus


def test_corpus_shape():
    corpus = load_corpus()
    airline = [c for c in corpus.clauses if c.doc_id == "AURELIA-CSP"]
    bank = [c for c in corpus.clauses if c.doc_id == "FERNHOLLOW-FEES"]
    assert (len(airline), len(bank), len(corpus.clauses)) == (34, 18, 52)
    assert {c.area for c in airline} == {
        "bereavement", "cancellation", "change_fee", "baggage", "refund", "delay", "travel_credit", "pets"}
    assert {c.area for c in bank} == {"overdraft", "fee_refund", "monthly_fee", "foreign_transaction", "wire_transfer",
                                      "atm", "dispute", "account_closure", "checks"}
    multi = {c.clause_id for c in airline if len(c.versions) > 1}
    assert multi == {"BRV-002", "CXL-001", "CHG-002", "BAG-001"}
    assert {c.clause_id for c in bank if len(c.versions) > 1} == {
        "OVD-001", "OVD-003", "FRV-001", "MTF-001", "MTF-002", "FXF-001", "ATM-001", "CLS-001"}


@pytest.mark.parametrize("on, label", [(date(2026, 6, 30), "v1"), (date(2026, 7, 1), "v2")])
def test_the_bank_overdraft_fee_changes_on_1_july(on, label):
    v = version_in_force(load_corpus(), "OVD-001", on)
    assert v.version_label == label and v.rule["overdraft_fee_usd"] == (35 if label == "v1" else 25)


@pytest.mark.parametrize("on, label", [
    (date(2026, 3, 10), "v1"), (date(2026, 4, 30), "v1"), (date(2026, 5, 1), "v2"), (date(2026, 6, 2), "v2"),
])
def test_brv_002_version_boundary(on, label):
    assert version_in_force(load_corpus(), "BRV-002", on).version_label == label


def test_no_version_before_policy_start():
    assert version_in_force(load_corpus(), "BRV-002", date(2025, 12, 31)) is None


def _clause(versions):
    return {"clause_id": "TST-001", "doc_id": "AURELIA-CSP", "area": "pets", "title": "t", "versions": versions}


def _v(label, start, end):
    return {"version_label": label, "bus_start": start, "bus_end": end, "clause_text": "x", "rule": {}}


def test_overlapping_versions_rejected():
    with pytest.raises(ValidationError, match="overlap"):
        Clause.model_validate(_clause([_v("v1", "2026-01-01", "2026-06-01"), _v("v2", "2026-05-01", "9999-12-31")]))


def test_empty_period_rejected():
    with pytest.raises(ValidationError, match="bus_end must be after"):
        Clause.model_validate(_clause([_v("v1", "2026-01-01", "2026-01-01")]))


def test_bad_clause_id_rejected():
    bad = _clause([_v("v1", "2026-01-01", "9999-12-31")]) | {"clause_id": "BRV-002'; DROP TABLE x"}
    with pytest.raises(ValidationError):
        Clause.model_validate(bad)


def test_secrets_never_appear_in_repr():
    s = Settings(_env_file=None, db2_admin_password="hunter2-admin", openrouter_api_key="sk-or-secret")
    assert "hunter2-admin" not in repr(s) and "sk-or-secret" not in repr(s)
    assert "hunter2-admin" not in str(s.model_dump())


def test_require_names_missing_keys():
    with pytest.raises(ConfigError, match="DB2_PASSWORD"):
        Settings(_env_file=None).require("db2_admin_password")


@pytest.mark.parametrize("field, value", [
    ("asof_app_user", "app; rm -rf /"),
    ("asof_app_user", "toolongname"),
    ("db2_database", "TEST DB"),
    ("db2_container", "x;y"),
    ("ollama_base_url", "file:///etc/passwd"),
])
def test_identifiers_and_urls_are_validated(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_values_left_as_in_env_example_count_as_missing():
    from asof.config import ConfigError, Settings

    s = Settings(_env_file=None, openrouter_api_key="sk-or-v1-your-key-here", db2_admin_password="change-me-db2-admin")
    assert s.embedding_key is not None and not s.indb_embeddings_wanted  # no in-database embeddings with a fake key
    for name in ("openrouter_api_key", "db2_admin_password"):
        with pytest.raises(ConfigError):
            s.require(name)
    assert Settings(_env_file=None, openrouter_api_key="sk-or-v1-0123456789abcdef").indb_embeddings_wanted


def test_env_example_names_every_setting_and_ships_no_owner_password():
    """README: .env.example lists every setting. An empty DB2_PASSWORD makes compose refuse to start
    instead of creating Db2 with a placeholder that setup would then reject."""
    import re
    from pathlib import Path

    from pydantic import AliasChoices

    text = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    names = [f.validation_alias.choices[0] if isinstance(f.validation_alias, AliasChoices) else n.upper()
             for n, f in Settings.model_fields.items()]
    assert [n for n in names if not re.search(rf"(?m)^(# )?{n}=", text)] == []
    assert re.search(r"(?m)^DB2_PASSWORD=$", text)
    assert not re.search(r"(?m)^[A-Z_]*(KEY|PASSWORD|TOKEN)=\S", text), "no value for any secret"


def test_an_openai_compatible_endpoint_needs_a_real_key_to_count_as_ready():
    base = dict(_env_file=None, llm_provider="openai_compatible", openai_compat_base_url="https://api.example.com/v1",
                openai_compat_model="m")
    assert not Settings(**base).llm_ready
    assert not Settings(**base, openai_compat_api_key="your-api-key-here").llm_ready  # copied from the example
    assert Settings(**base, openai_compat_api_key="sk-test-0123456789").llm_ready
