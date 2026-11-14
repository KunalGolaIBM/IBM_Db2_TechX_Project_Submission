"""Integration tests against a live Db2 loaded by `python src/setup_db.py`.

Skipped automatically when Db2 is not reachable. No LLM is needed: the tests
drive the same tools and stored procedures the agents use.
"""
import datetime as dt
import json

import pytest

from hotelops.config import SCHEMA
from hotelops.db import OUT_TEXT, Db2Error, get_db

try:
    ADMIN = get_db("admin")
    AGENT = get_db("agent")
    ADMIN.scalar("SELECT COUNT(*) FROM ROOMS")
except Exception as exc:  # pragma: no cover - environment dependent
    pytest.skip(f"Db2 not available: {exc}", allow_module_level=True)

from hotelops import manager  # noqa: E402
from hotelops.audit import RunContext  # noqa: E402
from hotelops.nights import in_band, pick_nights  # noqa: E402
from hotelops.tools import build_tools  # noqa: E402

_USED: dict[str, set[int]] = {}  # nights already taken by a test in this run, per room type


def _nights(code, start, factors=(1.0,), **kw):
    """A night (or window) whose seeded rate leaves room for this test's change, on any run date."""
    used = _USED.setdefault(code, set())
    n = pick_nights(ADMIN, code, start, factors, avoid=used, **kw)
    used.update(range(n.offset, n.offset + len(n.dates)))
    return n


@pytest.fixture()
def tools():
    return build_tools(RunContext(question="pytest", persist=False))


def _propose(type_, payload, rationale="pytest"):
    out = AGENT.call(f"{SCHEMA}.SP_PROPOSE_ACTION", "pytest", type_, json.dumps(payload), rationale, 0, OUT_TEXT)
    return out[4], out[5]


def test_vector_column_and_data_loaded():
    assert ADMIN.scalar("SELECT COUNT(*) FROM GUEST_REVIEWS WHERE EMBEDDING IS NOT NULL") > 200
    typ = ADMIN.scalar("SELECT TYPENAME FROM SYSCAT.COLUMNS WHERE TABSCHEMA = ? AND TABNAME = 'GUEST_REVIEWS' "
                       "AND COLNAME = 'EMBEDDING'", (SCHEMA,))
    assert typ.strip() == "VECTOR"


def test_semantic_search_finds_paraphrased_ac_complaints(tools):
    # none of the stored AC reviews contain the word "loud fan"; semantic match is required
    rows = json.loads(tools["search_reviews"].invoke({"query": "loud fan noise kept me awake", "days": 30,
                                                      "max_rating": 3, "k": 8}))
    rooms = [r["ROOM_NO"] for r in rows]
    assert sum(1 for r in rooms if r.startswith("3")) >= 4


def test_hotspots_point_to_rooms_307_and_312(tools):
    out = json.loads(tools["review_hotspots"].invoke({"query": "noisy air conditioning", "days": 30}))
    top_rooms = [r["ROOM_NO"] for r in out["rows"] if r["ROOM_NO"]][:3]
    assert {"307", "312"} & set(top_rooms)


def test_agent_identity_is_read_only():
    with pytest.raises(Db2Error):
        AGENT.execute("UPDATE RATE_PLAN SET RATE = 1 WHERE 1 = 0")
    with pytest.raises(Db2Error):
        AGENT.execute("DELETE FROM GUESTS WHERE 1 = 0")
    with pytest.raises(Db2Error):
        AGENT.call(f"{SCHEMA}.SP_APPLY_ACTION", 1, "agent", " " * 12, OUT_TEXT)


def test_pii_is_masked_for_agent_but_not_admin():
    agent_email = AGENT.scalar("SELECT EMAIL FROM GUESTS WHERE GUEST_ID = 901")
    admin_email = ADMIN.scalar("SELECT EMAIL FROM GUESTS WHERE GUEST_ID = 901")
    assert agent_email.startswith("***@") and admin_email.startswith("ananya")


def test_row_permission_hides_opted_out_guests_from_agent():
    opted_out = ADMIN.scalar("SELECT COUNT(*) FROM GUESTS WHERE AI_CONSENT = 'N'")
    assert opted_out > 0
    assert AGENT.scalar("SELECT COUNT(*) FROM GUESTS") == ADMIN.scalar("SELECT COUNT(*) FROM GUESTS") - opted_out
    assert AGENT.scalar("SELECT COUNT(*) FROM GUESTS WHERE AI_CONSENT = 'N'") == 0


