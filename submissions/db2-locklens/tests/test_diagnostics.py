"""Deterministic diagnostic rules."""

from helpers import lock, resource, session, snapshot, wait

from locklens.models import Severity
from locklens.services.diagnostic_engine import Thresholds, evaluate
from locklens.services.lock_monitor import analyze_snapshot

T = Thresholds(wait_warn_seconds=10, wait_critical_seconds=60)


def run(snap, t=T):
    return evaluate(snap, analyze_snapshot(snap), t)


def types(findings):
    return [f.finding_type for f in findings]


def test_no_waits_is_informational_and_not_persisted():
    f = run(snapshot(locks=[lock(7)]))
    assert types(f) == ["NO_LOCK_WAITS"] and f[0].severity == Severity.INFO and not f[0].persist


def test_short_wait_is_info_only_and_never_a_deadlock():
    f = run(snapshot(waits=[wait(9, 7, seconds=2)]))
    assert max(x.severity for x in f) == Severity.INFO
    assert not any("DEADLOCK" in x.finding_type for x in f)
    assert "BLOCKING_SESSION" in types(f)


def test_wait_over_warning_threshold_is_warning_and_over_critical_is_critical():
    assert run(snapshot(waits=[wait(9, 7, seconds=15)]))[0].severity == Severity.WARNING
    crit = run(snapshot(waits=[wait(9, 7, seconds=75)]))
    assert crit[0].severity == Severity.CRITICAL
    assert "LONG_LOCK_WAIT" in types(crit)


def test_thresholds_are_configurable():
    f = run(snapshot(waits=[wait(9, 7, seconds=15)]), Thresholds(5, 12))
    assert f[0].severity == Severity.CRITICAL


def test_every_finding_has_required_structure():
    f = run(snapshot(waits=[wait(9, 7, seconds=30)], sessions=[session(7), session(9)], resources=[resource()]))
    for x in f:
        assert x.severity in Severity and x.title and x.explanation and x.finding_type
        assert isinstance(x.evidence, list) and isinstance(x.affected_applications, list)


def test_blocking_session_names_blocker_waiters_and_object():
    f = run(snapshot(waits=[wait(9, 7, seconds=30), wait(10, 7, seconds=5)],
                     sessions=[session(7, "db2bp", "ALICE")], resources=[resource()]))
    b = next(x for x in f if x.finding_type == "BLOCKING_SESSION")
    assert b.blocker_handle == 7 and b.waiter_handles == [9, 10] and b.max_wait_seconds == 30
    assert b.severity == Severity.WARNING
    assert "ALICE" in b.title and any("ACCOUNTS" in e for e in b.evidence)
    assert b.subject_key == "blocker:7"
    assert any("FORCE APPLICATION" in r and "never" in r for r in b.recommendations)


def test_two_waiters_escalate_to_warning_even_if_waits_are_short():
    f = run(snapshot(waits=[wait(9, 7, seconds=1), wait(10, 7, seconds=1)]))
    assert next(x for x in f if x.finding_type == "BLOCKING_SESSION").severity == Severity.WARNING


def test_idle_holder_in_uowwait_is_flagged_with_cautious_wording():
    f = run(snapshot(waits=[wait(9, 7, seconds=20)], sessions=[session(7, state="UOWWAIT")]))
    idle = next(x for x in f if x.finding_type == "IDLE_TRANSACTION_HOLDER")
    assert "UOWWAIT" in " ".join(idle.evidence) and "consistent with" in idle.explanation
    assert "cannot show why" in idle.explanation          # does not claim a root cause


def test_no_idle_claim_without_state_information():
    f = run(snapshot(waits=[wait(9, 7, seconds=120)]))     # no session info at all
    assert "IDLE_TRANSACTION_HOLDER" not in types(f)


def test_executing_holder_is_not_called_idle():
    f = run(snapshot(waits=[wait(9, 7, seconds=20)], sessions=[session(7, state="UOWEXEC")]))
    assert "IDLE_TRANSACTION_HOLDER" not in types(f) and "ACTIVE_HOLDER" in types(f)


def test_unknown_holder_makes_no_blocking_claim():
    f = run(snapshot(waits=[wait(9, None, seconds=90)]))
    assert "BLOCKING_SESSION" not in types(f)
    u = next(x for x in f if x.finding_type == "UNKNOWN_BLOCKER")
    assert u.blocker_handle is None and u.severity == Severity.WARNING
    assert "no blocking relationship is claimed" in u.explanation


def test_holder_zero_explains_rollback_or_indoubt():
    f = run(snapshot(waits=[wait(9, 0, seconds=3)]))
    g = next(x for x in f if x.finding_type == "HOLDER_NOT_PRESENT")
    assert g.severity >= Severity.WARNING and "in-doubt" in g.explanation


def test_chain_finding_for_three_deep_blocking():
    f = run(snapshot(waits=[wait(2, 1, lock="L1", seconds=5), wait(3, 2, lock="L2", seconds=5)]))
    assert "BLOCKING_CHAIN" in types(f)


def test_cycle_is_reported_as_observation_not_confirmed_deadlock():
    f = run(snapshot(waits=[wait(1, 2, lock="L1", seconds=4), wait(2, 1, lock="L2", seconds=4)]))
    c = next(x for x in f if x.finding_type == "WAIT_CYCLE_OBSERVED")
    assert c.severity == Severity.CRITICAL and c.category == "possible_deadlock"
    assert "NOT a confirmed deadlock" in c.explanation
    assert not any(x.finding_type == "DEADLOCK" for x in f)


def test_monitoring_limits_surface_as_non_persistent_finding():
    from locklens.models import Note
    snap = snapshot()
    snap.notes.append(Note("error", "Not authorized to read MON_GET_LOCKS"))
    f = run(snap)
    m = next(x for x in f if x.finding_type == "MONITORING_LIMITED")
    assert not m.persist and "Not authorized" in m.evidence[0]


def test_findings_sorted_most_severe_first():
    f = run(snapshot(waits=[wait(9, 7, seconds=75), wait(10, 8, seconds=1)]))
    sev = [int(x.severity) for x in f]
    assert sev == sorted(sev, reverse=True)


def test_advice_never_contains_executable_destructive_sql():
    f = run(snapshot(waits=[wait(9, 7, seconds=75)], sessions=[session(7, state="UOWWAIT")]))
    text = " ".join(" ".join(x.recommendations) for x in f)
    assert "db2 force" not in text.lower() and "kill" not in text.lower()


def test_idle_holder_with_a_short_wait_is_informational_not_warning():
    f = run(snapshot(waits=[wait(9, 7, seconds=2)], sessions=[session(7, state="UOWWAIT")]))
    idle = next(x for x in f if x.finding_type == "IDLE_TRANSACTION_HOLDER")
    assert idle.severity == Severity.INFO
