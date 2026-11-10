"""Fault-injection eval: plant labelled faults into clean real station-days and compare
AQI Truth's Db2 detectors with (a) a min/max threshold rule and (b) a plain average (no checks).

The faults are SIMULATED; the days they are planted into are REAL (OpenAQ copy of CPCB data).
Detector settings in sql/02_reference.sql were fixed before this eval was written and are not tuned here.
Usage: DB2_PASSWORD=... python eval/fault_injection.py [--n 200] [--seed 7]"""
import argparse, collections, datetime as dt, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from db import connect, run_script, rows

ROOT = os.path.join(os.path.dirname(__file__), "..")
FAULTS = ["STUCK", "SPIKE", "DROPOUT", "SENTINEL", "ZERO", "SCALE"]
PARAMS = ["pm25", "pm10", "no2", "o3"]

def clean_days(conn, month_from, month_to):
    """Param-days with 24 valid hours, no stuck/jump flags and no implausible raw values."""
    return rows(conn, """
      SELECT STATION_ID, PARAM, DATE(HR - 1 SECOND) AS D
        FROM AQ.HOURLY
       WHERE PARAM IN ('pm25','pm10','no2','o3') AND STATION_ID <> 8118
         AND HR > ? AND HR <= ?
       GROUP BY STATION_ID, PARAM, DATE(HR - 1 SECOND)
      HAVING SUM(IS_VALID) = 24 AND SUM(FLAT) = 0 AND SUM(JUMP) = 0 AND SUM(N_RAW - N_OK) = 0""", (month_from, month_to))

