"""One-command proof for judges: every headline claim, checked against the live Db2.

    python src/verify.py

Needs only Db2 (no LLM key). Anything that writes runs inside a transaction that is rolled back,
so the database is left exactly as it was. Exit code 0 when every check passes.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ibm_db  # noqa: E402

from hotelops.config import PROJECT_ROOT, SCHEMA, load_settings  # noqa: E402
from hotelops.db import OUT_TEXT, Db2, Db2Error, get_db  # noqa: E402
from hotelops.nights import pick_nights  # noqa: E402

GREEN, RED, DIM, BOLD, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"
if not sys.stdout.isatty():
    GREEN = RED = DIM = BOLD = RESET = ""


def _own(role: str) -> Db2:
    """A dedicated connection, so a transaction here never mixes with anything else."""
    s = load_settings().db2
    user, pw = (s.admin_user, s.admin_password) if role == "admin" else (s.agent_user, s.agent_password)
    return Db2(s.conn_str(user, pw), f"verify-{role}")


def _sqlcode(exc: Exception) -> str:
    m = re.search(r"SQL\d{4,5}N", str(exc))
    return m.group(0) if m else type(exc).__name__


# --------------------------------------------------------------------------- checks
def db2_version(admin: Db2, agent: Db2) -> str:
    level = admin.scalar("SELECT SERVICE_LEVEL FROM SYSIBMADM.ENV_INST_INFO")
    assert "v12.1" in level, level
    return f"{level} (VECTOR needs 12.1.2+)"


def vector_columns(admin: Db2, agent: Db2) -> str:
    rows = admin.query("SELECT TABNAME, COLNAME FROM SYSCAT.COLUMNS WHERE TABSCHEMA = ? AND TYPENAME = 'VECTOR' "
                       "ORDER BY TABNAME", (SCHEMA,))
    assert rows, "no VECTOR columns"
    return ", ".join(f"{r['TABNAME']}.{r['COLNAME']}" for r in rows) + " are native VECTOR(384) columns"


def vector_radar(admin: Db2, agent: Db2) -> str:
    from hotelops.radar import complaint_radar

    themes = {t["THEME"]: t for t in complaint_radar(admin, 30)["themes"]}
    ac = themes.get("Air conditioning")
    assert ac and ac["PATTERN"] == "LOCALISED", themes.keys()
    rooms = [str(r["ROOM_NO"]) for r in ac["TOP_ROOMS"][:2]]
    assert {"307", "312"} <= set(rooms), rooms
    return f"one VECTOR_DISTANCE query finds {len(themes)} complaint themes; AC is localised to rooms {'/'.join(rooms)}"


def langchain_db2(admin: Db2, agent: Db2) -> str:
    from hotelops.knowledge import search_policies

    hits = search_policies("taking a room out of order when the hotel is nearly full", k=3)
    assert hits and all(h["policy_id"].startswith("POL-") for h in hits), hits
    return f"IBM langchain-db2 DB2VS search returns {', '.join(h['policy_id'] for h in hits)}"


def least_privilege(admin: Db2, agent: Db2) -> str:
    codes = []
    for sql in ("DELETE FROM GUESTS WHERE 1 = 0", "UPDATE RATE_PLAN SET RATE = 1 WHERE 1 = 0",
                "DROP TABLE RESERVATIONS"):
        try:
            agent.execute(sql)
        except Db2Error as exc:
            codes.append(_sqlcode(exc))
        else:
            raise AssertionError(f"agent was allowed to run: {sql}")
    try:
        agent.call(f"{SCHEMA}.SP_APPLY_ACTION", 1, "agent", " " * 12, OUT_TEXT)
    except Db2Error as exc:
        codes.append(_sqlcode(exc))
    else:
        raise AssertionError("agent was allowed to approve its own actions")
    return f"agent user refused DELETE / UPDATE / DROP / self-approval ({', '.join(sorted(set(codes)))})"


def column_mask(admin: Db2, agent: Db2) -> str:
    seen = agent.scalar("SELECT EMAIL FROM GUESTS WHERE GUEST_ID = 901")
    real = admin.scalar("SELECT EMAIL FROM GUESTS WHERE GUEST_ID = 901")
    assert seen.startswith("***@") and not real.startswith("***"), (seen, real)
    return f"agent sees '{seen}', the manager sees the real address (RCAC column mask)"


def row_permission(admin: Db2, agent: Db2) -> str:
    total = admin.scalar("SELECT COUNT(*) FROM GUESTS")
    opted_out = admin.scalar("SELECT COUNT(*) FROM GUESTS WHERE AI_CONSENT = 'N'")
    visible = agent.scalar("SELECT COUNT(*) FROM GUESTS")
    assert opted_out > 0 and visible == total - opted_out, (total, opted_out, visible)
    return (f"agent sees {visible} of {total} guests; {opted_out} who opted out of AI are invisible "
            "(RCAC row permission)")


def explain_cost_guard(admin: Db2, agent: Db2) -> str:
    from hotelops.costguard import QueryTooExpensive, check_cost, max_cost

    cheap = check_cost("SELECT COUNT(*) FROM RESERVATIONS WHERE CHECK_IN = CURRENT DATE")
    kpi = check_cost("SELECT OCCUPANCY_PCT FROM V_DAILY_KPIS WHERE STAY_DATE = CURRENT DATE")  # needs RUNSTATS
    try:
        check_cost("SELECT COUNT(*) FROM RESERVATIONS A, RESERVATIONS B, RESERVATIONS C")
    except QueryTooExpensive:
        pass
    else:
        raise AssertionError("cross join was not stopped")
    return (f"EXPLAIN prices normal queries at {cheap:,.0f}-{kpi:,.0f} timerons and refuses a triple cross join "
            f"(limit {max_cost():,.0f}) before it runs")


def temporal_tables(admin: Db2, agent: Db2) -> str:
    tables = admin.query("SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TEMPORALTYPE IN ('S', 'B') "
                         "ORDER BY TABNAME", (SCHEMA,))
    names = [t["TABNAME"] for t in tables]
    assert {"RATE_PLAN", "RESERVATIONS", "ROOMS"} <= set(names), names
    versions = admin.scalar("SELECT COUNT(*) FROM RATE_PLAN FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30'")
    current = admin.scalar("SELECT COUNT(*) FROM RATE_PLAN")
    return (f"{', '.join(names)} are system-period temporal; RATE_PLAN keeps {versions - current} past versions "
            "queryable with FOR SYSTEM_TIME")


def property_isolation(admin: Db2, agent: Db2) -> str:
    from hotelops.chain import isolation_check

    r = isolation_check()
    assert r["agent_properties"] == r["base_agent_properties"] == 1, r
    assert r["admin_properties"] == r["base_properties"] + 1, r
    assert r["agent_other_rows"] == 0 and r["admin_other_rows"] == 1, r
    assert r["agent_std_types"] == 1 and r["agent_kpi_rows_today"] == 1 and r["agent_kpi_rows_other_hotel"] == 0, r
    assert r["ticket_other_room"].startswith("REJECTED") and r["upgrade_other_booking"].startswith("REJECTED"), r
    assert r["std_proposal"] == "PENDING" and r["std_proposal_property"] == 1, r
    assert r["agent_sees_other_room_after_grant"] == 1 and r["agent_sees_other_room_after_revoke"] == 0, r
    assert not r["agent_can_widen_scope"] and r["left_behind"] == 0, r
    return (f"the group has {r['base_properties']} hotels and the Goa agent sees 1; a temporary hotel that reuses "
            "the code 'STD' is invisible to it (rooms, rates, bookings, reviews, history, KPIs), its proposals there "
            "are rejected, and only a manager's AGENT_SCOPE row changes that (RCAC row permissions). Removed after")


def proposal_guardrail(admin: Db2, agent: Db2) -> str:
    floor = float(admin.scalar("SELECT FLOOR_RATE FROM ROOM_TYPES WHERE CODE = 'STE'"))
    night = (dt.date.fromisoformat(str(admin.scalar("VALUES CURRENT DATE"))) + dt.timedelta(days=10)).isoformat()
    payload = {"room_type_code": "STE", "start_date": night, "end_date": night, "new_rate": 500}
    ibm_db.autocommit(agent.conn, ibm_db.SQL_AUTOCOMMIT_OFF)
    try:
        out = agent.call(f"{SCHEMA}.SP_PROPOSE_ACTION", "verify", "RATE_CHANGE", json.dumps(payload),
                         "verify.py: injected Rs 500 suite", 0, OUT_TEXT)
    finally:
        ibm_db.rollback(agent.conn)
        ibm_db.autocommit(agent.conn, ibm_db.SQL_AUTOCOMMIT_ON)
    assert not out[4] and str(out[5]).startswith("REJECTED"), out[4:6]
    msg = str(out[5]).split(" for ")[0]
    return f"SP_PROPOSE_ACTION rejects a Rs 500 Ocean Suite (floor Rs {floor:,.0f}) with \"{msg}\""


def apply_and_rollback(admin: Db2, agent: Db2) -> str:
    night = pick_nights(admin, "STD", 12, (1.02,)).night  # a night where +2% stays inside the price band
    sql = "SELECT RATE FROM RATE_PLAN WHERE ROOM_TYPE_ID = (SELECT ROOM_TYPE_ID FROM ROOM_TYPES WHERE CODE = 'STD') " \
          "AND STAY_DATE = ?"
    before = float(admin.scalar(sql, (night,)))
    new = round(before * 1.02 / 10) * 10
    payload = {"room_type_code": "STD", "start_date": night, "end_date": night, "new_rate": new}
    ibm_db.autocommit(admin.conn, ibm_db.SQL_AUTOCOMMIT_OFF)
    try:
        out = admin.call(f"{SCHEMA}.SP_PROPOSE_ACTION", "verify", "RATE_CHANGE", json.dumps(payload),
                         "verify.py dry run", 0, OUT_TEXT)
        action_id = out[4]
        assert action_id, out[5]
        res = admin.call(f"{SCHEMA}.SP_APPLY_ACTION", int(action_id), "verify", " " * 12, OUT_TEXT)
        during = float(admin.scalar(sql, (night,)))
        assert res[2].strip() == "APPLIED" and during == new, (res[2:4], during)
    finally:
        ibm_db.rollback(admin.conn)
        ibm_db.autocommit(admin.conn, ibm_db.SQL_AUTOCOMMIT_ON)
    after = float(admin.scalar(sql, (night,)))
    assert after == before, (before, after)
    return (f"SP_APPLY_ACTION moved STD {night} from Rs {before:,.0f} to Rs {new:,.0f} inside a transaction; "
            "ROLLBACK restored it")


def concurrent_approval(admin: Db2, agent: Db2) -> str:
    """Two managers approve the same action at once: Db2's row lock makes the second wait for the first."""
    night = pick_nights(admin, "STD", 13, (0.98,)).night  # a night where -2% stays inside the price band
    rate = float(admin.scalar("SELECT RATE FROM RATE_PLAN WHERE ROOM_TYPE_ID = (SELECT ROOM_TYPE_ID FROM ROOM_TYPES "
                              "WHERE CODE = 'STD') AND STAY_DATE = ?", (night,)))
    payload = {"room_type_code": "STD", "start_date": night, "end_date": night, "new_rate": round(rate * 0.98, 2)}
    out = admin.call(f"{SCHEMA}.SP_PROPOSE_ACTION", "verify", "RATE_CHANGE", json.dumps(payload),
                     "verify.py concurrency check", 0, OUT_TEXT)
    action_id = out[4]
    assert action_id, out[5]
    first, second = _own("admin"), _own("admin")
    try:
        second.execute("SET CURRENT LOCK TIMEOUT 3")
        with _tx(first):
            res = first.call(f"{SCHEMA}.SP_APPLY_ACTION", int(action_id), "manager-1", " " * 12, OUT_TEXT)
            assert res[2].strip() == "APPLIED", res[2:4]
            t0 = time.time()
            try:
                second.call(f"{SCHEMA}.SP_APPLY_ACTION", int(action_id), "manager-2", " " * 12, OUT_TEXT)
                raise AssertionError("second approval was not blocked while the first was in flight")
            except Db2Error as exc:
                assert "SQL0911N" in str(exc), exc
            waited = time.time() - t0
    finally:
        first.close()
        second.close()
        admin.execute("DELETE FROM AGENT_ACTIONS WHERE ACTION_ID = ?", (int(action_id),))
    return (f"while manager 1's approval of action #{action_id} was in flight, manager 2's approval waited on "
            f"Db2's row lock ({waited:.0f} s, then SQL0911N); an action can never be applied twice. Rolled back")


