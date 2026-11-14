"""Create the HOTELOPS schema in IBM Db2, load synthetic data and embed reviews.

Usage (from the project folder):
    python src/setup_db.py            # create everything (fails if it already exists)
    python src/setup_db.py --reset    # drop and recreate the HOTELOPS schema
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hotelops import seed  # noqa: E402
from hotelops.config import SCHEMA, load_settings  # noqa: E402
from hotelops.db import Db2Error, get_db, reset_connections, vector_literal  # noqa: E402

SQL_DIR = Path(__file__).resolve().parent / "sql"
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

TEMPORAL_TABLES = ["ROOMS", "RESERVATIONS", "RATE_PLAN", "AUTONOMY_POLICY", "PROMOTIONS"]
DROP_ORDER = [
    "PROCEDURE SP_ROLLBACK_ACTION", "PROCEDURE SP_REJECT_ACTION", "PROCEDURE SP_APPLY_ACTION",
    "PROCEDURE SP_PROPOSE_ACTION",
    "TABLE MQT_DAILY_KPIS", "TABLE PROMOTIONS", "TABLE PROMOTIONS_HISTORY",
    "VIEW V_REVIEW_SUMMARY", "VIEW V_DAILY_KPIS", "VIEW V_ROOM_TYPE_DAY",
    "TABLE AGENT_STEPS", "TABLE AGENT_RUNS", "TABLE AGENT_ACTIONS", "TABLE MAINTENANCE_TICKETS",
    "TABLE POLICY_KB", "TABLE AUTONOMY_POLICY", "TABLE AUTONOMY_POLICY_HISTORY",
    "TABLE REVIEW_CHUNKS", "TABLE GUEST_REVIEWS", "TABLE RATE_PLAN", "TABLE RATE_PLAN_HISTORY",
    "TABLE RESERVATIONS", "TABLE RESERVATIONS_HISTORY", "TABLE GUESTS",
    "TABLE ROOMS", "TABLE ROOMS_HISTORY", "TABLE ROOM_TYPES", "TABLE CALENDAR",
    "TABLE AGENT_SCOPE", "TABLE PROPERTIES",
]


def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def drop_all(db) -> None:
    log("Dropping existing HOTELOPS objects ...")
    for t in TEMPORAL_TABLES:
        try:
            db.execute(f"ALTER TABLE {SCHEMA}.{t} DROP VERSIONING")
        except Db2Error:
            pass
    for stmt in ("SET EVENT MONITOR HOTELOPS_AGENT_VIOLATIONS STATE 0", "DROP EVENT MONITOR HOTELOPS_AGENT_VIOLATIONS",
                 "DROP TABLE AGENT_THRESHOLD_VIOLATIONS", "DROP THRESHOLD HOTELOPS_AGENT_MAX_COST",
                 "DROP THRESHOLD HOTELOPS_AGENT_MAX_ROWS", "DROP THRESHOLD HOTELOPS_AGENT_MAX_TIME",
                 "ALTER WORKLOAD HOTELOPS_AGENT_WL DISABLE", "DROP WORKLOAD HOTELOPS_AGENT_WL"):
        try:  # Db2 workload management objects are database-wide, not in the HOTELOPS schema
            db.execute(stmt)
        except Db2Error:
            pass
    remaining = ["MASK GUEST_EMAIL_MASK", "MASK GUEST_PHONE_MASK", "PERMISSION GUEST_CONSENT_ROWS", *DROP_ORDER]
    for _ in range(3):  # a later pass drops what an earlier one could not (e.g. AGENT_SCOPE, used by permissions)
        failed = []
        for stmt in remaining:
            try:
                db.execute(f"DROP {stmt}")
            except Db2Error as exc:
                if "SQL0204N" not in str(exc):  # SQL0204N: already gone
                    failed.append(stmt)
        if not failed:
            break
        remaining = failed
    try:
        db.execute("DROP ROLE HOTELOPS_AGENT")
    except Db2Error:
        pass


def create_schema(db, agent_user: str) -> None:
    try:
        db.execute(f"CREATE SCHEMA {SCHEMA}")
    except Db2Error as exc:
        if "SQL0601N" not in str(exc):  # already exists
            raise
    for name in ("01_schema.sql", "02_procedures.sql", "04_extensions.sql"):
        n = db.run_script((SQL_DIR / name).read_text(encoding="utf-8"))
        log(f"  {name}: {n} statements")


def apply_security(db, agent_user: str) -> None:
    n = db.run_script((SQL_DIR / "03_security.sql").read_text(encoding="utf-8"),
                      {"AGENT_USER": agent_user.upper()},
                      ignore_sqlstates=("SQL0556N",))  # revoke of privilege not held
    log(f"  03_security.sql: {n} statements (role, grants, column masks, consent and property row permissions)")
    from hotelops.costguard import ensure_explain_tables

    if ensure_explain_tables(db):
        log("  created EXPLAIN tables in SYSTOOLS (cost guard for agent SQL)")


def load_data(db) -> dict:
    today = dt.date.fromisoformat(str(db.scalar("SELECT CURRENT DATE FROM SYSIBM.SYSDUMMY1")))
    now = dt.datetime.fromisoformat(str(db.scalar("SELECT CURRENT TIMESTAMP(0) FROM SYSIBM.SYSDUMMY1")))
    ds = seed.build(today, now)  # Db2's clock: no seeded booking is later than the moment of setup
    log(f"Generated dataset anchored on {today}: {len(ds.rooms)} rooms, {len(ds.guests)} guests, "
        f"{len(ds.reservations)} reservations, {len(ds.reviews)} reviews")

    db.bulk_insert("INSERT INTO ROOM_TYPES (ROOM_TYPE_ID, CODE, NAME, TIER, BASE_RATE, FLOOR_RATE, CEILING_RATE, "
                   "MAX_OCCUPANCY) VALUES (?,?,?,?,?,?,?,?)", ds.room_types)
    db.bulk_insert("INSERT INTO ROOMS (ROOM_NO, ROOM_TYPE_ID, FLOOR_NO) VALUES (?,?,?)", ds.rooms)
    db.bulk_insert("INSERT INTO GUESTS (GUEST_ID, FULL_NAME, EMAIL, PHONE, COUNTRY, LOYALTY_TIER) "
                   "VALUES (?,?,?,?,?,?)", ds.guests)
    # A few guests have withdrawn consent for AI processing (DPDP Act 2023).
    # Db2 row permission GUEST_CONSENT_ROWS hides them from the agent identity.
    db.execute("UPDATE GUESTS SET AI_CONSENT = 'N' WHERE MOD(GUEST_ID, 40) = 0 AND GUEST_ID <> 901")
    db.bulk_insert(
        "INSERT INTO RESERVATIONS (RESERVATION_ID, GUEST_ID, ROOM_TYPE_ID, ROOM_NO, CHECK_IN, CHECK_OUT, "
        "ADULTS, CHANNEL, STATUS, NIGHTLY_RATE, TOTAL_AMOUNT, BOOKED_AT, SPECIAL_NOTE) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", ds.reservations)
    db.bulk_insert("INSERT INTO RATE_PLAN (ROOM_TYPE_ID, STAY_DATE, RATE) VALUES (?,?,?)", ds.rate_plan)

    # Realistic history for time travel: a revenue manager repriced the festive
    # peak a while ago, and then trimmed suites again.
    year = today.year if today <= dt.date(today.year, 12, 24) else today.year + 1
    peak = (dt.date(year, 12, 20), dt.date(year, 12, 31))
    db.execute("UPDATE RATE_PLAN SET RATE = ROUND(RATE * 1.10, -1), UPDATED_BY = 'rm.priya', "
               "CHANGE_REASON = 'Festive peak uplift' WHERE STAY_DATE BETWEEN ? AND ?", peak)
    time.sleep(1.2)
    db.execute("UPDATE RATE_PLAN SET RATE = ROUND(RATE * 0.95, -1), UPDATED_BY = 'rm.priya', "
               "CHANGE_REASON = 'Suite rates trimmed after OTA comp-set check' "
               "WHERE ROOM_TYPE_ID IN (5, 6) AND STAY_DATE BETWEEN ? AND ?", peak)
    load_promotions(db, today, ds.scenario)
    load_second_hotel(db)
    db.execute("REFRESH TABLE MQT_DAILY_KPIS")
    log(f"  refreshed MQT_DAILY_KPIS ({db.scalar('SELECT COUNT(*) FROM MQT_DAILY_KPIS')} nights materialised)")
    return {"today": today, "dataset": ds}


SECOND_HOTEL = 2  # Backwater House, Kochi: a second hotel of the group, invisible to the Goa agent


def load_second_hotel(db) -> None:
    """A small second hotel of the group, so the app's hotel switcher has something to switch to.

    It has its own room type codes (LSTD/LDLX/LSTE) and room numbers (K...), 24 rooms, a rate plan and about two
    thirds of its nights booked. The Goa agent identity is not scoped to it, so Db2 hides all of it from the AI.
    """
    p = SECOND_HOTEL
    db.execute("INSERT INTO PROPERTIES (PROPERTY_ID, CODE, NAME, CITY) VALUES (?, 'KOCHI', 'Backwater House', "
               "'Kochi')", (p,))
    db.bulk_insert("INSERT INTO ROOM_TYPES (ROOM_TYPE_ID, CODE, NAME, TIER, BASE_RATE, FLOOR_RATE, CEILING_RATE, "
                   "MAX_OCCUPANCY, PROPERTY_ID) VALUES (?,?,?,?,?,?,?,?,?)",
                   [(7, "LSTD", "Lagoon Standard", 1, 4200, 3000, 6500, 2, p),
                    (8, "LDLX", "Lagoon Deluxe", 2, 5800, 4200, 8800, 2, p),
                    (9, "LSTE", "Backwater Suite", 3, 9800, 7200, 15000, 3, p)])
    rooms = ([(f"K{100 + i}", 7, 1, p) for i in range(1, 13)] + [(f"K{200 + i}", 8, 2, p) for i in range(1, 9)]
             + [(f"K{300 + i}", 9, 3, p) for i in range(1, 5)])
    db.bulk_insert("INSERT INTO ROOMS (ROOM_NO, ROOM_TYPE_ID, FLOOR_NO, PROPERTY_ID) VALUES (?,?,?,?)", rooms)
    db.execute("INSERT INTO RATE_PLAN (ROOM_TYPE_ID, STAY_DATE, RATE, PROPERTY_ID) "
               "SELECT RT.ROOM_TYPE_ID, C.CAL_DATE, RT.BASE_RATE, RT.PROPERTY_ID FROM ROOM_TYPES RT, CALENDAR C "
               "WHERE RT.PROPERTY_ID = ? AND C.CAL_DATE BETWEEN CURRENT DATE - 30 DAYS AND CURRENT DATE + 90 DAYS",
               (p,))
    # two-night stays that start every third night in each room (staggered by room), about 2/3 occupancy
    db.execute(
        "INSERT INTO RESERVATIONS (RESERVATION_ID, GUEST_ID, ROOM_TYPE_ID, ROOM_NO, CHECK_IN, CHECK_OUT, CHANNEL, "
        "STATUS, NIGHTLY_RATE, TOTAL_AMOUNT, BOOKED_AT, PROPERTY_ID) "
        "SELECT 300000 + ROW_NUMBER() OVER (ORDER BY R.ROOM_NO, C.CAL_DATE), "
        "       1 + MOD(ROW_NUMBER() OVER (ORDER BY C.CAL_DATE, R.ROOM_NO) * 37, 900), R.ROOM_TYPE_ID, R.ROOM_NO, "
        "       C.CAL_DATE, C.CAL_DATE + 2 DAYS, "
        "       CASE MOD(DAYS(C.CAL_DATE), 3) WHEN 0 THEN 'DIRECT' WHEN 1 THEN 'OTA' ELSE 'CORPORATE' END, "
        "       CASE WHEN C.CAL_DATE + 2 DAYS <= CURRENT DATE THEN 'CHECKED_OUT' "
        "            WHEN C.CAL_DATE <= CURRENT DATE THEN 'CHECKED_IN' ELSE 'CONFIRMED' END, "
        "       RT.BASE_RATE, RT.BASE_RATE * 2, "
        "       TIMESTAMP(MIN(C.CAL_DATE - 14 DAYS, CURRENT DATE - 1 DAY), '10:00:00'), R.PROPERTY_ID "
        "FROM ROOMS R JOIN ROOM_TYPES RT ON RT.ROOM_TYPE_ID = R.ROOM_TYPE_ID "
        "CROSS JOIN CALENDAR C "
        "WHERE R.PROPERTY_ID = ? AND C.CAL_DATE BETWEEN CURRENT DATE - 60 DAYS AND CURRENT DATE + 30 DAYS "
        "  AND MOD(DAYS(C.CAL_DATE) + INT(SUBSTR(R.ROOM_NO, 2)), 3) = 0", (p,))
    n = db.scalar("SELECT COUNT(*) FROM RESERVATIONS WHERE PROPERTY_ID = ?", (p,))
    log(f"  loaded a second hotel of the group (Backwater House, Kochi): {len(rooms)} rooms, {n} reservations")


def load_promotions(db, today: dt.date, scenario: dict) -> None:
    """Bitemporal promotions: a weekend offer, then a later correction that splits it by stay date."""
    weak = [dt.date.fromisoformat(d) for d in scenario["weak_weekend"]]
    fri, end = weak[0], weak[-1] + dt.timedelta(days=1)
    day = dt.timedelta(days=1)
    db.bulk_insert(
        "INSERT INTO PROMOTIONS (PROMO_ID, ROOM_TYPE_ID, NAME, DISCOUNT_PCT, VALID_FROM, VALID_TO, CHANGE_REASON) "
        "VALUES (?,?,?,?,?,?,?)",
        [(1, 5, "Weekend suite saver", 10.0, fri, end, "Weak weekend: Junior Suites under 20% sold"),
         (2, 6, "Ocean Suite escape", 8.0, fri, end, "Weak weekend: Ocean Suites unsold"),
         (3, 4, "Family monsoon deal", 12.0, today + day, today + 30 * day, "Family rooms soft all month"),
         (4, 2, "Early-bird Deluxe", 5.0, today + 21 * day, today + 45 * day, "Book 3+ weeks ahead")])
    time.sleep(1.2)  # so the correction below has a later SYSTEM_TIME than the original offer
    db.execute("UPDATE PROMOTIONS FOR PORTION OF BUSINESS_TIME FROM ? TO ? "
               "SET DISCOUNT_PCT = 18, UPDATED_BY = 'rm.priya', "
               "CHANGE_REASON = 'Deeper cut for Sat-Sun: still under 20% sold' WHERE PROMO_ID = 1",
               (fri + day, end))
    log("  loaded 4 bitemporal promotions; rm.priya later deepened the Junior Suite offer for Sat-Sun only")


def collect_statistics(db) -> None:
    """RUNSTATS on every HOTELOPS table. Without statistics the optimizer guesses, and the EXPLAIN cost guard
    would refuse ordinary agent queries on a fresh database (a KPI query was costed at 177,163 timerons
    instead of about 1,900) until Db2's automatic statistics catch up."""
    tables = [r["TABNAME"] for r in db.query("SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TYPE IN "
                                             "('T', 'S') ORDER BY TABNAME", (SCHEMA,))]
    for t in tables:
        db.execute(f"CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE {SCHEMA}.{t} WITH DISTRIBUTION AND INDEXES ALL')")
    log(f"  collected optimizer statistics (RUNSTATS) on {len(tables)} tables")


