"""Property-based test of the Db2 guardrails: thousands of random proposals, every decision checked.

``run_fuzz`` generates random agent proposals (valid ones, near-misses on every boundary, and garbage),
sends each to ``SP_PROPOSE_ACTION`` with the agent's own credentials, and compares Db2's decision with an
independent Python oracle written from the business rules. Everything runs in one transaction that is
rolled back, so nothing is persisted. A single disagreement means a guardrail does not do what we claim.
"""
from __future__ import annotations

import datetime as dt
import json
import random
import time
from collections import Counter

from .config import SCHEMA, load_settings
from .db import OUT_TEXT, Db2, Db2Error

PRIORITIES = ["LOW", "MEDIUM", "HIGH", "URGENT"]


def _connect(role: str) -> Db2:
    s = load_settings().db2
    user, pw = (s.admin_user, s.admin_password) if role == "admin" else (s.agent_user, s.agent_password)
    return Db2(s.conn_str(user, pw), f"fuzz-{role}")


class Oracle:
    """The guardrail rules, re-implemented in Python from the spec (not from the SQL)."""

    def __init__(self, admin: Db2, agent_user: str):
        self.today = dt.date.fromisoformat(str(admin.scalar("VALUES CURRENT DATE")))
        # rule: the agent may only act on the hotels it is scoped to; everything else does not exist for it
        self.scope = {r["PROPERTY_ID"] for r in admin.query(
            "SELECT PROPERTY_ID FROM AGENT_SCOPE WHERE AUTH_ID = ?", (agent_user.upper(),))}
        self.bands = {r["CODE"]: (float(r["FLOOR_RATE"]), float(r["CEILING_RATE"]), r["PROPERTY_ID"])
                      for r in admin.query("SELECT CODE, FLOOR_RATE, CEILING_RATE, PROPERTY_ID FROM ROOM_TYPES")}
        self.rooms = {r["ROOM_NO"]: r["PROPERTY_ID"] for r in admin.query("SELECT ROOM_NO, PROPERTY_ID FROM ROOMS")}
        self.res = {r["RESERVATION_ID"]: (r["STATUS"], r["AI_CONSENT"], r["PROPERTY_ID"]) for r in admin.query(
            "SELECT X.RESERVATION_ID, X.STATUS, G.AI_CONSENT, X.PROPERTY_ID FROM RESERVATIONS X JOIN GUESTS G "
            "ON G.GUEST_ID = X.GUEST_ID")}
        self.nightly = [(r["CODE"], str(r["STAY_DATE"]), float(r["RATE"])) for r in admin.query(
            "SELECT RT.CODE, RP.STAY_DATE, RP.RATE FROM RATE_PLAN RP JOIN ROOM_TYPES RT "
            "ON RT.ROOM_TYPE_ID = RP.ROOM_TYPE_ID WHERE RP.STAY_DATE BETWEEN CURRENT DATE + 8 DAYS "
            "AND CURRENT DATE + 60 DAYS ORDER BY RT.CODE, RP.STAY_DATE")]
        self.pending = {(r["ACTION_TYPE"], r["PAYLOAD"]) for r in admin.query(
            "SELECT ACTION_TYPE, PAYLOAD FROM AGENT_ACTIONS WHERE STATUS = 'PENDING' AND PROPERTY_ID IN "
            "(SELECT PROPERTY_ID FROM AGENT_SCOPE WHERE AUTH_ID = ?)", (agent_user.upper(),))}

    def _visible_code(self, code) -> bool:
        return code in self.bands and self.bands[code][2] in self.scope

    def decide(self, action_type: str, payload: str) -> str:
        """Expected outcome: REJECTED, DUPLICATE or PENDING (autonomy is off during the fuzz)."""
        try:
            p = json.loads(payload)
            if not isinstance(p, dict):
                raise ValueError
        except ValueError:
            return "REJECTED"
        if action_type == "RATE_CHANGE":
            code, start, end, rate = (p.get(k) for k in ("room_type_code", "start_date", "end_date", "new_rate"))
            if None in (code, start, end, rate):
                return "REJECTED"
            if not self._visible_code(code):
                return "REJECTED"
            start, end = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
            if start < self.today or end < start or end > self.today + dt.timedelta(days=90):
                return "REJECTED"
            lo, hi, _ = self.bands[code]
            if not lo <= float(rate) <= hi:
                return "REJECTED"
        elif action_type == "ROOM_UPGRADE":
            status, consent, prop = self.res.get(p.get("reservation_id"), (None, None, None))
            if status not in ("CONFIRMED", "CHECKED_IN") or consent != "Y" or prop not in self.scope:
                return "REJECTED"
            target = p.get("to_room_type_code")
            if not self._visible_code(target) or self.bands[target][2] != prop:  # upgrades stay in the same hotel
                return "REJECTED"
        elif action_type == "MAINTENANCE":
            if self.rooms.get(p.get("room_no")) not in self.scope or p.get("priority") not in PRIORITIES:
                return "REJECTED"
        else:
            return "REJECTED"
        key = (action_type, payload)
        if key in self.pending:
            return "DUPLICATE"
        self.pending.add(key)
        return "PENDING"