def inject(kind, readings, rng):
    """readings: list of [ts, value] for one param-day (96 quarter-hours). Returns faulted copy."""
    r = [list(x) for x in readings]
    hours = sorted({t.replace(minute=0, second=0) for t, _ in r})  # hour a reading starts in, as in BUILD_HOURLY
    if kind == "STUCK":          # sensor freezes: same value for 6 consecutive hours
        h0 = rng.randrange(0, len(hours) - 6); frozen = None
        for x in r:
            hb = x[0].replace(minute=0, second=0)
            if hours[h0] <= hb < hours[h0] + dt.timedelta(hours=6):
                frozen = x[1] if frozen is None else frozen; x[1] = frozen
    elif kind == "SPIKE":        # one hour reads 10x
        h = rng.choice(hours[1:])
        for x in r:
            if x[0].replace(minute=0, second=0) == h: x[1] *= 10
    elif kind == "DROPOUT":      # 10 hours of no data
        drop = set(rng.sample(hours, 10))
        r = [x for x in r if x[0].replace(minute=0, second=0) not in drop]
    elif kind in ("SENTINEL", "ZERO", "SCALE"):  # 3-4 hours of error codes, zeros or unit errors
        n = 3 if kind == "SENTINEL" else 4
        h0 = rng.randrange(0, len(hours) - n); bad = set(hours[h0:h0 + n])
        for x in r:
            if x[0].replace(minute=0, second=0) in bad:
                x[1] = -9999.0 if kind == "SENTINEL" else (0.0 if kind == "ZERO" else x[1] * 1000)
    return r

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=200); ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args(); rng = random.Random(a.seed)
    conn = connect()
    # Fresh eval schema AQE built from the SAME SQL files as production (schema name rewritten).
    cur = conn.cursor()
    if rows(conn, "SELECT COUNT(*) FROM SYSCAT.SCHEMATA WHERE SCHEMANAME = 'AQE'")[0][0]:
        cur.callproc("SYSPROC.ADMIN_DROP_SCHEMA", ("AQE", None, "ERRSCHEMA", "ERRTABLE")); conn.commit()
    for f in ("01_schema.sql", "02_reference.sql", "04_audit.sql"):
        run_script(conn, os.path.join(ROOT, "sql", f), schema="AQE")

    pool = clean_days(conn, "2025-09-01 00:00:00", "2026-01-01 00:00:00")
    rng.shuffle(pool)
    per = a.n // len(FAULTS)
    plan = [(k, None) for k in FAULTS for _ in range(per)] + [("CLEAN", None)] * (a.n // 2)
    cases = []
    for cid, ((kind, _), (sid, param, day)) in enumerate(zip(plan, pool)):
        start = dt.datetime.combine(day, dt.time()); end = start + dt.timedelta(days=1)
        rd = rows(conn, "SELECT TS, VALUE FROM AQ.READING WHERE STATION_ID=? AND PARAM=? AND TS >= ? AND TS < ? ORDER BY TS",
                  (sid, param, start, end))
        fr = rd if kind == "CLEAN" else inject(kind, rd, rng)
        fake = 900000 + cid
        cur.executemany("INSERT INTO AQE.READING (STATION_ID, PARAM, TS, VALUE, UNIT_SRC) VALUES (?,?,?,?,?)",
                        [(fake, param, t, v, "eval") for t, v in fr])
        cases.append(dict(id=cid, kind=kind, station=sid, param=param, day=day, fake=fake, raw=fr))
    conn.commit()
    cur.execute("CALL AQE.BUILD_HOURLY(?, ?)", ("2025-08-31 00:00:00", "2026-01-02 00:00:00")); conn.commit()

    maxv = dict(rows(conn, "SELECT PARAM, MAX_V FROM AQE.PLAUSIBLE"))
    res = collections.defaultdict(lambda: collections.Counter())
    for c in cases:
        start = dt.datetime.combine(c["day"], dt.time())
        h = rows(conn, """SELECT COALESCE(SUM(IS_VALID),0), COALESCE(SUM(FLAT),0), COALESCE(SUM(JUMP),0), COALESCE(SUM(N_RAW-N_OK),0)
                            FROM AQE.HOURLY WHERE STATION_ID=? AND PARAM=? AND HR > ? AND HR <= ?""",
                 (c["fake"], c["param"], start, start + dt.timedelta(days=1)))[0]
        valid, flat, jump, bad = h
        ours = valid < 16 or flat > 0 or jump > 0 or bad > 0
        base = any(v is not None and (v < 0 or v > maxv[c["param"]]) for _, v in c["raw"])
        res[c["kind"]]["n"] += 1; res[c["kind"]]["ours"] += ours; res[c["kind"]]["base"] += base
    out = ["| Planted fault | Cases | AQI Truth (Db2) flags | Min/max threshold flags | Plain average flags |", "|---|---|---|---|---|"]
    for k in FAULTS + ["CLEAN"]:
        r = res[k]; lab = "No fault (false alarms)" if k == "CLEAN" else k.title()
        out.append(f"| {lab} | {r['n']} | {r['ours']} ({100*r['ours']//max(r['n'],1)}%) | {r['base']} ({100*r['base']//max(r['n'],1)}%) | 0 (0%) |")
    tp_o = sum(res[k]["ours"] for k in FAULTS); tp_b = sum(res[k]["base"] for k in FAULTS); nf = sum(res[k]["n"] for k in FAULTS)
    out.append(f"\nFaults caught: AQI Truth {tp_o}/{nf} ({100*tp_o/nf:.0f}%), threshold {tp_b}/{nf} ({100*tp_b/nf:.0f}%), plain average 0/{nf}. "
               f"False alarms on clean days: AQI Truth {res['CLEAN']['ours']}/{res['CLEAN']['n']}, threshold {res['CLEAN']['base']}/{res['CLEAN']['n']}.")
    out.append(f"Clean real param-days available: {len(pool)}; seed {a.seed}.")
    text = "\n".join(out); print(text)
    open(os.path.join(ROOT, "eval", "fault_injection_results.md"), "w").write(
        "# Fault-injection results\n\nFaults are simulated; the days they are planted into are real.\n\n" + text + "\n")

if __name__ == "__main__":
    main()