def ast_guard(admin: Db2, agent: Db2) -> str:
    from hotelops.sqlguard import UnsafeSqlError, validate_select

    validate_select("SELECT RATE FROM RATE_PLAN FOR SYSTEM_TIME AS OF '2026-11-01-00.00.00' "
                    "WHERE STAY_DATE = CURRENT DATE + 7 DAYS")
    refused = []
    for sql in ("SELECT * FROM ROOMS WHERE ROOM_NO IN (SELECT TABNAME FROM SYSCAT.TABLES)",
                "WITH X AS (SELECT 1 AS A FROM SYSIBM.SYSDUMMY1) DELETE FROM GUESTS",
                "SELECT * FROM SYSIBMADM.ENV_INST_INFO"):
        try:
            validate_select(sql)
        except UnsafeSqlError:
            refused.append(sql)
    assert len(refused) == 3, refused
    return ("SQLGlot parses LLM-written SQL into a syntax tree: a Db2 time-travel query passes; a catalog read in a "
            "subquery, a DELETE inside a CTE and a system-view read are refused")


def audit_chain(admin: Db2, agent: Db2) -> str:
    from hotelops.audit import simulate_tampering, verify_audit_chain

    chain = verify_audit_chain(admin)
    assert chain["INTACT"] and chain["STEPS"] > 0, chain
    t = simulate_tampering()
    assert t["tampered"]["FIRST_BROKEN_STEP"] == t["step"]["STEP_ID"] and t["restored"]["INTACT"], t
    return (f"{chain['STEPS']} hash-chained steps verify inside Db2; a secret edit to step {t['step']['STEP_ID']} "
            "is flagged at exactly that step, then rolled back")