def test_property_isolation_keeps_the_agent_inside_its_own_hotel():
    from hotelops.chain import isolation_check

    r = isolation_check()
    # a second hotel exists for the manager, not for the agent: tables, history and the KPI view
    assert r["agent_properties"] == r["base_agent_properties"] == 1
    assert r["admin_properties"] == r["base_properties"] + 1
    assert (r["admin_other_rows"], r["agent_other_rows"]) == (1, 0)
    assert r["admin_kpi_rows_today"] == r["base_properties"] + 1 and r["agent_kpi_rows_today"] == 1
    assert r["agent_kpi_rows_other_hotel"] == 0
    # room type codes are per hotel: the agent's STD is its own hotel's, and its proposal is filed there
    assert (r["admin_std_types"], r["agent_std_types"]) == (2, 1)
    assert r["std_proposal"] == "PENDING" and r["std_proposal_property"] == 1
    # Db2 rejects proposals for the other hotel's room and booking
    assert r["ticket_other_room"] == "REJECTED: unknown room_no"
    assert r["upgrade_other_booking"].startswith("REJECTED: reservation not found")
    # only a manager's AGENT_SCOPE row changes what the agent sees; the agent cannot change it
    assert r["agent_properties_after_grant"] == 2 and r["agent_sees_other_room_after_grant"] == 1
    assert r["agent_sees_other_room_after_revoke"] == 0 and not r["agent_can_widen_scope"]
    assert r["left_behind"] == 0
    assert ADMIN.scalar("SELECT COUNT(*) FROM PROPERTIES") == r["base_properties"]


def test_db2_workload_management_stops_runaway_and_bulk_queries_from_the_agent_only():
    from hotelops.wlm import workload_check

    r = workload_check()
    assert r["thresholds"] == {"HOTELOPS_AGENT_MAX_COST": 25000.0, "HOTELOPS_AGENT_MAX_ROWS": 1000.0,
                               "HOTELOPS_AGENT_MAX_TIME": 30.0}
    assert r["normal"][0]
    assert r["runaway"] == (False, "SQL4712N HOTELOPS_AGENT_MAX_COST")
    assert r["bulk"] == (False, "SQL4712N HOTELOPS_AGENT_MAX_ROWS")
    assert r["manager_bulk"] == (True, "1500 row(s)")
    assert r["violations_logged"] >= 2  # Db2's own event monitor recorded both stops


def test_lbac_hides_restricted_guest_notes_from_the_agent():
    from hotelops.lbac import lbac_check

    r = lbac_check()
    assert set(r["manager"]) == {"PUBLIC", "INTERNAL", "RESTRICTED"}
    assert set(r["agent"]) == {"PUBLIC", "INTERNAL"}  # Db2 drops RESTRICTED rows for the agent's read label
    assert len(r["vip_agent"]) == 2 and any("allergy" in n for n in r["vip_manager"])
    assert not any("allergy" in n for n in r["vip_agent"])
    assert r["agent_opted_out_notes"] == 0 < r["manager_opted_out_notes"]  # RCAC consent rule on top of LBAC
    assert not r["agent_can_write"]


def test_demo_group_has_a_second_hotel_the_agent_cannot_see():
    assert ADMIN.scalar("SELECT COUNT(*) FROM PROPERTIES") == 2
    kochi = ADMIN.scalar("SELECT COUNT(*) FROM RESERVATIONS WHERE PROPERTY_ID = 2")
    assert kochi > 100
    assert AGENT.scalar("SELECT COUNT(*) FROM RESERVATIONS WHERE PROPERTY_ID = 2") == 0
    assert AGENT.scalar("SELECT COUNT(*) FROM ROOMS WHERE ROOM_NO LIKE 'K%'") == 0
    occ = ADMIN.scalar("SELECT OCCUPANCY_PCT FROM V_DAILY_KPIS WHERE PROPERTY_ID = 2 AND STAY_DATE = CURRENT DATE")
    assert 40 <= float(occ) <= 90  # about two thirds booked


def test_upgrade_for_opted_out_guest_is_rejected():
    rows = ADMIN.query("SELECT X.RESERVATION_ID FROM RESERVATIONS X JOIN GUESTS G ON G.GUEST_ID = X.GUEST_ID "
                       "WHERE G.AI_CONSENT = 'N' AND X.STATUS IN ('CONFIRMED', 'CHECKED_IN') AND X.PROPERTY_ID = 1 "
                       "FETCH FIRST 1 ROW ONLY")
    if not rows:
        pytest.skip("no active reservation for an opted-out guest")
    action_id, msg = _propose("ROOM_UPGRADE", {"reservation_id": rows[0]["RESERVATION_ID"],
                                               "to_room_type_code": "STE"})
    assert not action_id and "consent" in msg


