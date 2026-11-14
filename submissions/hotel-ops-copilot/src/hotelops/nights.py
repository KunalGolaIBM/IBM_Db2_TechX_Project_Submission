"""Pick stay dates for live checks (``verify.py`` and the Db2 integration tests).

The seed prices nights by season (Goa peak 18 Dec - 5 Jan) with a Friday / Saturday uplift, so a peak weekend
can sit above a room type's guardrail ceiling. A check that hard-codes "today + N days" therefore passes on most
dates and fails on others: on 14 Nov 2026, "today + 41" was Christmas night, where the Standard rate is above
the ceiling and a 3% cut is still out of band. These helpers pick the first night at or after the preferred
offset whose current rate leaves room for the change the check is about to make, so every check behaves the
same whatever the date. ``tests/test_nights.py`` replays each check against a full year of start dates.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

# SP_PROPOSE_ACTION accepts stays up to 90 days ahead, and the seed prices nights up to today + 90.
HORIZON_DAYS = 89

# ok(window_rates, floor, ceiling) -> bool
WindowCheck = Callable[[Sequence[float], float, float], bool]


def in_band(rate: float, factors: Iterable[float], floor: float, ceiling: float, margin: float = 0.01) -> bool:
    """True when ``rate * f`` stays inside [floor, ceiling] for every factor, with a margin for rounding."""
    return all(floor * (1 + margin) <= rate * f <= ceiling * (1 - margin) for f in factors)


def first_window(rates: Sequence[float | None], start: int, ok: Callable[[Sequence[float]], bool], *,
                 span: int = 1, avoid: Iterable[int] = (), stop: int = HORIZON_DAYS) -> int | None:
    """First offset k >= start where nights k .. k+span-1 are priced, none is in ``avoid``, and ``ok`` holds.

    ``rates[k]`` is the rate k days from today (None when the night is not priced).
    """
    avoid = set(avoid)
    for k in range(max(start, 0), stop - span + 2):
        window = list(rates[k:k + span])
        if len(window) < span or any(r is None for r in window) or avoid & set(range(k, k + span)):
            continue
        if ok(window):
            return k
    return None


@dataclass(frozen=True)
class Nights:
    offset: int
    dates: list[str]
    rates: list[float]
    floor: float
    ceiling: float

    @property
    def night(self) -> str:
        return self.dates[0]

    @property
    def rate(self) -> float:
        return self.rates[0]


def pick_nights(db, code: str, start: int, factors: Iterable[float] = (1.0,), *, span: int = 1,
                ok: WindowCheck | None = None, avoid: Iterable[int] = (), stop: int = HORIZON_DAYS) -> Nights:
    """Nights for room type ``code`` from ``start`` days ahead where a change by each factor stays in band.

    ``ok`` replaces the default rule (every night in the window times every factor inside the band).
    Raises LookupError when no night in the horizon qualifies, so a check fails loudly instead of silently.
    """
    factors = tuple(factors)
    today = dt.date.fromisoformat(str(db.scalar("VALUES CURRENT DATE")))
    band = db.query("SELECT FLOOR_RATE, CEILING_RATE FROM ROOM_TYPES WHERE CODE = ?", (code,))
    if not band:
        raise LookupError(f"unknown room type {code}")
    floor, ceiling = float(band[0]["FLOOR_RATE"]), float(band[0]["CEILING_RATE"])
    rows = db.query("SELECT P.STAY_DATE, P.RATE FROM RATE_PLAN P JOIN ROOM_TYPES T ON T.ROOM_TYPE_ID = P.ROOM_TYPE_ID "
                    "WHERE T.CODE = ? AND P.STAY_DATE BETWEEN ? AND ?",
                    (code, today.isoformat(), (today + dt.timedelta(days=stop)).isoformat()))
    rates: list[float | None] = [None] * (stop + 1)
    for r in rows:
        k = (dt.date.fromisoformat(str(r["STAY_DATE"])) - today).days
        if 0 <= k <= stop:
            rates[k] = float(r["RATE"])
    rule = ok or (lambda w, lo, hi: all(in_band(x, factors, lo, hi) for x in w))
    k = first_window(rates, start, lambda w: rule(w, floor, ceiling), span=span, avoid=avoid, stop=stop)
    if k is None:
        raise LookupError(f"no {code} night between today+{start} and today+{stop} leaves room for {factors}")
    days = [today + dt.timedelta(days=k + i) for i in range(span)]
    return Nights(k, [d.isoformat() for d in days], [rates[k + i] for i in range(span)], floor, ceiling)
