"""Scale benchmark: the same Db2 schema at 1,000,000 reservations, in a separate throwaway schema.

    python src/benchmark_scale.py              # 1,000,000 reservations, writes docs/scale_benchmark.md
    python src/benchmark_scale.py 200000       # a smaller run
    python src/benchmark_scale.py 1000000 --keep   # keep schema HOTELSCALE afterwards

It builds schema HOTELSCALE from the project's own DDL (01_schema.sql + 04_extensions.sql), loads a 12,000-room
hotel group with N reservations entirely inside Db2 (INSERT ... SELECT), collects statistics, and measures the
features the copilot relies on. The demo schema HOTELOPS is never touched. No LLM is needed.
"""
from __future__ import annotations

import datetime as dt
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hotelops.audit import CHAIN_SQL  # noqa: E402
from hotelops.config import PROJECT_ROOT, load_settings  # noqa: E402
from hotelops.costguard import max_cost  # noqa: E402
from hotelops.db import Db2, Db2Error  # noqa: E402

BENCH = "HOTELSCALE"
SQL_DIR = Path(__file__).resolve().parent / "sql"
OUT = PROJECT_ROOT / "docs" / "scale_benchmark.md"
ROOMS = 12_000
GUESTS = 200_000
STEPS = 50_000
DIGITS = "(VALUES 0,1,2,3,4,5,6,7,8,9) AS"


def connect() -> Db2:
    s = load_settings().db2
    conn = s.conn_str(s.admin_user, s.admin_password).replace("CURRENTSCHEMA=HOTELOPS", f"CURRENTSCHEMA={BENCH}")
    return Db2(conn, "scale-bench", query_timeout=600)


def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def timed(db: Db2, sql: str, params=(), runs: int = 5) -> float:
    """Median wall time in ms over ``runs`` executions (first run discarded as warm-up)."""
    db.query(sql, params)
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        db.query(sql, params)
        times.append((time.perf_counter() - t0) * 1000)
    return statistics.median(times)


def explain_cost(db: Db2, sql: str) -> float:
    qno = int(time.time() * 1000) % 2_000_000_000
    db.execute(f"EXPLAIN PLAN SET QUERYNO = {qno} FOR {sql}")
    cost = db.scalar("SELECT TOTAL_COST FROM SYSTOOLS.EXPLAIN_STATEMENT WHERE QUERYNO = ? AND EXPLAIN_LEVEL = 'P' "
                     "ORDER BY EXPLAIN_TIME DESC FETCH FIRST 1 ROW ONLY", (qno,))
    db.execute("DELETE FROM SYSTOOLS.EXPLAIN_INSTANCE WHERE (EXPLAIN_TIME, SOURCE_NAME) IN ("
               "SELECT EXPLAIN_TIME, SOURCE_NAME FROM SYSTOOLS.EXPLAIN_STATEMENT WHERE QUERYNO = ?)", (qno,))
    return float(cost or 0)


def drop_schema(db: Db2) -> None:
    for t in ("ROOMS", "RESERVATIONS", "RATE_PLAN", "AUTONOMY_POLICY", "PROMOTIONS"):
        try:
            db.execute(f"ALTER TABLE {BENCH}.{t} DROP VERSIONING")
        except Db2Error:
            pass
    try:
        db.call("SYSPROC.ADMIN_DROP_SCHEMA", BENCH, None, "ERRSCHEMA", "ERRTABLE")
    except Db2Error as exc:
        log(f"  (drop schema: {str(exc)[:120]})")
    try:
        db.execute("DROP TABLE ERRSCHEMA.ERRTABLE")
    except Db2Error:
        pass