def test_run_sql_tool_blocks_writes(tools):
    out = tools["run_sql"].invoke({"query": "DELETE FROM GUESTS"})
    assert out.startswith("ERROR")


def test_proposal_validation_rejects_out_of_band_rate():
    d = (dt.date.today() + dt.timedelta(days=20)).isoformat()
    action_id, msg = _propose("RATE_CHANGE", {"room_type_code": "STE", "start_date": d, "end_date": d,
                                              "new_rate": 99999})
    assert not action_id and msg.startswith("REJECTED")


def test_apply_and_time_travel_rollback_roundtrip():
    # two nights; the new rate (10% under the first night) must be in band and within 30% of both nights
    d1, d2 = _nights("PRM", 30, span=2, ok=lambda w, lo, hi: in_band(w[0], (0.9,), lo, hi)
                     and all(abs(w[0] * 0.9 - r) / r <= 0.3 for r in w)).dates
    before = ADMIN.query("SELECT STAY_DATE, RATE FROM RATE_PLAN WHERE ROOM_TYPE_ID = 3 "
                         "AND STAY_DATE BETWEEN ? AND ? ORDER BY STAY_DATE", (d1, d2))
    new_rate = round(before[0]["RATE"] * 0.9, -1)
    action_id, msg = _propose("RATE_CHANGE", {"room_type_code": "PRM", "start_date": d1, "end_date": d2,
                                              "new_rate": new_rate})
    assert action_id, msg

    state, msg = manager.approve(action_id, "pytest.manager")
    assert state == "APPLIED", msg
    after = ADMIN.query("SELECT RATE FROM RATE_PLAN WHERE ROOM_TYPE_ID = 3 AND STAY_DATE BETWEEN ? AND ?",
                        (d1, d2))
    assert all(r["RATE"] == new_rate for r in after)

    state, msg = manager.rollback(action_id, "pytest.manager")
    assert state == "ROLLED_BACK", msg
    restored = ADMIN.query("SELECT STAY_DATE, RATE FROM RATE_PLAN WHERE ROOM_TYPE_ID = 3 "
                           "AND STAY_DATE BETWEEN ? AND ? ORDER BY STAY_DATE", (d1, d2))
    assert [r["RATE"] for r in restored] == [r["RATE"] for r in before]
    versions = ADMIN.scalar("SELECT COUNT(*) FROM RATE_PLAN_HISTORY WHERE ROOM_TYPE_ID = 3 AND STAY_DATE = ?",
                            (d1,))
    assert versions >= 2


def test_guardrail_blocks_excessive_change_at_apply_time():
    # a 40% swing that is still inside the price band: a cut in high season, a rise in low season
    n = _nights("STD", 40, ok=lambda w, lo, hi: in_band(w[0], (0.6,), lo, hi) or in_band(w[0], (1.4,), lo, hi))
    d, cur = n.night, n.rate
    target = round(cur * 0.6, -1) if in_band(cur, (0.6,), n.floor, n.ceiling) else round(cur * 1.4, -1)
    assert abs(target - cur) / cur > 0.35
    action_id, msg = _propose("RATE_CHANGE", {"room_type_code": "STD", "start_date": d, "end_date": d,
                                              "new_rate": target})
    assert action_id, msg
    state, msg = manager.approve(action_id, "pytest.manager")
    assert state == "FAILED" and "35%" in msg


def test_change_feed_reconstructs_before_and_after_from_history(tools):
    from hotelops.changefeed import change_feed

    json.loads(tools["what_changed"].invoke({"hours": 720}))  # the tool output is always valid JSON
    # make a known change, then the feed (newest first) must show it with before/after and who
    n = _nights("DLX", 33, (1.05,))
    day, cur = n.night, n.rate
    manager.set_autonomy("RATE_CHANGE", False, "pytest", "pytest start")
    aid, _ = _propose("RATE_CHANGE", {"room_type_code": "DLX", "start_date": day, "end_date": day,
                                      "new_rate": round(cur * 1.05)})
    try:
        assert manager.approve(aid, "pytest.feed")[0] == "APPLIED"
        r = change_feed(AGENT, 1)["rate_changes"][0]
        assert r["UPDATED_BY"] == "pytest.feed" and r["SOURCE_ACTION_ID"] == aid
        assert float(r["AVG_RATE_BEFORE"]) == round(cur) and float(r["AVG_RATE_AFTER"]) == round(cur * 1.05)
    finally:
        manager.rollback(aid, "pytest")


