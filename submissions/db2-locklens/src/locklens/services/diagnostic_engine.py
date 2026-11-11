"""Deterministic, explainable diagnostic rules.

The engine only interprets what Db2 reported. It never claims a root cause the monitoring
data cannot establish, never reports a *confirmed* deadlock (that needs deadlock event
monitor data), and only *advises*: nothing here executes SQL against the monitored database.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import Finding, LockAnalysis, Severity, SessionInfo, Snapshot, WaitEdge


@dataclass(frozen=True)
class Thresholds:
    wait_warn_seconds: int = 10
    wait_critical_seconds: int = 60


_PROVENANCE_TEXT = {
    "db2_lockwait": "holder reported by Db2 (MON_GET_APPL_LOCKWAIT)",
    "lock_table_match": "holder inferred from MON_GET_LOCKS (single granted holder of the same lock name)",
    "ambiguous": "several applications hold this lock name",
    "holder_gone": "Db2 reports the holder no longer exists",
    "unknown": "holder not reported",
}

_FORCE_NOTE = ("If the holder cannot be contacted, a DBA may decide to end it (for example "
               "with FORCE APPLICATION), which rolls back its uncommitted work. LockLens never "
               "does this automatically.")


def _wait_severity(seconds: int | None, t: Thresholds) -> Severity:
    if seconds is None:
        return Severity.INFO
    if seconds >= t.wait_critical_seconds:
        return Severity.CRITICAL
    if seconds >= t.wait_warn_seconds:
        return Severity.WARNING
    return Severity.INFO


def _fmt_app(handle: int | None, sessions: dict[int, SessionInfo]) -> str:
    if handle is None:
        return "an unidentified application"
    info = sessions.get(handle)
    if not info:
        return f"application {handle}"
    extra = ", ".join(p for p in (info.application_name, info.system_auth_id) if p)
    return f"application {handle} ({extra})" if extra else f"application {handle}"


def _cap(text: str) -> str:
    """Upper-case only the first letter; the builtin would lowercase user and application names."""
    return text[:1].upper() + text[1:]


def _fmt_wait(seconds: int | None) -> str:
    return "unknown duration" if seconds is None else f"{seconds}s"


def _lock_text(e: WaitEdge) -> str:
    bits = [e.resource_label]
    if e.lock_mode_requested:
        bits.append(f"requested mode {e.lock_mode_requested}")
    if e.lock_mode_held:
        bits.append(f"held mode {e.lock_mode_held}")
    return ", ".join(bits)


def evaluate(snapshot: Snapshot, analysis: LockAnalysis, thresholds: Thresholds | None = None
             ) -> list[Finding]:
    t = thresholds or Thresholds()
    sessions = snapshot.sessions
    findings: list[Finding] = []

    # Monitoring limitations are findings too: the user must know what we could NOT see.
    errors = [n for n in snapshot.notes if n.level == "error"]
    if errors:
        findings.append(Finding(
            finding_type="MONITORING_LIMITED", severity=Severity.WARNING,
            title="Monitoring data is incomplete",
            explanation="Some Db2 monitoring information could not be read, so the picture below "
                        "may be missing locks or waits. Nothing is inferred about the missing parts.",
            evidence=[n.message for n in errors],
            recommendations=["Resolve the privilege or availability problem shown in the evidence, "
                             "then refresh."],
            subject_key="monitoring-limited", category="monitoring", persist=False))

    if not analysis.edges:
        if snapshot.waits_available:
            findings.append(Finding(
                finding_type="NO_LOCK_WAITS", severity=Severity.INFO,
                title="No lock waits observed in this snapshot",
                explanation="Db2 reported no application currently waiting for a lock. This describes "
                            "this moment only; short waits between refreshes can be missed.",
                evidence=[f"{analysis.total_locks} lock(s) currently listed by MON_GET_LOCKS"],
                subject_key="no-waits", persist=False))
        return findings

    # ---- per-wait rules ---------------------------------------------------------------
    by_blocker: dict[int, list[WaitEdge]] = {}
    for e in analysis.edges:
        if e.holder is not None:
            by_blocker.setdefault(e.holder, []).append(e)

    for e in analysis.edges:
        sev = _wait_severity(e.wait_seconds, t)
        waiter_txt = _fmt_app(e.waiter, sessions)
        if e.provenance in ("unknown", "ambiguous"):
            cand = (f" Candidate holders by lock name: {', '.join(map(str, e.holder_candidates))}."
                    if e.holder_candidates else "")
            findings.append(Finding(
                finding_type="UNKNOWN_BLOCKER",
                severity=Severity.WARNING if sev >= Severity.WARNING else Severity.INFO,
                title=f"{_cap(waiter_txt)} is waiting; the blocker could not be established",
                explanation=f"Db2 shows {waiter_txt} waiting for a lock for {_fmt_wait(e.wait_seconds)}, "
                            "but the holding application is not identified by the available monitoring "
                            f"data, so no blocking relationship is claimed.{cand}",
                evidence=[f"Lock: {_lock_text(e)}", f"Holder provenance: {_PROVENANCE_TEXT[e.provenance]}"],
                recommendations=["Query MON_GET_LOCKS filtered by this lock name to look for holders.",
                                 "Check whether your Db2 version/privileges expose HLD_APPLICATION_HANDLE."],
                affected_applications=[a for a in (e.waiter,) if a is not None],
                subject_key=f"unknown-blocker:{e.waiter}:{e.lock_name_hex}",
                waiter_handles=[a for a in (e.waiter,) if a is not None],
                lock_details=_lock_text(e), max_wait_seconds=e.wait_seconds,
                persist=sev >= Severity.WARNING))
        elif e.provenance == "holder_gone":
            findings.append(Finding(
                finding_type="HOLDER_NOT_PRESENT", severity=max(sev, Severity.WARNING),
                title=f"{_cap(waiter_txt)} waits on a lock whose holder no longer exists",
                explanation="Db2 reported application handle 0 as the holder. IBM documents this as a "
                            "lock held by a transaction that is being rolled back or an in-doubt "
                            "transaction that must be resolved, for example after a crash.",
                evidence=[f"Lock: {_lock_text(e)}", f"Waited: {_fmt_wait(e.wait_seconds)}"],
                recommendations=["Check the Db2 diagnostic log (db2diag.log) for rollback or crash "
                                 "recovery activity.",
                                 "If indoubt transactions are suspected, review them with LIST INDOUBT "
                                 "TRANSACTIONS; resolution is a DBA decision."],
                affected_applications=[a for a in (e.waiter,) if a is not None],
                subject_key=f"holder-gone:{e.waiter}:{e.lock_name_hex}",
                waiter_handles=[a for a in (e.waiter,) if a is not None],
                lock_details=_lock_text(e), max_wait_seconds=e.wait_seconds))
        elif sev >= Severity.WARNING:
            holder_txt = _fmt_app(e.holder, sessions)
            findings.append(Finding(
                finding_type="LONG_LOCK_WAIT", severity=sev,
                title=f"{_cap(waiter_txt)} has waited {_fmt_wait(e.wait_seconds)} for {holder_txt}",
                explanation=f"{_cap(waiter_txt)} has been waiting {_fmt_wait(e.wait_seconds)}, "
                            f"longer than the {'critical' if sev == Severity.CRITICAL else 'warning'} "
                            f"threshold ({t.wait_critical_seconds if sev == Severity.CRITICAL else t.wait_warn_seconds}s), "
                            f"for a lock held by {holder_txt}. A lock wait is normal in moderation; "
                            "it is not a deadlock.",
                evidence=[f"Lock: {_lock_text(e)}", f"Wait started: {e.wait_start_time or 'n/a'}",
                          f"Holder provenance: {_PROVENANCE_TEXT[e.provenance]}"],
                recommendations=[f"Find out what {holder_txt} is doing and whether its transaction "
                                 "should already have committed.",
                                 "Review LOCKTIMEOUT and application retry behaviour if waits of this "
                                 "length are not acceptable."],
                affected_applications=[a for a in (e.waiter, e.holder) if a is not None],
                subject_key=f"long-wait:{e.waiter}:{e.lock_name_hex}:{e.wait_start_time or ''}",
                blocker_handle=e.holder, waiter_handles=[a for a in (e.waiter,) if a is not None],
                lock_details=_lock_text(e), max_wait_seconds=e.wait_seconds))

    # ---- per-blocker rules ------------------------------------------------------------
    for holder, edges in sorted(by_blocker.items()):
        waiters = sorted({e.waiter for e in edges if e.waiter is not None})
        waits = [e.wait_seconds for e in edges if e.wait_seconds is not None]
        longest = max(waits) if waits else None
        is_root = holder in analysis.root_blockers
        sev = _wait_severity(longest, t)
        if len(waiters) >= 2:
            sev = max(sev, Severity.WARNING)
        holder_txt = _fmt_app(holder, sessions)
        info = sessions.get(holder)
        locks_txt = sorted({_lock_text(e) for e in edges})
        evidence = [f"Blocked application(s): {', '.join(map(str, waiters))}",
                    f"Longest wait: {_fmt_wait(longest)}",
                    f"Lock(s): {'; '.join(locks_txt)}",
                    f"Holder provenance: {_PROVENANCE_TEXT[edges[0].provenance]}"]
        if info and info.workload_state:
            evidence.append(f"Holder state reported by Db2: {info.workload_state}")
        findings.append(Finding(
            finding_type="BLOCKING_SESSION", severity=sev,
            title=f"{_cap(holder_txt)} is blocking {len(waiters)} application(s)",
            explanation=f"{_cap(holder_txt)} holds lock(s) that {len(waiters)} other "
                        f"application(s) are waiting for." +
                        (" It is not itself waiting on a lock, so it is the head of the blocking chain."
                         if is_root else " It is also waiting on another lock, so it is part of a chain."),
            evidence=evidence,
            recommendations=[f"Identify the owner of {holder_txt} and what it is doing.",
                             "Ask the owner to COMMIT or ROLLBACK if the work is finished.",
                             _FORCE_NOTE],
            affected_applications=[holder, *waiters],
            subject_key=f"blocker:{holder}", blocker_handle=holder, waiter_handles=waiters,
            lock_details="; ".join(locks_txt), max_wait_seconds=longest))

        state = (info.workload_state or "").upper() if info else ""
        if is_root and state == "UOWWAIT":
            findings.append(Finding(
                finding_type="IDLE_TRANSACTION_HOLDER", severity=sev,
                title=f"{_cap(holder_txt)} holds locks while idle inside a transaction",
                explanation="Db2 reports the holder in state UOWWAIT: its unit of work is open and Db2 "
                            "is waiting for its next request. This pattern is consistent with a "
                            "transaction that has not been committed or rolled back. Monitoring data "
                            "alone cannot show why the application stopped sending requests.",
                evidence=[f"Holder state: {info.workload_state}",
                          f"Blocked application(s): {', '.join(map(str, waiters))}",
                          f"Longest wait: {_fmt_wait(longest)}"],
                recommendations=["Ask the application owner whether a COMMIT/ROLLBACK is missing, the "
                                 "client is paused (debugger, user prompt) or the client has crashed.",
                                 "Consider shorter transactions and an idle-transaction policy in the "
                                 "application.", _FORCE_NOTE],
                affected_applications=[holder, *waiters],
                subject_key=f"idle-holder:{holder}", blocker_handle=holder, waiter_handles=waiters,
                lock_details="; ".join(locks_txt), max_wait_seconds=longest))
        elif is_root and state == "UOWEXEC":
            findings.append(Finding(
                finding_type="ACTIVE_HOLDER", severity=Severity.INFO,
                title=f"{_cap(holder_txt)} is still executing while holding locks",
                explanation="Db2 reports the holder in state UOWEXEC (executing a request), so this may "
                            "be a long-running statement rather than an abandoned transaction.",
                evidence=[f"Holder state: {info.workload_state}"],
                recommendations=["Inspect the holder's running statement (for example with "
                                 "MON_GET_ACTIVITY) before taking any action."],
                affected_applications=[holder], subject_key=f"active-holder:{holder}",
                blocker_handle=holder, persist=False))

    # ---- structural rules -------------------------------------------------------------
    deepest = max(analysis.depth.values(), default=0)
    if deepest >= 2:
        findings.append(Finding(
            finding_type="BLOCKING_CHAIN", severity=Severity.WARNING,
            title=f"Blocking chain {deepest + 1} applications deep",
            explanation="At least one application is waiting for a lock held by an application that is "
                        "itself waiting. Resolving the head of the chain unblocks the others in order.",
            evidence=[f"Root blocker(s): {', '.join(map(str, sorted(analysis.root_blockers))) or 'none'}",
                      f"Applications waiting: {len(analysis.waiters)}"],
            recommendations=["Start with the root blocker(s); the rest depend on them."],
            affected_applications=sorted(analysis.waiters | analysis.blockers),
            subject_key="chain:" + ",".join(map(str, sorted(analysis.root_blockers))),
            waiter_handles=sorted(analysis.waiters),
            blocker_handle=min(analysis.root_blockers) if analysis.root_blockers else None,
            max_wait_seconds=analysis.max_wait_seconds))

    for cyc in analysis.cycles:
        findings.append(Finding(
            finding_type="WAIT_CYCLE_OBSERVED", severity=Severity.CRITICAL,
            title="Circular wait observed: " + " -> ".join(map(str, cyc)) + f" -> {cyc[0]}",
            explanation="In this snapshot each listed application waits for a lock held by the next, "
                        "forming a cycle. Db2's deadlock detector normally resolves such cycles within "
                        "its check interval (DLCHKTIME) by rolling back one participant. This is a "
                        "point-in-time observation, NOT a confirmed deadlock record; confirming a "
                        "deadlock requires deadlock event monitor data.",
            evidence=["Wait-for cycle: " + " -> ".join(map(str, cyc)) + f" -> {cyc[0]}"],
            recommendations=["Refresh: if the cycle persists beyond DLCHKTIME, investigate the deadlock "
                             "detector settings.",
                             "Review the deadlock event monitor or db2diag.log for SQL0911N reason code 2 "
                             "entries to confirm whether a deadlock actually occurred.",
                             "Make applications access shared rows in a consistent order."],
            affected_applications=list(cyc),
            subject_key="cycle:" + ",".join(map(str, cyc)), category="possible_deadlock",
            waiter_handles=list(cyc), max_wait_seconds=analysis.max_wait_seconds))

    # Informational summary of short waits so the dashboard explains them too.
    if not any(f.finding_type in {"LONG_LOCK_WAIT", "BLOCKING_SESSION", "UNKNOWN_BLOCKER",
                                  "HOLDER_NOT_PRESENT", "WAIT_CYCLE_OBSERVED"} for f in findings):
        findings.append(Finding(
            finding_type="SHORT_LOCK_WAIT", severity=Severity.INFO,
            title=f"{len(analysis.waiters)} application(s) briefly waiting for locks",
            explanation="Lock waits below the warning threshold are normal in concurrent workloads.",
            evidence=[f"Longest wait: {_fmt_wait(analysis.max_wait_seconds)}"],
            subject_key="short-waits", persist=False))
    findings.sort(key=lambda f: (-int(f.severity), f.finding_type, f.subject_key))
    return findings