def load_reviews(db, ds) -> None:
    from hotelops.embeddings import embed_documents

    texts = [r[5] for r in ds.reviews]
    chunks = []  # (chunk_id, review_id, seq, text)
    for r in ds.reviews:
        for seq, sentence in enumerate(s for s in SENTENCE_SPLIT.split(r[5]) if s.strip()):
            chunks.append((len(chunks) + 1, r[0], seq + 1, sentence.strip()[:600]))
    t0 = time.time()
    vectors = embed_documents(texts)
    chunk_vectors = embed_documents([c[3] for c in chunks])
    log(f"Embedded {len(texts)} reviews + {len(chunks)} sentence chunks locally in {time.time() - t0:.1f}s")
    db.bulk_insert(
        "INSERT INTO GUEST_REVIEWS (REVIEW_ID, RESERVATION_ID, ROOM_NO, SOURCE, RATING, REVIEW_TEXT, "
        "CREATED_AT, EMBEDDING) VALUES (?,?,?,?,?,?,?, VECTOR(?, 384, FLOAT32))",
        [(*r, vector_literal(v)) for r, v in zip(ds.reviews, vectors, strict=True)])
    db.bulk_insert(
        "INSERT INTO REVIEW_CHUNKS (CHUNK_ID, REVIEW_ID, SEQ, CHUNK_TEXT, EMBEDDING) "
        "VALUES (?,?,?,?, VECTOR(?, 384, FLOAT32))",
        [(*c, vector_literal(v)) for c, v in zip(chunks, chunk_vectors, strict=True)])