def test_dry_run_shows_oversell_and_persists_nothing():
    from hotelops.preview import preview_action

    action_id, _ = _propose("MAINTENANCE", {"room_no": "307", "category": "HVAC", "priority": "HIGH",
                                            "description": "pytest dry run", "take_out_of_order": True})
    assert action_id
    state = lambda: (ADMIN.scalar("SELECT COUNT(*) FROM MAINTENANCE_TICKETS"),  # noqa: E731
                     ADMIN.scalar("SELECT STATUS FROM ROOMS WHERE ROOM_NO = '307'"),
                     ADMIN.scalar("SELECT STATUS FROM AGENT_ACTIONS WHERE ACTION_ID = ?", (action_id,)))
    before = state()
    pv = preview_action(action_id)
    assert pv["status"] == "APPLIED" and "OUT_OF_ORDER" in pv["summary"]
    assert pv["rows"] and all(r["SELLABLE_AFTER"] == r["SELLABLE_BEFORE"] - 1 for r in pv["rows"])
    full_nights = [r for r in pv["rows"] if r["SOLD"] >= r["SELLABLE_BEFORE"]]
    if full_nights:  # sold-out DLX nights (the planted conference) must be flagged
        assert any("OVERSOLD" in w for w in pv["warnings"])
    assert state() == before == (before[0], "IN_SERVICE", "PENDING")
    manager.reject(action_id, "pytest")


def _fingerprint():
    return (ADMIN.scalar("SELECT COUNT(*) FROM AGENT_ACTIONS"),
            ADMIN.scalar("SELECT COUNT(*) FROM MAINTENANCE_TICKETS"),
            float(ADMIN.scalar("SELECT SUM(RATE) FROM RATE_PLAN")),
            ADMIN.scalar("SELECT COUNT(*) FROM RATE_PLAN_HISTORY"),
            ADMIN.scalar("SELECT SUM(ROOM_TYPE_ID) FROM RESERVATIONS"),
            ADMIN.scalar("SELECT COUNT(*) FROM GUESTS"))


def test_redteam_scoreboard_blocks_everything_and_changes_nothing():
    from hotelops.redteam import run_redteam

    before = _fingerprint()
    res = run_redteam()
    not_blocked = [a["attack"] for a in res["attacks"] if not a["blocked"]]
    assert res["total"] >= 20 and not not_blocked, not_blocked
    assert {"Db2 privileges (role HOTELOPS_AGENT)", "Db2 RCAC column mask", "Db2 RCAC row permission",
            "Db2 SQL PL guardrail (SP_PROPOSE_ACTION)", "Db2 SQL PL guardrail (SP_APPLY_ACTION)",
            "Db2 EXPLAIN cost guard"} <= set(res["by_layer"])
    assert _fingerprint() == before


def test_cost_guard_refuses_runaway_queries_but_allows_normal_ones(tools):
    ok = json.loads(tools["run_sql"].invoke({"query": "SELECT STAY_DATE, OCCUPANCY_PCT FROM V_DAILY_KPIS "
                                                      "WHERE STAY_DATE = CURRENT DATE"}))
    assert ok["est_cost_timerons"] < 25000
    bad = tools["run_sql"].invoke({"query": "SELECT COUNT(*) FROM RESERVATIONS A, RESERVATIONS B, GUEST_REVIEWS C"})
    assert bad.startswith("ERROR") and "timerons" in bad