def build(db: Db2, n: int) -> dict:
    drop_schema(db)
    db.execute(f"CREATE SCHEMA {BENCH}")
    db.execute(f"SET SCHEMA {BENCH}")
    for name in ("01_schema.sql", "04_extensions.sql"):
        db.run_script((SQL_DIR / name).read_text(encoding="utf-8"))
    log("  schema built from 01_schema.sql + 04_extensions.sql")
    db.execute("INSERT INTO ROOM_TYPES SELECT * FROM HOTELOPS.ROOM_TYPES")
    db.execute(f"INSERT INTO ROOMS (ROOM_NO, ROOM_TYPE_ID, FLOOR_NO) "
               f"SELECT 'R' || TRIM(CHAR(N)), 1 + MOD(N, 6), 1 + MOD(N / 40, 30) FROM ("
               f"SELECT A.D * 10000 + B.D * 1000 + C.D * 100 + D.D * 10 + E.D AS N "
               f"FROM {DIGITS} A(D), {DIGITS} B(D), {DIGITS} C(D), {DIGITS} D(D), {DIGITS} E(D)) T WHERE N < {ROOMS}")
    db.execute(f"INSERT INTO GUESTS (GUEST_ID, FULL_NAME, EMAIL, PHONE, COUNTRY, LOYALTY_TIER) "
               f"SELECT N + 1, 'Guest ' || TRIM(CHAR(N)), 'g' || TRIM(CHAR(N)) || '@example.com', '+91 90000' || "
               f"TRIM(CHAR(N)), 'India', CASE WHEN MOD(N, 33) = 0 THEN 'PLATINUM' WHEN MOD(N, 11) = 0 THEN 'GOLD' "
               f"ELSE 'NONE' END FROM (SELECT A.D * 100000 + B.D * 10000 + C.D * 1000 + "
               f"D.D * 100 + E.D * 10 + F.D AS N FROM {DIGITS} A(D), {DIGITS} B(D), {DIGITS} C(D), "
               f"{DIGITS} D(D), {DIGITS} E(D), {DIGITS} F(D)) T WHERE N < {GUESTS}")
    db.execute("INSERT INTO RATE_PLAN (ROOM_TYPE_ID, STAY_DATE, RATE) SELECT RT.ROOM_TYPE_ID, C.CAL_DATE, "
               "RT.BASE_RATE FROM ROOM_TYPES RT CROSS JOIN CALENDAR C")
    t0 = time.time()
    batch = 20_000  # Db2 Community's default transaction log (~100 MB) fills on 100,000-row inserts
    for start in range(0, n, batch):  # batches keep the transaction log small
        db.execute(
            "INSERT INTO RESERVATIONS (RESERVATION_ID, GUEST_ID, ROOM_TYPE_ID, ROOM_NO, CHECK_IN, CHECK_OUT, ADULTS, "
            "CHANNEL, STATUS, NIGHTLY_RATE, TOTAL_AMOUNT, BOOKED_AT) "
            "SELECT N + 1, 1 + MOD(BIGINT(N) * 7, ?), 1 + MOD(N, 6), NULL, CI, CI + (1 + MOD(N, 4)) DAYS, 2, "
            "CASE MOD(N, 4) WHEN 0 THEN 'DIRECT' WHEN 1 THEN 'OTA' WHEN 2 THEN 'CORPORATE' ELSE 'WALK_IN' END, "
            "CASE WHEN MOD(N, 25) = 0 THEN 'CANCELLED' WHEN CI + (1 + MOD(N, 4)) DAYS <= CURRENT DATE THEN "
            "'CHECKED_OUT' WHEN CI <= CURRENT DATE THEN 'CHECKED_IN' ELSE 'CONFIRMED' END, 5000, "
            "5000 * (1 + MOD(N, 4)), TIMESTAMP(CI - 20 DAYS, '10:00:00') FROM ("
            "SELECT N, CURRENT DATE - 180 DAYS + MOD(BIGINT(N) * 7919, 296) DAYS AS CI FROM ("
            "SELECT A.D * 10000 + B.D * 1000 + C.D * 100 + D.D * 10 + E.D + ? AS N "
            f"FROM {DIGITS} A(D), {DIGITS} B(D), {DIGITS} C(D), {DIGITS} D(D), {DIGITS} E(D)) X WHERE N < ?) Y",
            (GUESTS, start, min(start + batch, n)))
        # the generator above yields 100,000 ids per call (offset by start)
    load_s = time.time() - t0
    count = db.scalar("SELECT COUNT(*) FROM RESERVATIONS")
    log(f"  loaded {count:,} reservations in {load_s:.0f} s")
    return {"reservations": count, "load_s": load_s}