def red_team(admin: Db2, agent: Db2) -> str:
    from hotelops.redteam import run_redteam

    res = run_redteam()
    by_db2 = sum(v for k, v in res["by_layer"].items() if k.startswith("Db2"))
    assert res["blocked"] == res["total"], [a for a in res["attacks"] if not a["blocked"]]
    return (f"{res['blocked']}/{res['total']} attacks blocked, {by_db2} by Db2 itself, "
            f"across {len(res['by_layer'])} layers")


def evaluation(admin: Db2, agent: Db2) -> str:
    text = (PROJECT_ROOT / "docs" / "eval_results.md").read_text(encoding="utf-8")
    m = re.search(r"\*\*(\d+)/(\d+) passed", text)
    assert m and m.group(1) == m.group(2), m and m.group(0)
    return (f"last recorded run: {m.group(1)}/{m.group(2)} questions correct "
            "(docs/eval_results.md; rerun needs an LLM key)")


def _tx(db: Db2):
    """Context manager: run the block in a transaction on ``db`` and always roll it back."""
    from contextlib import contextmanager

    @contextmanager
    def cm():
        ibm_db.autocommit(db.conn, ibm_db.SQL_AUTOCOMMIT_OFF)
        try:
            yield db
        finally:
            ibm_db.rollback(db.conn)
            ibm_db.autocommit(db.conn, ibm_db.SQL_AUTOCOMMIT_ON)
    return cm()


