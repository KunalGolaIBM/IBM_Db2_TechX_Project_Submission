from datetime import timedelta
from decimal import Decimal

from time_machine import diff_engine as de
from time_machine.memory_repo import MemoryRepository, demo_scenario


def analyse(fault):
    repo, snap = demo_scenario(fault)
    now = repo.now()
    rows, _ = repo.versions(1, snap, now)
    dl, _ = repo.delete_log(snap, now)
    events = de.build_events(de.versions_from_rows(rows), snap, now, dl)
    m0, m1 = repo.metric_as_of(1, snap).revenue, repo.metric_as_of(1, now).revenue
    return events, m0, m1


def test_price_change_is_found_and_reconciles():
    events, m0, m1 = analyse("price")
    assert de.reconcile(events, m0, m1)["ok"]
    price = [e for e in events if e.pattern == "price_change"]
    assert len(price) == 12 and {e.actor for e in price} == {"nightly_batch"}
    assert len({e.txn for e in price}) == 1  # one transaction
    assert de.score_hypothesis("price_change", events, m0, m1)["confirmed"]
    assert not de.score_hypothesis("rows_deleted", events, m0, m1)["confirmed"]


def test_duplicate_load_is_distinguished_from_normal_new_orders():
    events, m0, m1 = analyse("duplicate")
    assert sum(e.pattern == "duplicate_load" for e in events) == 10
    assert sum(e.pattern == "new_rows" for e in events) == 3  # the legitimate web orders
    assert de.score_hypothesis("duplicate_load", events, m0, m1)["confirmed"]


def test_quantity_and_deleted_patterns():
    events, m0, m1 = analyse("quantity")
    assert de.score_hypothesis("quantity_change", events, m0, m1)["confirmed"]
    events, m0, m1 = analyse("deleted")
    assert de.score_hypothesis("rows_deleted", events, m0, m1)["confirmed"]
    deletes = [e for e in events if e.kind == "delete"]
    assert len(deletes) == 8 and {e.actor for e in deletes} == {"cleanup_job"}
    assert de.reconcile(events, m0, m1)["ok"]


def test_wrong_direction_is_rejected():
    events, m0, m1 = analyse("duplicate")  # revenue went UP
    # pretend someone asks about a price change that never happened
    s = de.score_hypothesis("price_change", events, m0, m1)
    assert s["rows"] == 0 and not s["confirmed"]


def test_grouping_by_transaction():
    events, *_ = analyse("price")
    groups = de.group_events(events)
    assert groups[0].pattern == "price_change" and groups[0].n_rows == 12 and groups[0].bulk
    assert groups[0].actors == ["nightly_batch"]


def test_no_events_when_nothing_changed():
    from datetime import datetime
    t0 = datetime(2026, 1, 1, 8)
    repo = MemoryRepository(t0 + timedelta(hours=3))
    repo.insert(t0, 1, 1, 1, 2, 10)
    rows, _ = repo.versions(1, t0 + timedelta(hours=1), repo.now())
    assert de.build_events(de.versions_from_rows(rows), t0 + timedelta(hours=1), repo.now()) == []


def test_money_is_exact():
    events, m0, m1 = analyse("price")
    assert isinstance(m0, Decimal) and de.reconcile(events, m0, m1)["difference"] == "0.00"
