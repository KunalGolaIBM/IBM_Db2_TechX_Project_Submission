"""The router against Db2: one statement ranks both documents' clauses in force on the date, and a held route lands
in the ledger and the specialist inbox, where the specialist may check the reply against either document."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fakes import ScriptedLLM, claims, judge, verdict

from asof import db, ledger, review, router, schema, seed
from asof.gate import Gate, GateRequest

pytestmark = pytest.mark.db2


@pytest.fixture(scope="module")
def routed(admin_conn, embeddings, settings):
    name = f"ASOF_T{uuid.uuid4().hex[:6].upper()}"
    try:
        schema.install(admin_conn, name)
        seed.seed_policy(admin_conn, embeddings, name)
        seed.seed_chain_head(admin_conn, name)
        seed.seed_faq(admin_conn, embeddings, name)
        schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name)
    except Exception:
        schema.drop(admin_conn, name)
        raise
    yield name
    schema.drop(admin_conn, name)


def test_db2_ranks_both_documents_in_one_statement(settings, embeddings, routed):
    r = router.Router(embeddings, lambda: db.connect(settings, "app"), routed)
    near = r.nearest("How much is the overdraft fee?", "The overdraft fee is $35 per item.", date(2026, 3, 2))
    assert {n.doc_id for n in near} == {"AURELIA-CSP", "FERNHOLLOW-FEES"}
    assert len(near) == 2 * router.NEAREST and near[0].doc_id == "AURELIA-CSP"  # ordered by document, then rank
    bank = [n for n in near if n.doc_id == "FERNHOLLOW-FEES"]
    assert bank[0].clause_id == "OVD-001" and bank[0].version == "v1"  # the version in force on 2 March
    assert [n.distance for n in bank] == sorted(n.distance for n in bank)
    out = r.route("How much is the overdraft fee?", "The overdraft fee is $35 per item.", date(2026, 3, 2))
    assert (out.doc_id, out.method) == ("FERNHOLLOW-FEES", "db2")


def test_an_uncertain_route_is_held_and_the_specialist_picks_the_document(settings, embeddings, routed):
    gate = Gate(ScriptedLLM(extract=[claims(("An overdraft fee is charged for each item paid.", "other", "amount"))],
                            judge=[judge(verdict(1, "SUPPORTED", "OVD-001", "is charged for each item we pay"))]),
                embeddings, lambda: db.connect(settings, "app"), routed)
    r = router.Router(embeddings, lambda: db.connect(settings, "app"), routed).route(
        "Is there a fee?", "It depends.", date(2026, 3, 2))
    assert r.doc_id is None
    held = gate.hold(GateRequest("Is there a fee?", "It depends.", date(2026, 3, 2), r.leader, "chat", None, r.as_json()),
                     "ROUTE_UNCERTAIN", f"router:{r.method}")
    assert (held.decision, held.reason_code, held.released) == ("ESCALATED", "ROUTE_UNCERTAIN", False)
    with db.connection(settings, "app") as conn:
        entry = ledger.get_entry(conn, held.ledger_id, routed)
        assert entry["verdicts"]["route"]["method"] == "ask" and entry["model_info"] == "router:ask"
        assert ledger.verify_chain(conn, routed).status == "OK"
    other = "FERNHOLLOW-FEES" if r.leader == "AURELIA-CSP" else "AURELIA-CSP"
    done = review.resolve(gate, held.ledger_id, "An overdraft fee is charged for each item we pay.", doc_id="FERNHOLLOW-FEES",
                          connect=lambda: db.connect(settings, "review"))  # as the API sends it: the reviewer account
    assert done.outcome == "SPECIALIST_CHECKED"
    with db.connection(settings, "app") as conn:
        assert ledger.get_entry(conn, done.ledger_id, routed)["doc_id"].strip() == "FERNHOLLOW-FEES"
    assert other in ("AURELIA-CSP", "FERNHOLLOW-FEES")