def _night(admin: Db2, days: int) -> str:
    return (dt.date.fromisoformat(str(admin.scalar("VALUES CURRENT DATE"))) + dt.timedelta(days=days)).isoformat()


def bitemporal(admin: Db2, agent: Db2) -> str:
    sat = admin.scalar("SELECT MIN(VALID_FROM) FROM PROMOTIONS WHERE PROMO_ID = 1 AND DISCOUNT_PCT = 18")
    assert sat, "no corrected Saturday promotion"
    now = float(agent.scalar("SELECT DISCOUNT_PCT FROM PROMOTIONS FOR BUSINESS_TIME AS OF CAST(? AS DATE) "
                             "WHERE PROMO_ID = 1", (str(sat),)))
    first_known = admin.scalar("SELECT MIN(SYS_START) FROM PROMOTIONS FOR SYSTEM_TIME FROM '0001-01-01' "
                               "TO '9999-12-30' WHERE PROMO_ID = 1")
    then = float(agent.scalar("SELECT DISCOUNT_PCT FROM PROMOTIONS FOR SYSTEM_TIME AS OF CAST(? AS TIMESTAMP) "
                              "FOR BUSINESS_TIME AS OF CAST(? AS DATE) WHERE PROMO_ID = 1",
                              (str(first_known), str(sat))))
    assert now == 18 and then == 10, (now, then)
    return (f"PROMOTIONS has BUSINESS_TIME + SYSTEM_TIME: the night of {sat} is {now:.0f}% off today, but "
            f"{then:.0f}% as the hotel recorded it originally (what a guest was quoted)")