def verify(settings) -> None:
    log("Verifying least-privilege agent connection ...")
    reset_connections()
    agent = get_db("agent")
    sample = agent.query("SELECT GUEST_ID, EMAIL, PHONE FROM GUESTS FETCH FIRST 1 ROW ONLY")[0]
    log(f"  agent sees masked PII: {sample}")
    admin_n = get_db("admin").scalar("SELECT COUNT(*) FROM GUESTS")
    agent_n = agent.scalar("SELECT COUNT(*) FROM GUESTS")
    log(f"  row permission: admin sees {admin_n} guests, agent sees {agent_n} (opted-out guests hidden)")
    try:
        agent.execute("UPDATE RATE_PLAN SET RATE = 1 WHERE 1 = 0")
        raise SystemExit("SECURITY CHECK FAILED: agent user was able to UPDATE")
    except Db2Error as exc:
        log(f"  agent UPDATE correctly refused by Db2: {str(exc)[:90]}...")
    kpi = agent.query("SELECT STAY_DATE, OCCUPANCY_PCT, ADR, REVPAR FROM V_DAILY_KPIS "
                      "WHERE STAY_DATE = CURRENT DATE")
    log(f"  today's KPIs: {kpi}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="drop and recreate all HOTELOPS objects")
    parser.add_argument("--skip-verify", action="store_true")
    args = parser.parse_args()

    settings = load_settings()
    db = get_db("admin")
    log(f"Connected to Db2 {db.scalar('SELECT SERVICE_LEVEL FROM SYSIBMADM.ENV_INST_INFO')} "
        f"at {settings.db2.host}:{settings.db2.port}/{settings.db2.database}")
    if args.reset:
        drop_all(db)
    log("Creating schema, temporal tables, vector table, views and procedures ...")
    create_schema(db, settings.db2.agent_user)
    result = load_data(db)
    load_reviews(db, result["dataset"])
    from hotelops.knowledge import load_handbook

    log(f"Loaded {load_handbook()} policies into POLICY_KB with IBM langchain-db2 (DB2VS, VECTOR(384))")
    collect_statistics(db)
    log("Applying role-based security and column masks ...")
    apply_security(db, settings.db2.agent_user)
    from sample_runs import load as load_sample_runs

    n_runs = load_sample_runs()
    if n_runs:
        log(f"Loaded {n_runs} recorded agent runs into AGENT_RUNS / AGENT_STEPS (Audit tab works without an LLM key)")
    from hotelops.audit import ANCHOR_FILE, write_anchor

    anchor = write_anchor(db, note="setup")
    if anchor:
        log(f"Anchored audit chain head (step {anchor['step_id']}) outside Db2 in {ANCHOR_FILE}")
    if not args.skip_verify:
        verify(settings)
    log(f"Done. Planted scenarios: {result['dataset'].scenario}")


if __name__ == "__main__":
    main()
