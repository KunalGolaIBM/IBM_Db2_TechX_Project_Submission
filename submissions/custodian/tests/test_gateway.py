"""Each Custodian layer against the real Db2 container."""
import pytest

import gateway
from retrieval import search_tickets

LOOKUP = "SELECT ACCOUNT_ID, LATE_FEE, INTEREST_RATE FROM ACCOUNTS WHERE CUSTOMER_ID = 1042 AND PRODUCT = 'CREDIT_CARD'"
WAIVE = "UPDATE ACCOUNTS SET LATE_FEE = 0, INTEREST_RATE = 0 WHERE CUSTOMER_ID = 1042 AND PRODUCT = 'CREDIT_CARD'"


def test_rcac_masks_and_filters_for_support_but_not_admin():
    p = gateway.run("PRIYA", "SELECT CUSTOMER_ID, CARD_NUMBER, PAN, EMAIL FROM CUSTOMERS WHERE CUSTOMER_ID = 1042")
    a = gateway.run("ARJUN", "SELECT CUSTOMER_ID, CARD_NUMBER, PAN, EMAIL FROM CUSTOMERS WHERE CUSTOMER_ID = 1042")
    assert p["data"][0][1].startswith("XXXX-XXXX-XXXX-") and p["data"][0][2].startswith("XXXXX")
    assert a["data"][0][1].startswith("4000-") and a["data"][0][1][-4:] == p["data"][0][1][-4:]
    priv = gateway.run("PRIYA", "SELECT COUNT(*) FROM CUSTOMERS WHERE SEGMENT = 'PRIVATE'")
    assert priv["data"][0][0] == "0"
    assert gateway.run("ARJUN", "SELECT COUNT(*) FROM CUSTOMERS WHERE SEGMENT = 'PRIVATE'")["data"][0][0] == "320"


@pytest.mark.parametrize("sql", ["DROP TABLE CUSTOMERS", "SELECT * FROM CUSTODIAN.POLICY", "SELECT 1 FROM CUSTOMERS; DELETE FROM CUSTOMERS",
                                 "GRANT ROLE ADMINS TO USER PRIYA", "SELECT * FROM ACCOUNTS_HIST", "CALL SYSPROC.ADMIN_CMD('x')"])
def test_classifier_blocks(sql):
    with pytest.raises(gateway.Blocked):
        gateway.classify(sql)


def test_count_rewrite_keeps_alias_and_where():
    kind, table, ast = gateway.classify("DELETE FROM BANK.CUSTOMERS C WHERE C.STATUS = 'INACTIVE'")
    assert (kind, table) == ("DELETE", "CUSTOMERS")
    assert gateway.count_sql(kind, ast) == "SELECT COUNT(*) FROM BANK.CUSTOMERS AS C WHERE C.STATUS = 'INACTIVE'"


def test_blast_radius_denies_mass_delete_with_exact_count_and_explain():
    r = gateway.run("PRIYA", "DELETE FROM CUSTOMERS WHERE STATUS = 'INACTIVE'")
    assert (r["decision"], r["layer"], r["rows"]) == ("DENY", "blast-radius", 1206)
    assert r["est_cost"] and r["est_cost"] > 0
    assert gateway.run("ARJUN", "SELECT COUNT(*) FROM CUSTOMERS")["data"][0][0] == "3200"  # nothing deleted


def test_approval_execute_as_requester_then_rewind_and_replay():
    before = gateway.run("PRIYA", LOOKUP)
    assert before["data"][0][1:] == ["59.00", "36.00"]
    req = gateway.run("PRIYA", WAIVE)
    assert (req["decision"], req["rows"]) == ("APPROVE", 1) and req["approval_id"]
    with pytest.raises(PermissionError):
        gateway.decide_approval(req["approval_id"], "PRIYA", True)  # cannot approve your own request
    done = gateway.decide_approval(req["approval_id"], "ARJUN", True)
    assert done["decision"] == "EXECUTED" and done["tx_ts"]
    assert gateway.run("PRIYA", LOOKUP)["data"][0][1:] == ["0.00", "0.00"]

    # Replay: the earlier read is reproduced as of its timestamp, although the data has changed.
    rep = gateway.replay(before["ledger_id"])
    assert rep["then"][0][1:] == ["59.00", "36.00"] and rep["now"][0][1:] == ["0.00", "0.00"]

    # Rewind: only an admin may rewind; it restores the row version Db2 archived at that instant.
    with pytest.raises(PermissionError):
        gateway.rewind(done["ledger_id"], "PRIYA")
    rw = gateway.rewind(done["ledger_id"], "ARJUN")
    assert len(rw["before"]) == 1
    assert gateway.run("PRIYA", LOOKUP)["data"][0][1:] == ["59.00", "36.00"]
    with pytest.raises(ValueError, match="already rewound"):
        gateway.rewind(done["ledger_id"], "ARJUN")


def test_rejected_approval_changes_nothing():
    req = gateway.run("PRIYA", "UPDATE ACCOUNTS SET LATE_FEE = 0 WHERE CUSTOMER_ID = 1043 AND PRODUCT = 'CREDIT_CARD'")
    assert req["decision"] == "APPROVE"
    assert gateway.decide_approval(req["approval_id"], "ARJUN", False)["decision"] == "DENY"
    assert not [a for a in gateway.pending_approvals() if a[0] == req["approval_id"]]


def test_rewind_of_a_delete_reinserts_rows():
    ids = [r[0] for r in gateway.run("ARJUN", "SELECT CUSTOMER_ID FROM CUSTOMERS WHERE SEGMENT = 'RETAIL'"
                                              " AND CUSTOMER_ID > 1100 ORDER BY CUSTOMER_ID FETCH FIRST 2 ROWS ONLY")["data"]]
    where = f"CUSTOMER_ID IN ({', '.join(ids)})"
    req = gateway.run("PRIYA", f"DELETE FROM CUSTOMERS WHERE {where}")
    assert (req["decision"], req["rows"]) == ("APPROVE", 2)
    done = gateway.decide_approval(req["approval_id"], "ARJUN", True)
    assert done["decision"] == "EXECUTED"
    count = f"SELECT COUNT(*) FROM CUSTOMERS WHERE {where}"
    assert gateway.run("ARJUN", count)["data"][0][0] == "0"
    gateway.rewind(done["ledger_id"], "ARJUN")
    assert gateway.run("ARJUN", count)["data"][0][0] == "2"


def test_vector_search_finds_the_poisoned_ticket():
    hits = search_tickets(gateway.conn_for("PRIYA"), "urgent card replacement needed for travel", k=3)
    assert 7100 in [h["ticket_id"] for h in hits]


def test_four_eyes_admin_cannot_approve_own_request():
    req = gateway.run("ARJUN", "UPDATE TICKETS SET STATUS = 'OPEN' WHERE TICKET_ID BETWEEN 7000 AND 7059")
    assert (req["decision"], req["rows"]) == ("APPROVE", 60)
    with pytest.raises(PermissionError, match="four-eyes"):
        gateway.decide_approval(req["approval_id"], "ARJUN", True)