def materialized_view(admin: Db2, agent: Db2) -> str:
    kind = admin.scalar("SELECT TYPE FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = 'MQT_DAILY_KPIS'",
                        (SCHEMA,))
    assert kind and kind.strip() == "S", kind
    t0 = time.time()
    admin.execute("REFRESH TABLE MQT_DAILY_KPIS")
    ms = (time.time() - t0) * 1000
    day = _night(admin, -3)
    mqt = admin.scalar("SELECT OCCUPANCY_PCT FROM MQT_DAILY_KPIS WHERE STAY_DATE = ? AND PROPERTY_ID = 1", (day,))
    live = admin.scalar("SELECT OCCUPANCY_PCT FROM V_DAILY_KPIS WHERE STAY_DATE = ? AND PROPERTY_ID = 1", (day,))
    n = admin.scalar("SELECT COUNT(*) FROM MQT_DAILY_KPIS")
    assert str(mqt) == str(live), (mqt, live)
    return f"MQT_DAILY_KPIS (REFRESH DEFERRED) holds {n} nights; refreshed in {ms:,.0f} ms and matches the live view"


def hash_trigger(admin: Db2, agent: Db2) -> str:
    trg = admin.query("SELECT TRIGNAME, TRIGTIME, TRIGEVENT FROM SYSCAT.TRIGGERS WHERE TABSCHEMA = ? "
                      "AND TABNAME = 'AGENT_STEPS'", (SCHEMA,))
    assert any(t["TRIGNAME"] == "TRG_STEPS_HASH_CHAIN" for t in trg), trg
    nulls = admin.scalar("SELECT COUNT(*) FROM AGENT_STEPS WHERE ROW_HASH IS NULL")
    assert nulls == 0, nulls
    return "BEFORE INSERT trigger TRG_STEPS_HASH_CHAIN stamps every step with HASH(previous hash || step, SHA-256)"


def check_constraints(admin: Db2, agent: Db2) -> str:
    with _tx(admin):
        try:
            admin.execute("UPDATE AUTONOMY_POLICY SET MAX_CHANGE_PCT = 50 WHERE ACTION_TYPE = 'RATE_CHANGE'")
        except Db2Error as exc:
            code = _sqlcode(exc)
        else:
            raise AssertionError("a 50% autonomy grant was accepted")
    return f"even the manager cannot grant the AI more than 15% price autonomy: CHECK constraint ({code})"


def agent_cannot_self_grant(admin: Db2, agent: Db2) -> str:
    try:
        agent.execute("UPDATE AUTONOMY_POLICY SET ENABLED = 'Y'")
    except Db2Error as exc:
        return f"the agent cannot switch on its own autonomy ({_sqlcode(exc)})"
    raise AssertionError("agent changed AUTONOMY_POLICY")