def test_earned_autonomy_applies_only_within_granted_limits_and_stays_reversible():
    far = _nights("STD", 20, ok=lambda w, lo, hi: in_band(w[0], (1.02, 1.03), lo, hi)
                  and (in_band(w[0], (1.12,), lo, hi) or in_band(w[0], (0.88,), lo, hi))).night
    near = _nights("STD", 2, (1.02,), stop=6).night  # inside the 7-day lead time that always needs a human
    rate = lambda d: float(ADMIN.scalar("SELECT RATE FROM RATE_PLAN WHERE ROOM_TYPE_ID = 1 AND STAY_DATE = ?", (d,)))  # noqa: E731
    floor, ceil = ADMIN.query("SELECT FLOOR_RATE, CEILING_RATE FROM ROOM_TYPES WHERE ROOM_TYPE_ID = 1")[0].values()
    cur = rate(far)
    created = []
    manager.set_autonomy("RATE_CHANGE", False, "pytest", "pytest start")  # independent of any demo state
    manager.set_autonomy("MAINTENANCE", False, "pytest", "pytest start")
    try:
        # without a grant, even a tiny nudge waits for a human
        aid, msg = _propose("RATE_CHANGE", {"room_type_code": "STD", "start_date": far, "end_date": far,
                                            "new_rate": round(cur * 1.02)})
        created.append(aid)
        assert msg.startswith("PENDING") and rate(far) == cur
        manager.reject(aid, "pytest")

        manager.set_autonomy("RATE_CHANGE", True, "pytest", "pytest", max_change_pct=5, min_lead_days=7, daily_limit=20)
        manager.set_autonomy("MAINTENANCE", True, "pytest", "pytest", max_priority="MEDIUM", daily_limit=20)

        # within limits: applied by Db2 without a human, and reversible
        small = round(cur * 1.03)
        aid, msg = _propose("RATE_CHANGE", {"room_type_code": "STD", "start_date": far, "end_date": far,
                                            "new_rate": small})
        created.append(aid)
        assert msg.startswith("AUTO-APPLIED") and rate(far) == small
        assert ADMIN.scalar("SELECT DECIDED_BY FROM AGENT_ACTIONS WHERE ACTION_ID = ?", (aid,)) == "autonomy"
        assert manager.rollback(aid, "pytest")[0] == "ROLLED_BACK" and rate(far) == cur

        # too big a change, or too close to arrival: a human decides
        big = round(cur * 1.12) if cur * 1.12 <= float(ceil) else round(cur * 0.88)
        assert float(floor) <= big <= float(ceil)
        aid, msg = _propose("RATE_CHANGE", {"room_type_code": "STD", "start_date": far, "end_date": far,
                                            "new_rate": big})
        created.append(aid)
        assert msg.startswith("PENDING") and "not autonomous" in msg and rate(far) == cur
        aid, msg = _propose("RATE_CHANGE", {"room_type_code": "STD", "start_date": near, "end_date": near,
                                            "new_rate": round(rate(near) * 1.02)})
        created.append(aid)
        assert msg.startswith("PENDING") and "days need a human" in msg

        # routine ticket that keeps the room in service: autonomous; blocking a room never is
        aid, msg = _propose("MAINTENANCE", {"room_no": "204", "category": "GENERAL", "priority": "LOW",
                                            "description": "pytest autonomy", "take_out_of_order": False})
        created.append(aid)
        assert msg.startswith("AUTO-APPLIED")
        assert manager.rollback(aid, "pytest")[0] == "ROLLED_BACK"
        aid, msg = _propose("MAINTENANCE", {"room_no": "204", "category": "GENERAL", "priority": "LOW",
                                            "description": "pytest autonomy ooo", "take_out_of_order": True})
        created.append(aid)
        assert msg.startswith("PENDING") and "out of order" in msg
        assert ADMIN.scalar("SELECT STATUS FROM ROOMS WHERE ROOM_NO = '204'") == "IN_SERVICE"
    finally:
        manager.set_autonomy("RATE_CHANGE", False, "pytest", "pytest cleanup")
        manager.set_autonomy("MAINTENANCE", False, "pytest", "pytest cleanup")
        for aid in created:
            if aid:
                manager.reject(aid, "pytest")


def test_agent_cannot_grant_itself_autonomy():
    with pytest.raises(Db2Error):
        AGENT.execute("UPDATE AUTONOMY_POLICY SET ENABLED = 'Y'")


def test_audit_trail_hash_chain_detects_tampering():
    import ibm_db

    from hotelops.audit import verify_audit_chain
    from hotelops.config import load_settings
    from hotelops.db import Db2

    clean = verify_audit_chain()
    assert clean["STEPS"] > 0 and clean["INTACT"], clean
    s = load_settings().db2
    db = Db2(s.conn_str(s.admin_user, s.admin_password), "tamper")
    ibm_db.autocommit(db.conn, ibm_db.SQL_AUTOCOMMIT_OFF)
    try:
        target = db.scalar("SELECT MIN(STEP_ID) + 3 FROM AGENT_STEPS")
        db.execute("UPDATE AGENT_STEPS SET TOOL_OUTPUT = 'quietly edited' WHERE STEP_ID = ?", (target,))
        tampered = verify_audit_chain(db)
        assert not tampered["INTACT"] and tampered["FIRST_BROKEN_STEP"] == target
    finally:
        ibm_db.rollback(db.conn)
        db.close()
    assert verify_audit_chain()["INTACT"]


