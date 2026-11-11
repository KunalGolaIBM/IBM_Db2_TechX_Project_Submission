"""Blocking / waiting classification."""

from helpers import lock, snapshot, wait

from locklens.services.lock_monitor import analyze_snapshot, find_cycles


def edge_for(analysis, waiter):
    return next(e for e in analysis.edges if e.waiter == waiter)


def test_holder_reported_by_db2_is_used_as_is():
    a = analyze_snapshot(snapshot(waits=[wait(9, 7)]))
    e = edge_for(a, 9)
    assert (e.holder, e.provenance) == (7, "db2_lockwait")
    assert a.waiters == {9} and a.blockers == {7} and a.root_blockers == {7}


def test_missing_holder_resolved_from_single_granted_lock_holder():
    a = analyze_snapshot(snapshot(waits=[wait(9, None)], locks=[lock(7), lock(9, status="W")]))
    e = edge_for(a, 9)
    assert (e.holder, e.provenance) == (7, "lock_table_match")


def test_requester_own_granted_lock_is_not_treated_as_blocker():
    # lock conversion: requester holds a granted lock on the same name itself
    a = analyze_snapshot(snapshot(waits=[wait(9, None)], locks=[lock(9, mode="S")]))
    e = edge_for(a, 9)
    assert e.holder is None and e.provenance == "unknown"
    assert a.blockers == set()


def test_multiple_granted_holders_are_ambiguous_not_guessed():
    a = analyze_snapshot(snapshot(waits=[wait(9, None)], locks=[lock(7, mode="S"), lock(8, mode="S")]))
    e = edge_for(a, 9)
    assert e.holder is None and e.provenance == "ambiguous" and e.holder_candidates == (7, 8)
    assert a.blockers == set()


def test_no_information_stays_unknown():
    e = edge_for(analyze_snapshot(snapshot(waits=[wait(9, None)])), 9)
    assert e.holder is None and e.provenance == "unknown"


def test_holder_handle_zero_means_holder_gone():
    e = edge_for(analyze_snapshot(snapshot(waits=[wait(9, 0)])), 9)
    assert e.holder is None and e.provenance == "holder_gone"


def test_only_granted_locks_count_as_holders():
    a = analyze_snapshot(snapshot(waits=[wait(9, None)], locks=[lock(7, status="W")]))
    assert edge_for(a, 9).provenance == "unknown"


def test_chain_depth_and_root_blockers():
    # 1 blocks 2, 2 blocks 3: 2 is both waiter and holder
    a = analyze_snapshot(snapshot(waits=[wait(2, 1, lock="L1"), wait(3, 2, lock="L2")]))
    assert a.root_blockers == {1} and a.blockers == {1, 2} and a.waiters == {2, 3}
    assert (a.depth[1], a.depth[2], a.depth[3]) == (0, 1, 2)


def test_two_waiters_on_one_blocker():
    a = analyze_snapshot(snapshot(waits=[wait(2, 1, seconds=3), wait(3, 1, seconds=40)]))
    assert a.blockers == {1} and a.waiters == {2, 3} and a.max_wait_seconds == 40


def test_cycle_detection_marks_edges_and_is_not_called_deadlock():
    a = analyze_snapshot(snapshot(waits=[wait(1, 2, lock="L1"), wait(2, 1, lock="L2")]))
    assert a.cycles == [(1, 2)]
    assert all(e.on_cycle for e in a.edges)
    assert a.root_blockers == set()


def test_find_cycles_canonical_and_deduplicated():
    assert find_cycles([(3, 1), (1, 2), (2, 3)]) == [(1, 2, 3)]
    assert find_cycles([(1, 2), (2, 3)]) == []
    assert find_cycles([(1, 1)]) == [(1,)]


def test_no_waits_gives_empty_analysis_but_counts_locks():
    a = analyze_snapshot(snapshot(locks=[lock(7), lock(8, status="W")]))
    assert a.edges == [] and a.total_locks == 2 and a.granted_locks == 1 and a.max_wait_seconds is None