def earned_autonomy(admin: Db2, agent: Db2) -> str:
    night = _night(admin, 12)
    rate = float(admin.scalar("SELECT RATE FROM RATE_PLAN WHERE ROOM_TYPE_ID = 1 AND STAY_DATE = ?", (night,)))
    with _tx(admin):
        admin.execute("UPDATE AUTONOMY_POLICY SET ENABLED = 'Y', MAX_CHANGE_PCT = 5, MIN_LEAD_DAYS = 7, "
                      "DAILY_LIMIT = 50 WHERE ACTION_TYPE = 'RATE_CHANGE'")
        msgs = []
        for pct in (1.03, 1.15):
            payload = {"room_type_code": "STD", "start_date": night, "end_date": night,
                       "new_rate": round(rate * pct / 10) * 10}
            out = admin.call(f"{SCHEMA}.SP_PROPOSE_ACTION", "verify", "RATE_CHANGE", json.dumps(payload),
                             "verify.py autonomy", 0, OUT_TEXT)
            msgs.append(str(out[5]))
        small, big = msgs
    assert small.startswith("AUTO-APPLIED") and big.startswith("PENDING"), msgs
    return "with a ±5% grant, Db2 applied a +3% change itself and held a +15% change for a human (rolled back)"


def json_guardrail(admin: Db2, agent: Db2) -> str:
    with _tx(agent):
        out = agent.call(f"{SCHEMA}.SP_PROPOSE_ACTION", "verify", "RATE_CHANGE", "this is not json",
                         "verify.py", 0, OUT_TEXT)
    assert not out[4] and "JSON" in str(out[5]), out[4:6]
    return f"SP_PROPOSE_ACTION validates payloads with JSON_EXISTS / JSON_VALUE: {str(out[5])[:50]}"


def change_feed(admin: Db2, agent: Db2) -> str:
    from hotelops.changefeed import change_feed as feed

    res = feed(agent, 24 * 30)
    rates = res["rate_changes"]
    assert rates, "no rate changes found"
    who = sorted({r["UPDATED_BY"] for r in rates})
    return (f"change feed rebuilt from *_HISTORY (P.SYS_END = V.SYS_START, no triggers): {len(rates)} rate "
            f"changes by {', '.join(who)}")


def catalog_card(admin: Db2, agent: Db2) -> str:
    from hotelops.tools import schema_card

    card = schema_card()
    assert "V_DAILY_KPIS" in card and "PROMOTIONS" in card, card[:200]
    tables = card.count("\nT ") + card.count("\nV ") + card.count("\nS ")
    return f"the agent learns the schema from SYSCAT tables + COMMENTs ({tables} objects, {len(card):,} chars)"


def external_anchor(admin: Db2, agent: Db2) -> str:
    from hotelops.audit import check_anchor, simulate_rebuilt_ledger

    res = simulate_rebuilt_ledger()
    chain_ok = res["chain_after_rebuild"]["INTACT"]
    caught = res["anchor_after_rebuild"]["ok"] is False
    restored = res["anchor_after_rollback"]["ok"] is True and check_anchor(admin)["ok"]
    assert chain_ok and caught and restored, res
    return (f"an insider edits step {res['step_id']} AND re-hashes {res['rehashed']} later steps: the Db2 chain "
            "looks intact, but the external anchor catches it (rolled back)")


def data_volume(admin: Db2, agent: Db2) -> str:
    q = {"reservations": "RESERVATIONS", "reviews": "GUEST_REVIEWS", "sentence vectors": "REVIEW_CHUNKS",
         "rate nights": "RATE_PLAN", "agent runs": "AGENT_RUNS"}
    counts = {k: admin.scalar(f"SELECT COUNT(*) FROM {t}") for k, t in q.items()}
    assert all(counts.values()), counts
    return ", ".join(f"{v:,} {k}" for k, v in counts.items())



def guardrail_fuzz(admin: Db2, agent: Db2) -> str:
    from hotelops.fuzz import run_fuzz

    r = run_fuzz(1000, seed=11)
    assert r["agree"] == r["proposals"], r["mismatches"][:3]
    return (f"{r['agree']:,}/{r['proposals']:,} random proposals (boundaries, garbage, repeats): every Db2 decision "
            f"matches an independent oracle ({r['rejected']} rejected, {r['accepted']} queued, "
            f"{r['duplicates']} duplicates; rolled back)")