def test_simulate_tampering_is_detected_at_the_edited_step_and_rolled_back():
    from hotelops.audit import simulate_tampering, verify_audit_chain

    target = ADMIN.scalar("SELECT MIN(STEP_ID) + 2 FROM AGENT_STEPS")
    res = simulate_tampering(target)
    assert not res["tampered"]["INTACT"] and res["tampered"]["FIRST_BROKEN_STEP"] == target
    assert res["restored"]["INTACT"] and verify_audit_chain()["INTACT"]
    out = ADMIN.scalar("SELECT TOOL_OUTPUT FROM AGENT_STEPS WHERE STEP_ID = ?", (target,))
    assert "quietly edited" not in (out or "")
    default = simulate_tampering()  # the UI button: picks a step in the middle of the trail
    assert default["tampered"]["FIRST_BROKEN_STEP"] == default["step"]["STEP_ID"]
    assert default["restored"]["INTACT"]


def test_dry_run_flags_stale_evidence_when_rates_change_after_the_proposal():
    from hotelops.preview import preview_action
    from hotelops.provenance import provenance

    n = _nights("STD", 25, (1.04, 0.97))
    day, cur = n.night, n.rate
    manager.set_autonomy("RATE_CHANGE", False, "pytest", "pytest start")
    proposal, _ = _propose("RATE_CHANGE", {"room_type_code": "STD", "start_date": day, "end_date": day,
                                           "new_rate": round(cur * 1.04)})
    assert provenance(proposal)["freshness"]["fresh"]
    competing, _ = _propose("RATE_CHANGE", {"room_type_code": "STD", "start_date": day, "end_date": day,
                                            "new_rate": round(cur * 0.97)}, rationale="someone else repriced")
    try:
        assert manager.approve(competing, "pytest.rm")[0] == "APPLIED"
        pv = preview_action(proposal)
        assert any(w.startswith("Stale evidence") for w in pv["warnings"])
        assert pv["stale_changes"][0]["CHANGED_BY"] == "pytest.rm"
    finally:
        manager.rollback(competing, "pytest")
        manager.reject(proposal, "pytest")


def test_daily_autonomy_budget_stops_autonomous_actions():
    n = _nights("STD", 30, (1.02,))
    day, cur = n.night, n.rate
    manager.set_autonomy("RATE_CHANGE", True, "pytest", "pytest", max_change_pct=5, min_lead_days=7, daily_limit=0)
    aid = None
    try:
        aid, msg = _propose("RATE_CHANGE", {"room_type_code": "STD", "start_date": day, "end_date": day,
                                            "new_rate": round(cur * 1.02)})
        assert msg.startswith("PENDING") and "daily autonomy budget" in msg
    finally:
        manager.set_autonomy("RATE_CHANGE", False, "pytest", "pytest cleanup", daily_limit=5)
        if aid:
            manager.reject(aid, "pytest")


def test_verify_script_passes_every_check_and_leaves_no_trace():
    import verify

    pending = ADMIN.scalar("SELECT COUNT(*) FROM AGENT_ACTIONS WHERE STATUS = 'PENDING'")
    assert verify.main() == 0
    assert ADMIN.scalar("SELECT COUNT(*) FROM AGENT_ACTIONS WHERE STATUS = 'PENDING'") == pending


def test_promotions_are_bitemporal_and_the_agent_tool_shows_both_versions():
    sat = ADMIN.scalar("SELECT MIN(VALID_FROM) FROM PROMOTIONS WHERE PROMO_ID = 1 AND DISCOUNT_PCT = 18")
    tools = build_tools(RunContext(question="pytest", persist=False))
    out = json.loads(tools["promotion_on"].invoke({"room_type_code": "JST", "stay_date": str(sat)}))
    assert [float(r["DISCOUNT_PCT"]) for r in out["in_force"]] == [18.0]
    assert sorted(float(r["DISCOUNT_PCT"]) for r in out["all_recorded_versions"]) == [10.0, 18.0]
    first = min(r["RECORDED_AT"] for r in out["all_recorded_versions"])
    then = json.loads(tools["promotion_on"].invoke({"room_type_code": "JST", "stay_date": str(sat),
                                                    "as_known_at": str(first)}))
    assert [float(r["DISCOUNT_PCT"]) for r in then["in_force"]] == [10.0]
    # the Friday of the same offer was never corrected
    fri = ADMIN.scalar("SELECT MIN(VALID_FROM) FROM PROMOTIONS WHERE PROMO_ID = 1")
    assert float(AGENT.scalar("SELECT DISCOUNT_PCT FROM PROMOTIONS FOR BUSINESS_TIME AS OF CAST(? AS DATE) "
                              "WHERE PROMO_ID = 1", (str(fri),))) == 10.0


