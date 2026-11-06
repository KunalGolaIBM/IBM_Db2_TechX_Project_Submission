"""Seed corpus validation and configuration safety."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from asof.config import ConfigError, Settings
from asof.corpus import Clause, load_corpus


def test_corpus_shape():
    corpus = load_corpus()
    assert len(corpus.clauses) == 34
    assert {c.area for c in corpus.clauses} == {
        "bereavement", "cancellation", "change_fee", "baggage", "refund", "delay", "travel_credit", "pets"}
    multi = {c.clause_id for c in corpus.clauses if len(c.versions) > 1}
    assert multi == {"BRV-002", "CXL-001", "CHG-002", "BAG-001"}


@pytest.mark.parametrize("on, label", [
    (date(2026, 3, 10), "v1"), (date(2026, 4, 30), "v1"), (date(2026, 5, 1), "v2"), (date(2026, 6, 2), "v2"),
])
def test_brv_002_version_boundary(on, label):
    assert load_corpus().version_in_force("BRV-002", on).version_label == label


def test_no_version_before_policy_start():
    assert load_corpus().version_in_force("BRV-002", date(2025, 12, 31)) is None


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
