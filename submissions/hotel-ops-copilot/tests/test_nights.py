"""The live checks pick their stay dates with hotelops.nights. Replay every one against two years of run dates.

No Db2 needed: the seed's rate plan is a pure function of the date (``seed.rate_for``), so the same night
selection the integration tests and verify.py make against Db2 can be replayed for any "today".
"""
import datetime as dt

import pytest

from hotelops.nights import HORIZON_DAYS, first_window, in_band
from hotelops.seed import ROOM_TYPES, rate_for

BAND = {code: (base, float(floor), float(ceil)) for _id, code, _n, _t, base, floor, ceil, _o in ROOM_TYPES}


def _rates(code, today):
    base = BAND[code][0]
    return [rate_for(base, today + dt.timedelta(days=k)) for k in range(HORIZON_DAYS + 1)]


def _factors(*fs):
    return lambda w, lo, hi: all(in_band(x, fs, lo, hi) for x in w)


# (room type, preferred offset, rule, span, stop) in the order tests/test_db2_integration.py asks for them
INTEGRATION_CHECKS = [
    ("PRM", 30, lambda w, lo, hi: in_band(w[0], (0.9,), lo, hi) and all(abs(w[0] * 0.9 - r) / r <= 0.3 for r in w),
     2, HORIZON_DAYS),
    ("STD", 40, lambda w, lo, hi: in_band(w[0], (0.6,), lo, hi) or in_band(w[0], (1.4,), lo, hi), 1, HORIZON_DAYS),
    ("DLX", 33, _factors(1.05), 1, HORIZON_DAYS),
    ("STD", 20, lambda w, lo, hi: in_band(w[0], (1.02, 1.03), lo, hi)
     and (in_band(w[0], (1.12,), lo, hi) or in_band(w[0], (0.88,), lo, hi)), 1, HORIZON_DAYS),
    ("STD", 2, _factors(1.02), 1, 6),
    ("STD", 25, _factors(1.04, 0.97), 1, HORIZON_DAYS),
    ("STD", 30, _factors(1.02), 1, HORIZON_DAYS),
    ("STD", 41, _factors(0.97, 0.97 * 0.98), 1, HORIZON_DAYS),
    ("STD", 42, _factors(0.97, 0.97 * 0.98), 1, HORIZON_DAYS),
    ("STD", 43, _factors(0.97, 0.97 * 0.98), 1, HORIZON_DAYS),
]
VERIFY_CHECKS = [("STD", 12, _factors(1.02), 1, HORIZON_DAYS), ("STD", 13, _factors(0.98), 1, HORIZON_DAYS)]
RUN_DATES = [dt.date(2026, 1, 1) + dt.timedelta(days=i) for i in range(731)]


def _find(today, code, start, rule, span, stop, avoid=()):
    _base, lo, hi = BAND[code]
    return first_window(_rates(code, today), start, lambda w: rule(w, lo, hi), span=span, avoid=avoid, stop=stop)


def _check_run_date(today):
    used: dict[str, set[int]] = {}
    for code, start, rule, span, stop in INTEGRATION_CHECKS:
        avoid = used.setdefault(code, set())
        k = _find(today, code, start, rule, span, stop, avoid)
        assert k is not None, (today, code, start)
        assert not avoid & set(range(k, k + span))
        avoid.update(range(k, k + span))
    for code, start, rule, span, stop in VERIFY_CHECKS:
        assert _find(today, code, start, rule, span, stop) is not None, (today, code, start)


def test_every_live_check_finds_a_night_on_every_run_date_for_two_years():
    for today in RUN_DATES:  # every day of 2026 and 2027: peak season, weekends, month ends, leap-free years
        _check_run_date(today)


@pytest.mark.parametrize("today", [dt.date(2026, 11, 14), dt.date(2026, 12, 13), dt.date(2026, 12, 24)],
                         ids=lambda d: d.isoformat())
def test_dates_that_used_to_break_the_checks(today):
    # The old fixed offsets landed on peak-season weekend nights above the Standard ceiling from these dates:
    # 14 Nov + 41 = 25 Dec (tests), 13 Dec + 12 / + 13 = 25 / 26 Dec (verify.py), 24 Dec + 2 = 26 Dec (tests).
    _check_run_date(today)


def test_hard_coded_offsets_were_date_dependent():
    # Why the helper exists: on 14 Nov 2026 "today + 41" is Christmas night, and a 3% cut of the Standard rate
    # there is still above the guardrail ceiling, so the old hard-coded test failed on that date.
    today = dt.date(2026, 11, 14)
    _base, lo, hi = BAND["STD"]
    rate = _rates("STD", today)[41]
    assert today + dt.timedelta(days=41) == dt.date(2026, 12, 25)
    assert not in_band(rate, (0.97,), lo, hi)


def test_first_window_respects_span_avoid_and_stop():
    rates = [100.0, None, 100.0, 100.0, 100.0, 100.0]
    ok = lambda w: True  # noqa: E731
    assert first_window(rates, 0, ok) == 0
    assert first_window(rates, 0, ok, span=2) == 2  # night 1 is not priced
    assert first_window(rates, 0, ok, span=2, avoid={3}) == 4
    assert first_window(rates, 0, ok, span=2, avoid={3}, stop=4) is None
    assert first_window(rates, 0, lambda w: w[0] > 100) is None