def test_promotions_reject_overlapping_periods_and_oversized_discounts():
    with pytest.raises(Db2Error):
        ADMIN.execute("INSERT INTO PROMOTIONS (PROMO_ID, ROOM_TYPE_ID, NAME, DISCOUNT_PCT, VALID_FROM, VALID_TO) "
                      "SELECT 1, 5, 'overlap', 5, VALID_FROM, VALID_TO FROM PROMOTIONS "
                      "WHERE PROMO_ID = 1 FETCH FIRST 1 ROW ONLY")
    with pytest.raises(Db2Error):
        ADMIN.execute("INSERT INTO PROMOTIONS (PROMO_ID, ROOM_TYPE_ID, NAME, DISCOUNT_PCT, VALID_FROM, VALID_TO) "
                      "VALUES (99, 1, 'too generous', 60, CURRENT DATE, CURRENT DATE + 3 DAYS)")
    with pytest.raises(Db2Error):
        AGENT.execute("UPDATE PROMOTIONS SET DISCOUNT_PCT = 40 WHERE 1 = 0")


def test_mqt_is_a_materialized_copy_of_the_kpi_view():
    kind = ADMIN.scalar("SELECT TYPE FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = 'MQT_DAILY_KPIS'",
                        (SCHEMA,))
    assert kind.strip() == "S"
    diff = ADMIN.scalar(
        "SELECT COUNT(*) FROM MQT_DAILY_KPIS M JOIN V_DAILY_KPIS V "
        "ON V.STAY_DATE = M.STAY_DATE AND V.PROPERTY_ID = M.PROPERTY_ID "
        "WHERE M.STAY_DATE < CURRENT DATE AND (M.OCCUPANCY_PCT <> V.OCCUPANCY_PCT OR M.ROOMS_SOLD <> V.ROOMS_SOLD)")
    assert diff == 0
    assert AGENT.scalar("SELECT COUNT(*) FROM MQT_DAILY_KPIS") > 0


def test_external_anchor_matches_and_catches_a_rebuilt_ledger(tmp_path, monkeypatch):
    from hotelops import audit

    monkeypatch.setattr(audit, "ANCHOR_FILE", tmp_path / "anchors.jsonl")
    assert audit.check_anchor(ADMIN)["ok"] is None  # nothing anchored yet in this temp file
    anchor = audit.write_anchor(ADMIN, note="pytest")
    assert audit.latest_anchor() == anchor and audit.check_anchor(ADMIN)["ok"] is True
    res = audit.simulate_rebuilt_ledger()
    assert res["chain_after_rebuild"]["INTACT"]          # the in-database chain was rebuilt consistently
    assert res["anchor_after_rebuild"]["ok"] is False    # ... but the external anchor no longer matches
    assert res["anchor_after_rollback"]["ok"] is True
    assert audit.verify_audit_chain(ADMIN)["INTACT"]



def test_guardrail_fuzz_agrees_with_the_oracle():
    from hotelops.fuzz import run_fuzz

    r = run_fuzz(600, seed=3)
    assert r["agree"] == r["proposals"], r["mismatches"][:3]
    assert r["rejected"] and r["accepted"] and r["duplicates"]  # every outcome is exercised


def test_guardrail_rejects_over_long_fields_cleanly():
    """Found by the fuzzer: over-long fields crashed SP_PROPOSE_ACTION (SQL0137N) instead of a clean REJECTED."""
    for type_, payload in [("ROOM_UPGRADE", {"reservation_id": 1, "to_room_type_code": "PENTHOUSE_SUITE"}),
                           ("RATE_CHANGE", {"room_type_code": "STANDARD_ROOM", "start_date": "2099-01-01",
                                            "end_date": "2099-01-01", "new_rate": 5000}),
                           ("MAINTENANCE", {"room_no": "1234567890", "priority": "VERY_URGENT_NOW"})]:
        action_id, msg = _propose(type_, payload)
        assert not action_id and msg.startswith("REJECTED"), msg


def test_policy_search_leaves_no_lock_behind():
    """langchain-db2 (ibm_db_dbi) kept its read lock open, which once blocked a schema reset for 10 minutes."""
    import ibm_db

    from hotelops.config import load_settings
    from hotelops.db import Db2
    from hotelops.knowledge import search_policies

    assert search_policies("room out of order", 2)
    s = load_settings().db2
    db = Db2(s.conn_str(s.admin_user, s.admin_password), "lock-probe")
    db.execute("SET CURRENT LOCK TIMEOUT 3")
    ibm_db.autocommit(db.conn, ibm_db.SQL_AUTOCOMMIT_OFF)
    try:
        db.execute("LOCK TABLE POLICY_KB IN EXCLUSIVE MODE")  # fails with SQL0911N if a lock was left behind
    finally:
        ibm_db.rollback(db.conn)
        db.close()