def runstats(db: Db2) -> float:
    t0 = time.time()
    for t in [r["TABNAME"] for r in db.query("SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TYPE IN "
                                             "('T', 'S')", (BENCH,))]:
        db.execute(f"CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE {BENCH}.{t} WITH DISTRIBUTION AND INDEXES ALL')")
    return time.time() - t0


def measure(db: Db2) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    kpi_one = "SELECT OCCUPANCY_PCT FROM V_DAILY_KPIS WHERE STAY_DATE = CURRENT DATE"
    kpi_30 = ("SELECT STAY_DATE, OCCUPANCY_PCT, ADR, REVPAR FROM V_DAILY_KPIS WHERE STAY_DATE BETWEEN "
              "CURRENT DATE - 30 DAYS AND CURRENT DATE - 1 DAY")
    mqt_30 = kpi_30.replace("V_DAILY_KPIS", "MQT_DAILY_KPIS")

    cost_one = explain_cost(db, kpi_one)
    rows.append(("EXPLAIN cost guard: the agent's \"occupancy tonight\" query", f"{cost_one:,.0f} timerons",
                 f"{'passes' if cost_one <= max_cost() else 'REFUSED by'} the {max_cost():,.0f}-timeron guard"))
    cross = explain_cost(db, "SELECT COUNT(*) FROM RESERVATIONS A, RESERVATIONS B")
    rows.append(("EXPLAIN cost guard: a runaway self cross join", f"{cross:,.0f} timerons", "refused before it runs"))

    live = timed(db, kpi_30, runs=3)
    t0 = time.time()
    db.execute("REFRESH TABLE MQT_DAILY_KPIS")
    refresh = time.time() - t0
    db.execute(f"CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE {BENCH}.MQT_DAILY_KPIS')")
    mat = timed(db, mqt_30)
    cost_mqt = explain_cost(db, kpi_one.replace("V_DAILY_KPIS", "MQT_DAILY_KPIS"))
    rows.append(("Same \"occupancy tonight\" question asked of the MQT", f"{cost_mqt:,.0f} timerons",
                 f"{'passes' if cost_mqt <= max_cost() else 'REFUSED by'} the guard: at scale the agent should read "
                 "KPIs from the MQT"))
    rows.append(("30-night KPI history from the live view", f"{live:,.0f} ms", "aggregates every reservation"))
    rows.append(("Same 30 nights from the MQT", f"{mat:,.1f} ms",
                 f"**{live / max(mat, 0.01):,.0f}× faster**; `REFRESH TABLE` took {refresh:.1f} s"))

    t0 = time.time()
    top = db.scalar("SELECT MAX(RESERVATION_ID) FROM RESERVATIONS")
    for lo in range(0, top + 1, 100_000):  # in slices, so each statement fits the default transaction log
        db.execute("UPDATE RESERVATIONS SET STATUS = 'CANCELLED' WHERE MOD(RESERVATION_ID, 10) = 3 AND STATUS = "
                   "'CONFIRMED' AND RESERVATION_ID BETWEEN ? AND ?", (lo, lo + 99_999))
    upd = time.time() - t0
    changed = db.scalar("SELECT COUNT(*) FROM RESERVATIONS_HISTORY")
    before = db.scalar("SELECT MAX(SYS_START) FROM RESERVATIONS_HISTORY")
    as_of = ("SELECT COUNT(*) FROM RESERVATIONS FOR SYSTEM_TIME AS OF CAST(? AS TIMESTAMP) "
             "WHERE STATUS = 'CONFIRMED' AND CHECK_IN BETWEEN CURRENT DATE AND CURRENT DATE + 14 DAYS")
    t_asof = timed(db, as_of, (str(before),))
    then = db.query(as_of, (str(before),))[0]
    rows.append(("Mass update with automatic history", f"{changed:,} row versions in {upd:.1f} s",
                 "Db2 writes `RESERVATIONS_HISTORY` itself, no triggers"))
    rows.append(("Time travel: confirmed arrivals next 14 days `AS OF` before the change", f"{t_asof:,.0f} ms",
                 f"answers {list(then.values())[0]:,} from history"))
    feed = ("SELECT COUNT(*) FROM RESERVATIONS FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30' V "
            "JOIN RESERVATIONS FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30' P "
            "ON P.RESERVATION_ID = V.RESERVATION_ID AND P.SYS_END = V.SYS_START "
            "WHERE V.SYS_START >= CURRENT TIMESTAMP - 24 HOURS")
    t_feed = timed(db, feed, runs=3)
    rows.append(("Change feed (before/after pairs from history)", f"{t_feed:,.0f} ms",
                 f"{db.scalar(feed):,} changes paired"))

    db.execute("INSERT INTO AGENT_RUNS (RUN_ID, USER_QUESTION, MODEL) VALUES ('bench', 'scale benchmark', 'none')")
    t0 = time.time()
    db.bulk_insert("INSERT INTO AGENT_STEPS (RUN_ID, AGENT, TOOL_NAME, TOOL_INPUT, TOOL_OUTPUT, OK, LATENCY_MS) "
                   "VALUES ('bench', 'analyst', 'run_sql', ?, ?, 1, 5)",
                   [(f'{{"query": "SELECT {i}"}}', f'{{"rows": {i}}}') for i in range(STEPS)])
    ins = time.time() - t0
    t_chain = timed(db, CHAIN_SQL, runs=3)
    chain = db.query(CHAIN_SQL)[0]
    rows.append(("Audit steps hash-chained by the trigger", f"{STEPS:,} steps in {ins:.0f} s",
                 f"{STEPS / ins:,.0f} steps/s including SHA-256 per row"))
    rows.append(("Verify the whole hash chain inside Db2 (`LAG()` + `HASH`)", f"{t_chain:,.0f} ms",
                 "intact" if chain["BROKEN"] == 0 else f"BROKEN at {chain['FIRST_BROKEN_STEP']}"))
    return rows


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 1_000_000
    keep = "--keep" in sys.argv
    db = connect()
    log(f"Scale benchmark: {n:,} reservations in schema {BENCH} (demo schema HOTELOPS untouched)")
    info = build(db, n)
    st = runstats(db)
    log(f"  RUNSTATS on all tables: {st:.0f} s")
    rows = measure(db)
    lvl = db.scalar("SELECT SERVICE_LEVEL FROM SYSIBMADM.ENV_INST_INFO")
    if not keep:
        drop_schema(db)
        log(f"  dropped schema {BENCH}")
    lines = [
        "# Scale benchmark: the same schema at 1,000,000 reservations",
        "",
        f"Run {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC on {lvl} (Docker on a laptop, WSL2) · "
        f"**{info['reservations']:,} reservations**, {ROOMS:,} rooms, {GUESTS:,} guests, loaded inside Db2 in "
        f"{info['load_s']:.0f} s · statistics collected in {st:.0f} s · no LLM.",
        "",
        "The schema is built from the project's own `01_schema.sql` and `04_extensions.sql` in a separate schema "
        "(`HOTELSCALE`), so the views, temporal tables, MQT and the hash-chain trigger are exactly the ones the "
        "copilot uses. Timings are medians of repeated runs after one warm-up. Reproduce with "
        "`python src/benchmark_scale.py`.",
        "",
        "| What | Measured | Note |",
        "|---|---|---|",
        *[f"| {a} | {b} | {c} |" for a, b, c in rows],
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    log(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
