"""Domain row permissions without a database: the SQL's rule, the roles and users setup grants, and the API scope.
The Db2 behaviour itself is in test_db2_row_permissions.py."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from asof import db, rowaccess, schema, setup
from asof.api import create_app
from asof.config import Settings
from asof.domains import DOMAINS

PROTECTED = {"ANSWER_LEDGER", "CLAIM_CITATION", "ESCALATION_REVIEW", "CORRECTION_NOTICE", "ANSWER_SUGGESTION"}
DOMAIN_MQTS = {"MQT_DOMAIN_DECISION_STATS", "MQT_DOMAIN_CLAIM_OUTCOMES"}  # per policy document: the domain rule
ALL_DOMAIN_MQTS = {"MQT_DECISION_STATS", "MQT_CLAIM_OUTCOMES"}  # counts over every domain: all-domain readers only
# The three terms every domain permission (and V_DOMAIN_SCOPE) is made of; see the head of 06_domain_permissions.sql.
ALL_DOMAINS_TERM = "VERIFY_ROLE_FOR_USER(SESSION_USER, 'ASOF_ALL_DOMAINS') = 1"
SECADM_TERM = ("EXISTS (SELECT 1 FROM SYSCAT.DBAUTH A WHERE A.GRANTEE = SESSION_USER AND A.GRANTEETYPE = 'U' "
               "AND A.SECURITYADMAUTH = 'Y')")
DOMAIN_TERM = "IN (SELECT X.DOC_ID FROM ASOF.DOMAIN_ACCESS X WHERE VERIFY_ROLE_FOR_USER(SESSION_USER, X.ROLE_NAME) = 1)"
# The analytics views' second branch: only for a reader who is neither of the first two.
NEITHER = f"{ALL_DOMAINS_TERM[:-1]}0 AND NOT {SECADM_TERM}"


def _flat(sql: str) -> str:
    return re.sub(r"\s+", " ", sql)


def _statements():
    return [st for st in schema.load_statements("ASOF") if st.source == "06_domain_permissions.sql"]


def test_every_table_with_decision_rows_has_a_permission_and_row_access_control():
    sts = _statements()
    permitted = {re.search(r" ON ASOF\.(\w+)( AS |\s+FOR ROWS)", _flat(st.sql)).group(1)
                 for st in sts if st.kind == "permission"}
    activated = {re.search(r"ALTER TABLE ASOF\.(\w+) ACTIVATE ROW ACCESS CONTROL", st.sql).group(1)
                 for st in sts if st.kind == "other"}
    assert permitted == PROTECTED | DOMAIN_MQTS | ALL_DOMAIN_MQTS
    assert activated == PROTECTED  # Db2 activates row access control on the MQTs itself
    assert all("ENFORCED FOR ALL ACCESS ENABLE" in st.sql for st in sts if st.kind == "permission")


def test_every_permission_and_the_scope_view_apply_the_same_rule():
    """The rule is written out in each permission (Db2 will not replace a view a permission depends on): one copy
    that drifts would show a user rows the others hide."""
    sts = {st.name: _flat(st.sql) for st in _statements() if st.kind in ("permission", "view")}
    assert len(sts) == len(PROTECTED) + len(DOMAIN_MQTS) + len(ALL_DOMAIN_MQTS) + 1
    for name, flat in sts.items():
        where = flat.split(" WHERE ", 1)[1]
        assert where.index(ALL_DOMAINS_TERM) < where.index(SECADM_TERM), name
        if any(f" ON ASOF.{m} " in flat for m in ALL_DOMAIN_MQTS):
            assert DOMAIN_TERM not in flat, name  # every domain's counts mixed together: never for a domain reader
        else:
            assert where.index(SECADM_TERM) < where.index(DOMAIN_TERM), name


def test_the_analytics_views_give_a_domain_reader_its_own_figures_and_everyone_else_the_original_ones():
    views = {st.name: _flat(st.sql) for st in schema.load_statements("ASOF") if st.kind == "view"}
    for view, original, per_domain in (("V_DECISION_STATS", "MQT_DECISION_STATS", "MQT_DOMAIN_DECISION_STATS"),
                                       ("V_CLAIM_OUTCOMES_BY_AREA", "MQT_CLAIM_OUTCOMES", "MQT_DOMAIN_CLAIM_OUTCOMES")):
        first, second = views[view].split(" UNION ALL ")
        assert f"FROM ASOF.{original} " in first + " " and per_domain not in first, view
        assert f"FROM ASOF.{per_domain}" in second and NEITHER in second, view


def test_the_review_and_notice_triggers_are_secured():
    """Db2 refuses to activate row access control on a table with a trigger that is not SECURED (SQL20469N, 37)."""
    triggers = {st.name: st.sql for st in schema.load_statements("ASOF") if st.kind == "trigger"}
    for name, sql in triggers.items():
        if name.startswith(("ESCALATION_REVIEW_", "CORRECTION_NOTICE_", "ANSWER_LEDGER_", "CLAIM_CITATION_")):
            assert "FOR EACH ROW SECURED" in sql, name


def test_every_domain_gets_a_role_and_the_shipped_domains_have_users():
    # The third public domain (Indian Railways) gets its role and DOMAIN_ACCESS row, but ships with no users of its own.
    assert {rowaccess.role_for(d) for d in DOMAINS.values()} == {"ASOF_DOMAIN_AIRLINE", "ASOF_DOMAIN_BANK",
                                                                  "ASOF_DOMAIN_INDIAN_RAIL"}
    s = Settings(_env_file=None)
    assert rowaccess.domain_users(s) == rowaccess.DEFAULT_DOMAIN_USERS == {"airline": ("airread", "airrev"),
                                                                           "bank": ("bankread", "bankrev")}
    assert [(x.key, x.user, x.connection, x.doc_ids) for x in rowaccess.scopes(s)] == [
        ("all", "asofread", "analyst", ("AURELIA-CSP", "FERNHOLLOW-FEES", "INDIAN-RAIL-REFUNDS")),
        ("airline", "airread", "analyst_airline", ("AURELIA-CSP",)),
        ("bank", "bankread", "analyst_bank", ("FERNHOLLOW-FEES",))]


def test_each_domain_user_connects_with_its_own_password():
    s = Settings(_env_file=None, asof_bank_review_user="fhrev", asof_bank_review_password="pw-bank-review-0123")
    assert db._credentials(s, "review_bank") == ("fhrev", "pw-bank-review-0123")
    with pytest.raises(Exception, match="ASOF_AIRLINE_ANALYST_PASSWORD"):
        db._credentials(Settings(_env_file=None), "analyst_airline")


def test_setup_generates_a_password_for_every_domain_user_and_creates_them_all():
    assert {"ASOF_AIRLINE_ANALYST_PASSWORD", "ASOF_AIRLINE_REVIEW_PASSWORD", "ASOF_BANK_ANALYST_PASSWORD",
            "ASOF_BANK_REVIEW_PASSWORD"} <= set(setup.GENERATED_KEYS)
    users = [u for u, _ in setup._users(Settings(_env_file=None))]
    assert users == ["asofapp", "asofedit", "asofrev", "asofread", "asofmart", "airread", "airrev", "bankread", "bankrev"]
    assert len(users) == len(setup.GENERATED_KEYS)  # the manual instructions pair each user with its key


@pytest.mark.parametrize("users", [{"airline": ("asofread", "airrev")}, {"bank": ("bankread", "asofmart")}])
def test_a_domain_user_may_not_also_be_an_all_domain_user(users):
    with pytest.raises(ValueError, match="all-domain"):
        schema.apply_grants(None, "asofapp", "asofedit", "ASOF", domain_users=users)  # refused before any SQL


def test_the_api_lists_the_scopes_and_refuses_an_unknown_one():
    class Asker:
        def __init__(self):
            self.asked = []

        def ask(self, question, scope="all"):
            from asof.askledger import AskResult
            self.asked.append(scope)
            return AskResult(question=question, status="ANSWERED", scope=scope)

    from test_api import FakeAssistant, FakeGate

    asker = Asker()
    c = TestClient(create_app(Settings(_env_file=None), gate=FakeGate(), assistant=FakeAssistant(), asker=asker))
    listed = c.get("/api/ledger/ask/scopes").json()
    assert [(x["key"], x["user"], x["doc_ids"]) for x in listed] == [
        ("all", "asofread", ["AURELIA-CSP", "FERNHOLLOW-FEES", "INDIAN-RAIL-REFUNDS"]), ("airline", "airread", ["AURELIA-CSP"]),
        ("bank", "bankread", ["FERNHOLLOW-FEES"])]
    assert c.post("/api/ledger/ask", json={"question": "How many?", "scope": "bank"}).json()["scope"] == "bank"
    assert c.post("/api/ledger/ask", json={"question": "How many?", "scope": "railway"}).status_code == 422
    assert c.post("/api/ledger/ask", json={"question": "How many?", "scope": "ALL; DROP"}).status_code == 422
    assert asker.asked == ["bank"]