def test_guardrail_fuzz_still_agrees_when_earned_autonomy_is_on():
    """Found in a rehearsal: with autonomy granted, Db2 auto-applies small changes; the oracle must accept that."""
    from hotelops.fuzz import run_fuzz

    manager.set_autonomy("RATE_CHANGE", True, "pytest", "fuzz with autonomy", max_change_pct=5, min_lead_days=7,
                         daily_limit=50)
    try:
        r = run_fuzz(400, seed=13)
    finally:
        manager.set_autonomy("RATE_CHANGE", False, "pytest", "fuzz done")
    assert r["agree"] == r["proposals"], r["mismatches"][:3]
    assert r["autonomous"] > 0


# --- concurrency: real conflicts between managers -----------------------------------------------

def _fresh_admin():
    from hotelops.config import load_settings
    from hotelops.db import Db2

    s = load_settings().db2
    return Db2(s.conn_str(s.admin_user, s.admin_password), "pytest-concurrency")


def _race(proc, action_id, n):
    """Call ``proc`` for the same action from ``n`` separate Db2 connections released at the same instant."""
    import threading

    barrier, results, errors = threading.Barrier(n), [], []

    def worker(i):
        conn = _fresh_admin()
        try:
            barrier.wait()
            out = conn.call(f"{SCHEMA}.{proc}", int(action_id), f"manager-{i}", " " * 12, OUT_TEXT)
            results.append(str(out[3]))
        except Exception as exc:  # noqa: BLE001 - reported by the assertion below
            errors.append(str(exc))
        finally:
            conn.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    return results


def _std_rate_action(days_ahead):
    n = _nights("STD", days_ahead, (0.97, 0.97 * 0.98))  # a 3% cut, and room for a later 2% cut on top
    night, rate = dt.date.fromisoformat(n.night), n.rate
    action_id, msg = _propose("RATE_CHANGE", {"room_type_code": "STD", "start_date": night.isoformat(),
                                              "end_date": night.isoformat(), "new_rate": round(rate * 0.97, 2)})
    assert action_id, msg
    return action_id, night


def _versions(night):
    return ADMIN.scalar("SELECT COUNT(*) FROM RATE_PLAN_HISTORY WHERE STAY_DATE = ? AND ROOM_TYPE_ID = "
                        "(SELECT ROOM_TYPE_ID FROM ROOM_TYPES WHERE CODE = 'STD')", (night.isoformat(),))


def test_simultaneous_approvals_apply_an_action_exactly_once():
    action_id, night = _std_rate_action(41)
    before = _versions(night)
    msgs = _race("SP_APPLY_ACTION", action_id, 6)
    assert sum(m.startswith("Repriced") for m in msgs) == 1, msgs
    assert sum("not pending" in m for m in msgs) == 5, msgs
    assert _versions(night) == before + 1  # the rate was written once, not six times


def test_simultaneous_rollbacks_restore_exactly_once():
    action_id, night = _std_rate_action(42)
    assert manager.approve(action_id, "pytest")[0].strip() == "APPLIED"
    msgs = _race("SP_ROLLBACK_ACTION", action_id, 4)
    assert sum(m.startswith("Restored") for m in msgs) == 1, msgs
    assert ADMIN.scalar("SELECT STATUS FROM AGENT_ACTIONS WHERE ACTION_ID = ?", (action_id,)).strip() == "ROLLED_BACK"


def test_rollback_refused_after_a_later_change_to_the_same_night():
    first, night = _std_rate_action(43)
    assert manager.approve(first, "pytest")[0].strip() == "APPLIED"
    rate = float(ADMIN.scalar("SELECT RATE FROM RATE_PLAN WHERE ROOM_TYPE_ID = (SELECT ROOM_TYPE_ID FROM ROOM_TYPES "
                              "WHERE CODE = 'STD') AND STAY_DATE = ?", (night.isoformat(),)))
    second, msg = _propose("RATE_CHANGE", {"room_type_code": "STD", "start_date": night.isoformat(),
                                           "end_date": night.isoformat(), "new_rate": round(rate * 0.98, 2)})
    assert second, msg
    assert manager.approve(second, "pytest")[0].strip() == "APPLIED"
    status, message = manager.rollback(first, "pytest")
    assert status.strip() == "APPLIED" and "changed again" in message  # Db2 refuses to clobber the newer change
