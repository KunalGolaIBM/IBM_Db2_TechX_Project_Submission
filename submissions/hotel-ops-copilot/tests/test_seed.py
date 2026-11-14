import datetime as dt

from hotelops import seed

TODAY = dt.date(2026, 11, 8)


def test_seed_is_deterministic():
    a, b = seed.build(TODAY), seed.build(TODAY)
    assert a.reservations == b.reservations
    assert a.reviews == b.reviews


def test_no_double_booked_rooms():
    ds = seed.build(TODAY)
    active = [r for r in ds.reservations if r[8] in ("CONFIRMED", "CHECKED_IN", "CHECKED_OUT")]
    by_room: dict[str, list] = {}
    for r in active:
        by_room.setdefault(r[3], []).append((r[4], r[5]))
    for room, stays in by_room.items():
        stays.sort()
        for (_a_in, a_out), (b_in, _b_out) in zip(stays, stays[1:], strict=False):
            assert b_in >= a_out, f"room {room} double booked"


def test_planted_scenarios_present():
    ds = seed.build(TODAY)
    vip = [r for r in ds.reservations if r[0] == ds.scenario["vip_reservation_id"]][0]
    assert vip[1] == 901 and vip[4] == TODAY + dt.timedelta(days=1)
    ac = [r for r in ds.reviews if r[2] in ("307", "312") and "air" in r[5].lower()
          or r[2] in ("307", "312") and "AC" in r[5]]
    assert len(ac) >= 3
    assert len(ds.rooms) == 72
    assert all(3200 <= rate for _, _, rate in ds.rate_plan)


def test_rate_band_respected():
    for _type_id, _code, _, _, base, floor, ceiling, _ in seed.ROOM_TYPES:
        assert floor <= base <= ceiling


def test_planted_review_stories_hold_on_any_anchor_date():
    for offset in range(0, 28, 3):  # the data is regenerated relative to "today"
        today = TODAY + dt.timedelta(days=offset)
        ds = seed.build(today)
        for room, (theme, target) in seed.PLANTED_REVIEW_TARGETS.items():
            n = sum(1 for rv in ds.reviews if rv[2] == room and (today - rv[6]).days <= 24
                    and any(p in rv[5] for p in seed.THEMES[theme]["phrases"]))
            assert n >= target, f"{today}: room {room} has only {n} {theme} reviews"
        assert all(rv[6] <= today for rv in ds.reviews)


def test_no_booking_is_in_the_future():
    import datetime as dt

    now = dt.datetime.combine(TODAY, dt.time(2, 15))  # early in the day, as on a 02:15 UTC setup
    ds = seed.build(TODAY, now)
    assert max(r[11] for r in ds.reservations) <= now
