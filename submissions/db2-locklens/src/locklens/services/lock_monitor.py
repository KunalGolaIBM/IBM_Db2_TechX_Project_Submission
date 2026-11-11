"""Turns a raw :class:`Snapshot` into blocking/waiting relationships.

Every relationship carries a *provenance* so the UI and the diagnostics never present a guess
as a fact:

``db2_lockwait``      Db2 itself reported the holder (HLD_APPLICATION_HANDLE).
``lock_table_match``  Db2 did not name the holder, but MON_GET_LOCKS shows exactly one other
                      application holding a granted lock with the same lock name.
``ambiguous``         Several other applications hold that lock name; none is singled out.
``holder_gone``       Db2 reported handle 0: the holder no longer exists (for example a
                      transaction being rolled back, or an in-doubt transaction).
``unknown``           No holder could be established. It stays unknown; we do not guess.
"""

from __future__ import annotations

from collections import defaultdict

from ..models import LockAnalysis, ResourceInfo, Snapshot, WaitEdge


def _label(snapshot: Snapshot, lock_name_hex: str | None, object_type: str | None) -> str:
    res: ResourceInfo | None = snapshot.resources.get(lock_name_hex or "")
    if res is not None:
        return res.label if res.object_type or res.table_name else (
            f"{object_type} lock" if object_type else res.label)
    if object_type:
        return f"{object_type} lock"
    return "Lock (object not resolved)"


def build_edges(snapshot: Snapshot) -> list[WaitEdge]:
    granted: dict[str, set[int]] = defaultdict(set)
    for lk in snapshot.locks:
        if lk.lock_status == "G" and lk.lock_name_hex and lk.application_handle is not None:
            granted[lk.lock_name_hex].add(lk.application_handle)

    edges: list[WaitEdge] = []
    for w in snapshot.waits:
        holder: int | None = None
        candidates: tuple[int, ...] = ()
        reported = w.hld_application_handle
        if reported == 0:
            provenance = "holder_gone"
        elif reported is not None and reported != w.req_application_handle:
            holder, provenance = reported, "db2_lockwait"
        else:
            others = sorted(granted.get(w.lock_name_hex or "", set()) - {w.req_application_handle})
            if len(others) == 1:
                holder, provenance = others[0], "lock_table_match"
            elif len(others) > 1:
                candidates, provenance = tuple(others), "ambiguous"
            else:
                provenance = "unknown"
        edges.append(WaitEdge(
            waiter=w.req_application_handle, holder=holder, provenance=provenance,
            holder_candidates=candidates, lock_name_hex=w.lock_name_hex,
            lock_object_type=w.lock_object_type, lock_mode_held=w.lock_mode,
            lock_mode_requested=w.lock_mode_requested, wait_seconds=w.wait_seconds,
            wait_start_time=w.lock_wait_start_time,
            resource_label=_label(snapshot, w.lock_name_hex, w.lock_object_type)))
    return edges


def find_cycles(pairs: list[tuple[int, int]]) -> list[tuple[int, ...]]:
    """Find wait-for cycles. ``pairs`` are (waiter, holder). Cycles are canonicalised."""
    graph: dict[int, set[int]] = defaultdict(set)
    for waiter, holder in pairs:
        graph[waiter].add(holder)
    cycles: set[tuple[int, ...]] = set()

    def dfs(node: int, path: list[int], on_path: set[int]) -> None:
        for nxt in sorted(graph.get(node, ())):
            if nxt in on_path:
                cyc = path[path.index(nxt):]
                i = cyc.index(min(cyc))
                cycles.add(tuple(cyc[i:] + cyc[:i]))
            elif nxt not in done:
                dfs(nxt, path + [nxt], on_path | {nxt})
        done.add(node)

    done: set[int] = set()
    for start in sorted(graph):
        if start not in done:
            dfs(start, [start], {start})
    return sorted(cycles)


def _depths(edges: list[WaitEdge]) -> dict[int, int]:
    """Depth 0 = not waiting on a known holder; N = N hops from a root blocker."""
    holders_of: dict[int, set[int]] = defaultdict(set)
    for e in edges:
        if e.waiter is not None and e.holder is not None:
            holders_of[e.waiter].add(e.holder)
    memo: dict[int, int] = {}

    def depth(app: int, seen: frozenset[int]) -> int:
        if app in memo:
            return memo[app]
        parents = [h for h in holders_of.get(app, ()) if h not in seen]
        value = 0 if not parents else 1 + max(depth(h, seen | {app}) for h in parents)
        memo[app] = value
        return value

    apps = set(holders_of) | {h for hs in holders_of.values() for h in hs}
    return {a: depth(a, frozenset()) for a in apps}


def analyze_snapshot(snapshot: Snapshot) -> LockAnalysis:
    edges = build_edges(snapshot)
    waiters = {e.waiter for e in edges if e.waiter is not None}
    blockers = {e.holder for e in edges if e.holder is not None}
    pairs = [(e.waiter, e.holder) for e in edges if e.waiter is not None and e.holder is not None]
    cycles = find_cycles(pairs)
    cycle_pairs: set[tuple[int, int]] = set()
    for cyc in cycles:
        for i, node in enumerate(cyc):
            cycle_pairs.add((node, cyc[(i + 1) % len(cyc)]))
    marked = [
        WaitEdge(**{**e.__dict__, "on_cycle": (e.waiter, e.holder) in cycle_pairs}) for e in edges]
    waits = [e.wait_seconds for e in marked if e.wait_seconds is not None]
    return LockAnalysis(
        edges=marked, waiters=waiters, blockers=blockers,
        root_blockers={b for b in blockers if b not in waiters},
        cycles=cycles, depth=_depths(marked),
        total_locks=len(snapshot.locks),
        granted_locks=sum(1 for lk in snapshot.locks if lk.lock_status == "G"),
        max_wait_seconds=max(waits) if waits else None)