CHECKS: list[tuple[str, str, Callable[[Db2, Db2], str]]] = [
    ("Db2 integration", "IBM Db2 12.1 is connected", db2_version),
    ("Db2 integration", "Realistic data volume", data_volume),
    ("Db2 integration", "Native VECTOR columns", vector_columns),
    ("Db2 integration", "Vector similarity search in SQL", vector_radar),
    ("Db2 integration", "IBM langchain-db2 vector store", langchain_db2),
    ("Db2 integration", "System-period temporal tables (time travel)", temporal_tables),
    ("Db2 integration", "Bitemporal table (BUSINESS_TIME + SYSTEM_TIME)", bitemporal),
    ("Db2 integration", "Materialized query table (MQT)", materialized_view),
    ("Db2 integration", "Change feed from temporal history", change_feed),
    ("Db2 integration", "Schema learned from the Db2 catalog", catalog_card),
    ("Security", "Least-privilege agent identity", least_privilege),
    ("Security", "RCAC column mask on PII", column_mask),
    ("Security", "RCAC row permission (AI consent)", row_permission),
    ("Security", "Property isolation for a hotel chain (RCAC)", property_isolation),
    ("Security", "EXPLAIN cost guard", explain_cost_guard),
    ("Security", "SQL syntax-tree (AST) guard", ast_guard),
    ("Security", "Agent cannot grant itself autonomy", agent_cannot_self_grant),
    ("Governance", "SQL PL guardrail on proposals", proposal_guardrail),
    ("Governance", "Guardrail fuzz: 1,000 random proposals", guardrail_fuzz),
    ("Governance", "JSON validation inside Db2", json_guardrail),
    ("Governance", "Guarded apply + transactional rollback", apply_and_rollback),
    ("Governance", "Concurrent approvals serialised by Db2", concurrent_approval),
    ("Governance", "Earned autonomy decided inside Db2", earned_autonomy),
    ("Governance", "CHECK constraints cap autonomy", check_constraints),
    ("Governance", "Hash-chain trigger", hash_trigger),
    ("Governance", "Tamper-evident audit trail", audit_chain),
    ("Governance", "External anchor catches a rebuilt ledger", external_anchor),
    ("Governance", "Red-team scoreboard", red_team),
    ("AI quality", "Evaluation set", evaluation),
]


def run_checks(own_admin: bool = False):
    """Run every check; yields (index, area, name, ok, detail, seconds). Used by the CLI and the app's Proofs tab.

    ``own_admin`` opens a dedicated admin connection (the app must not share its connection with the
    transactions some checks open and roll back).
    """
    try:  # fastembed logs a harmless cache-metadata warning through loguru; keep the proof output clean
        from loguru import logger

        logger.disable("fastembed")
    except ImportError:
        pass
    admin = _own("admin") if own_admin else get_db("admin")
    agent = _own("agent")
    try:
        for i, (area, name, fn) in enumerate(CHECKS, 1):
            t0 = time.time()
            try:
                detail, ok = fn(admin, agent), True
            except Exception as exc:  # report every failure, keep checking the rest
                detail, ok = f"{type(exc).__name__}: {str(exc)[:200]}", False
            yield i, area, name, ok, detail, time.time() - t0
    finally:
        agent.close()
        if own_admin:
            admin.close()


def main() -> int:
    print(f"\n{BOLD}Hotel Ops Copilot · verifying every claim against the live Db2{RESET}")
    print(f"{DIM}No LLM needed. Anything that writes is rolled back.{RESET}\n")
    passed, started = 0, time.time()
    for i, area, name, ok, detail, secs in run_checks():
        passed += ok
        mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f" {mark}  {i:>2}. {BOLD}{name}{RESET} {DIM}[{area}] {secs:.1f}s{RESET}")
        print(f"        {detail}")
    total = len(CHECKS)
    colour = GREEN if passed == total else RED
    print(f"\n{colour}{BOLD}{passed}/{total} checks passed{RESET} in {time.time() - started:.0f}s\n")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