def _generate(rng: random.Random, o: Oracle) -> tuple[str, str, str]:
    """One random proposal: (category, action_type, payload_json)."""
    codes = sorted(o.bands)
    kind = rng.choices(["rate", "nudge", "upgrade", "maint", "type", "json", "repeat"], [44, 6, 18, 18, 4, 5, 5])[0]
    if kind == "nudge" and o.nightly:  # a small change to a real night's rate: what earned autonomy may apply
        code, night, rate = rng.choice(o.nightly)
        p = {"room_type_code": code, "start_date": night, "end_date": night,
             "new_rate": round(rate * (1 + rng.uniform(-0.03, 0.03)), 2)}
        return "price nudge", "RATE_CHANGE", json.dumps(p)
    if kind == "nudge":
        kind = "rate"
    if kind == "rate":
        code = rng.choice(codes + ["XXX", "std", "SUITE"]) if rng.random() < 0.15 else rng.choice(codes)
        lo, hi, _ = o.bands.get(code, (3000.0, 30000.0, None))
        start = o.today + dt.timedelta(days=rng.choice([rng.randint(-5, 100), 0, 90, 91, -1]))
        end = start + dt.timedelta(days=rng.choice([rng.randint(0, 6), -1, 0]))
        rate = rng.choice([lo, hi, lo - 0.01, hi + 0.01, round(rng.uniform(lo * 0.5, hi * 1.5), 2)])
        p = {"room_type_code": code, "start_date": start.isoformat(), "end_date": end.isoformat(),
             "new_rate": round(rate, 2)}
        if rng.random() < 0.06:
            p.pop(rng.choice(list(p)))
        return "rate change", "RATE_CHANGE", json.dumps(p)
    if kind == "upgrade":
        rid = rng.choice(list(o.res)) if rng.random() < 0.9 else rng.randint(1, 99)
        code = rng.choice(codes + ["PENTHOUSE"])
        return "room upgrade", "ROOM_UPGRADE", json.dumps({"reservation_id": rid, "to_room_type_code": code})
    if kind == "maint":
        room = rng.choice(sorted(o.rooms)) if rng.random() < 0.85 else rng.choice(["999", "abc", "0", "1201"])
        prio = rng.choice(PRIORITIES) if rng.random() < 0.85 else rng.choice(["CRITICAL", "low", "", "P1"])
        p = {"room_no": room, "category": rng.choice(["HVAC", "PLUMBING", "GENERAL"]), "priority": prio,
             "description": "fuzz", "take_out_of_order": rng.random() < 0.3}
        return "maintenance", "MAINTENANCE", json.dumps(p)
    if kind == "type":
        return "unknown type", rng.choice(["DELETE_GUEST", "GRANT", "rate_change", "SQL"]), json.dumps({"x": 1})
    if kind == "json":
        return "malformed JSON", "RATE_CHANGE", rng.choice(["not json", "{", "[1, 2", "{'a': 1}", ""])
    return "repeat", "", ""  # filled in by run_fuzz with an earlier payload (duplicate detection)


def run_fuzz(n: int = 1000, seed: int = 7) -> dict:
    admin, agent = _connect("admin"), _connect("agent")
    import ibm_db

    rng = random.Random(seed)
    oracle = Oracle(admin, load_settings().db2.agent_user)
    admin.close()
    history: list[tuple[str, str]] = []
    by_cat: Counter = Counter()
    outcomes: Counter = Counter()
    mismatches: list[dict] = []
    autonomous = 0
    t0 = time.time()
    ibm_db.autocommit(agent.conn, ibm_db.SQL_AUTOCOMMIT_OFF)
    try:
        for _ in range(n):
            cat, action_type, payload = _generate(rng, oracle)
            while cat == "repeat" and not history:  # nothing to repeat yet: draw another proposal, so n is exact
                cat, action_type, payload = _generate(rng, oracle)
            if cat == "repeat":
                action_type, payload = rng.choice(history)
            expected = oracle.decide(action_type, payload)
            try:
                out = agent.call(f"{SCHEMA}.SP_PROPOSE_ACTION", "fuzz", action_type, payload, "guardrail fuzz",
                                 0, OUT_TEXT)
                msg = str(out[5])
                got = msg.split(":")[0].strip()
            except Db2Error as exc:  # a crash is a finding too: the procedure must always answer cleanly
                msg, got = str(exc), "ERROR"
            if got.startswith(("AUTO-APPLIED", "AUTONOMY BLOCKED")):
                # Earned autonomy is switched on: Db2 accepted the proposal and decided it itself, so it is
                # an accepted proposal that is no longer pending (a repeat of it is not a duplicate).
                got = "PENDING"
                oracle.pending.discard((action_type, payload))
                autonomous += 1
            by_cat[cat] += 1
            outcomes[(expected, got)] += 1
            if expected != got:
                mismatches.append({"category": cat, "type": action_type, "payload": payload,
                                   "expected": expected, "db2": msg[:160]})
            if got == "PENDING" and (action_type, payload) in oracle.pending:
                history.append((action_type, payload))
    finally:
        ibm_db.rollback(agent.conn)
        agent.close()
    total = sum(by_cat.values())
    return {"proposals": total, "agree": total - len(mismatches), "mismatches": mismatches[:20],
            "by_category": dict(by_cat), "rejected": sum(v for (e, g), v in outcomes.items() if g == "REJECTED"),
            "accepted": sum(v for (e, g), v in outcomes.items() if g == "PENDING"),
            "duplicates": sum(v for (e, g), v in outcomes.items() if g == "DUPLICATE"),
            "autonomous": autonomous, "seconds": round(time.time() - t0, 1), "seed": seed}
