"""Deterministic diff engine (no LLM).

Turns row versions into change events, groups them by transaction and pattern,
and scores how much of an observed metric change each pattern explains.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Iterable, Optional

from .models import ChangeEvent, ChangeGroup, Version, money, parse_ts, PATTERN_TITLES


def versions_from_rows(rows: Iterable[dict]) -> list[Version]:
    out = []
    for r in rows:
        r = {k.lower(): v for k, v in r.items()}
        out.append(Version(
            item_id=int(r["item_id"]), order_id=int(r["order_id"]), product_id=int(r["product_id"]),
            quantity=int(r["quantity"]), unit_price=money(r["unit_price"]), changed_by=(r.get("changed_by") or None),
            sys_start=parse_ts(r["sys_start"]), sys_end=parse_ts(r.get("sys_end")),
            trans_id=(str(r["trans_id"]).strip() if r.get("trans_id") else None),
        ))
    return out


def _image(v: Version) -> dict:
    return {"order_id": v.order_id, "product_id": v.product_id, "quantity": v.quantity,
            "unit_price": str(v.unit_price), "revenue": str(v.revenue)}


def build_events(versions: list[Version], start, end, delete_log: Optional[list[dict]] = None) -> list[ChangeEvent]:
    """Derive insert / update / delete events that happened inside [start, end]."""
    by_item: dict[int, list[Version]] = defaultdict(list)
    for v in versions:
        by_item[v.item_id].append(v)

    baseline_keys = {v.natural_key() for v in versions if v.sys_start < start}
    seen_inserts: set = set()
    deleters: dict[int, list] = defaultdict(list)
    for d in delete_log or []:
        d = {k.lower(): val for k, val in d.items()}
        deleters[int(d["item_id"])].append((parse_ts(d["deleted_at"]), d.get("deleted_by")))

    events: list[ChangeEvent] = []
    for item_id, vs in by_item.items():
        vs.sort(key=lambda v: v.sys_start)
        for i, v in enumerate(vs):
            if i == 0:
                if v.sys_start >= start:  # row created inside the window
                    key = v.natural_key()
                    duplicate = key in baseline_keys or key in seen_inserts
                    seen_inserts.add(key)
                    events.append(ChangeEvent(
                        "insert", item_id, v.sys_start, v.trans_id or fmt(v.sys_start), v.changed_by,
                        "duplicate_load" if duplicate else "new_rows", v.revenue, None, _image(v)))
            else:
                prev = vs[i - 1]
                if (prev.quantity, prev.unit_price) == (v.quantity, v.unit_price) and prev.order_id == v.order_id:
                    continue  # no business-visible change
                price_changed = prev.unit_price != v.unit_price
                pattern = "price_change" if price_changed else "quantity_change"
                events.append(ChangeEvent(
                    "update", item_id, v.sys_start, v.trans_id or fmt(v.sys_start), v.changed_by,
                    pattern, v.revenue - prev.revenue, _image(prev), _image(v)))
        last = vs[-1]
        if last.sys_end is not None and last.sys_end <= end:  # version closed and not replaced -> deleted
            actor = None
            for when, who in deleters.get(item_id, []):
                if when and abs((when - last.sys_end).total_seconds()) < 5:
                    actor = who
            events.append(ChangeEvent(
                "delete", item_id, last.sys_end, "del@" + fmt(last.sys_end), actor,
                "rows_deleted", -last.revenue, _image(last), None))
    events.sort(key=lambda e: (e.at, e.item_id))
    return events


def fmt(ts) -> str:
    return ts.strftime("%Y-%m-%d %H:%M:%S.%f")


def group_events(events: list[ChangeEvent], sample_size: int = 5) -> list[ChangeGroup]:
    buckets: dict[tuple, list[ChangeEvent]] = defaultdict(list)
    for e in events:
        buckets[(e.txn, e.pattern)].append(e)
    groups = []
    for (txn, pattern), evs in buckets.items():
        actors = sorted({e.actor for e in evs if e.actor})
        groups.append(ChangeGroup(
            txn=txn, pattern=pattern, n_rows=len(evs), impact=sum((e.impact for e in evs), Decimal("0")),
            actors=actors, first_at=min(e.at for e in evs), last_at=max(e.at for e in evs),
            sample=[e.to_dict() for e in evs[:sample_size]]))
    groups.sort(key=lambda g: abs(g.impact), reverse=True)
    return groups


def impact_by_pattern(events: list[ChangeEvent]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for e in events:
        totals[e.pattern] += e.impact
    return dict(totals)


def reconcile(events: list[ChangeEvent], metric_start: Decimal, metric_end: Decimal) -> dict:
    """Cross-check: the sum of all event impacts must equal the change measured by two AS OF queries."""
    observed = money(metric_end) - money(metric_start)
    accounted = money(sum((e.impact for e in events), Decimal("0")))
    return {"observed": str(observed), "accounted": str(accounted), "ok": observed == accounted,
            "difference": str(observed - accounted)}


def score_hypothesis(pattern: str, events: list[ChangeEvent], metric_start: Decimal, metric_end: Decimal,
                     confirm_share: float = 0.60) -> dict:
    """How much of the observed change does ``pattern`` explain?"""
    observed = money(metric_end) - money(metric_start)
    explained = impact_by_pattern(events).get(pattern, Decimal("0"))
    n_rows = sum(1 for e in events if e.pattern == pattern)
    if observed == 0 or n_rows == 0:
        share = Decimal("0")
    else:
        share = explained / observed
    same_direction = observed != 0 and (explained > 0) == (observed > 0)
    confirmed = bool(n_rows and same_direction and share >= Decimal(str(confirm_share)))
    counterfactual = money(metric_end) - explained
    title = PATTERN_TITLES.get(pattern, pattern)
    if n_rows == 0:
        reason = f"No '{title.lower()}' events were found in the window."
    elif not same_direction:
        reason = f"'{title}' moved the metric the opposite way ({explained:+}), so it cannot explain the change."
    elif confirmed:
        if share > Decimal("1.05"):
            how = f"The net change is {observed:+} because other activity partly offset it."
        else:
            how = f"That is {float(share):.0%} of the net change of {observed:+}."
        reason = (f"'{title}' moved the metric by {explained:+}. {how} "
                  f"Without it the metric would be {counterfactual} instead of {money(metric_end)}.")
    else:
        reason = (f"'{title}' accounts for only {float(share):.0%} of the {observed:+} change "
                  f"(needs at least {confirm_share:.0%}).")
    return {"pattern": pattern, "title": title, "explained": str(explained), "observed": str(observed),
            "share": float(share), "rows": n_rows, "confirmed": confirmed,
            "counterfactual": str(counterfactual), "reason": reason}
