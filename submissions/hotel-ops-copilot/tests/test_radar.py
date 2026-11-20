"""verify.py check 4 expects the planted AC story (rooms 307/312) to read as LOCALISED. Replay it over many run dates.

No Db2 needed: the seed is a pure function of the date, so the radar's 30-day window and LOCALISED rule can be
replayed for any "today". Matching reviews by the seed's own phrases stands in for Db2's VECTOR_DISTANCE match.
"""
import collections
import datetime as dt

import pytest

from hotelops import seed
from hotelops.radar import hot_rooms

# 20-21 Nov 2026 broke the old rule: a third floor-3 room drew two background AC complaints
DATES = sorted({dt.date(2026, 1, 3) + dt.timedelta(days=k) for k in range(0, 730, 9)}
               | {dt.date(2026, 11, 20), dt.date(2026, 11, 21), dt.date(2026, 1, 10), dt.date(2026, 2, 26),
                  dt.date(2027, 1, 18), dt.date(2026, 1, 27), dt.date(2027, 5, 20)})  # lowest 307/312 shares


def _rooms(ds, theme):
    phrases = seed.THEMES[theme]["phrases"]
    counts = collections.Counter(rv[2] for rv in ds.reviews if rv[4] <= 3 and (ds.today - rv[6]).days <= 30
                                 and any(p in rv[5] for p in phrases))
    rooms = [{"ROOM_NO": r, "REVIEWS": n} for r, n in counts.items()]
    return sorted(rooms, key=lambda x: (-x["REVIEWS"], x["ROOM_NO"])), sum(counts.values())


@pytest.mark.parametrize("today", DATES, ids=str)
def test_planted_complaints_read_as_localised(today):
    ds = seed.build(today)
    for theme, want in (("ac_noise", {"307", "312"}), ("hot_water", {"512"})):
        hot = hot_rooms(*_rooms(ds, theme))
        assert want <= {r["ROOM_NO"] for r in hot}, (theme, _rooms(ds, theme)[0][:4])


def test_spread_out_complaints_stay_systemic():
    rooms = [{"ROOM_NO": f"{n}", "REVIEWS": 2} for n in range(101, 108)]
    assert hot_rooms(rooms, 14) == []
    assert hot_rooms([], 0) == []
    assert hot_rooms([{"ROOM_NO": "307", "REVIEWS": 1}], 1) == []  # one complaint is not a pattern
