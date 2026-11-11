"""One-command setup: build the Db2 schema, load OpenAQ CSVs, MERGE, run the audit, embed rule texts.
Usage: python src/load.py RAW_DIR FROM_DAY TO_DAY [--schema AQ] [--no-embed] [--append [--reaudit]] [--if-empty]
  default    rebuild: drop the schema and load from scratch (temporal history starts empty)
  --append   keep the schema and its history: MERGE the new files, so a value the publisher revised becomes a new
             version (old one kept in READING_HIST), then re-audit only the station-days whose readings changed
             (--reaudit: every day in the range, e.g. after a method change). Old verdicts stay; V_DAY shows the latest.
  --if-empty do nothing if the schema already holds an audit, except apply schema migrations (safe on every restart)
Example (sample shipped in the repo): python src/load.py data/sample 2025-10-01 2025-10-31"""
import argparse, csv, os, re, sys, tempfile, time
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(__file__))
from db import connect, run_script
import prepare

ROOT = os.path.join(os.path.dirname(__file__), "..")
POLLUTANTS = {"pm25", "pm10", "no2", "so2", "o3", "co"}
SCRIPTS = ["00_tablespace.sql", "01_schema.sql", "02_reference.sql", "04_audit.sql", "05_views.sql", "06_asklog.sql", "08_receipt.sql"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw"); ap.add_argument("day_from"); ap.add_argument("day_to")
    ap.add_argument("--schema", default="AQ"); ap.add_argument("--no-embed", action="store_true")
    ap.add_argument("--if-empty", action="store_true", help="do nothing if the schema already holds audited data (safe on every restart)")
    ap.add_argument("--append", action="store_true", help="keep the schema and its temporal history; re-audit changed days")
    ap.add_argument("--reaudit", action="store_true", help="with --append: re-audit every day in the range")
    a = ap.parse_args()
    s = a.schema.upper()
    conn = connect(); cur = conn.cursor()
    sch = None if s == "AQ" else s
    run_tolerant(conn, "00_tablespace.sql", sch)            # SYSTOOLSPACE must exist before ADMIN_DROP_SCHEMA
    cur.execute("SELECT COUNT(*) FROM SYSCAT.SCHEMATA WHERE SCHEMANAME = ?", (s,))
    exists = cur.fetchone()[0]
    if exists and (a.if_empty or a.append):
        migrate(conn, sch)
        if a.if_empty:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {s}.VERDICT")
                if cur.fetchone()[0] > 0:
                    print(f"schema {s} already loaded: migrations applied, nothing else to do"); return
            except Exception:
                conn.rollback()
    if exists and not a.append:
        print(f"schema {s} exists: dropping it"); cur.callproc("SYSPROC.ADMIN_DROP_SCHEMA", (s, None, "ERRSCHEMA", "ERRTABLE")); conn.commit()
    if not exists or not a.append:
        for f in SCRIPTS[1:]:
            run_script(conn, os.path.join(ROOT, "sql", f), schema=sch)
        run_tolerant(conn, "07_access.sql", sch)    # the role is database-wide, so it may already exist
        run_tolerant(conn, "09_mqt_mask.sql", sch)
        run_tolerant(conn, "10_rule_version.sql", sch)
    cur.execute(f"DELETE FROM {s}.STAGE_READING"); conn.commit()
    cur.execute("VALUES CURRENT TIMESTAMP"); load_start = cur.fetchone()[0]
    t = time.time()
    out = tempfile.mkdtemp(); prepare.main(a.raw, out)
    with open(os.path.join(out, "stations.del")) as fh:
        for r in csv.reader(fh):
            cur.execute(f"""MERGE INTO {s}.STATION T USING (VALUES (CAST(? AS INTEGER), CAST(? AS VARCHAR(120)), CAST(? AS VARCHAR(20)),
                            CAST(? AS DECIMAL(9,6)), CAST(? AS DECIMAL(9,6)))) N (ID, NAME, OP, LAT, LON) ON T.STATION_ID = N.ID
                            WHEN NOT MATCHED THEN INSERT VALUES (N.ID, N.NAME, N.OP, N.LAT, N.LON)""", (int(r[0]), r[1], r[2] or None, r[3], r[4]))
    batch = []
    with open(os.path.join(out, "readings.del")) as fh:
        for r in csv.reader(fh):
            if r[1] not in POLLUTANTS: continue        # weather channels are not part of the AQI
            # ibm_db sizes string parameters from the first row of a batch, so pad to fixed widths
            batch.append((int(r[0]), r[1].ljust(4), r[2], float(r[3]) if r[3] else None, r[4][:10].ljust(10)))
            if len(batch) == 20000:
                cur.executemany(f"INSERT INTO {s}.STAGE_READING VALUES (?, RTRIM(CAST(? AS VARCHAR(12))), ?, ?, RTRIM(CAST(? AS VARCHAR(10))))", batch); batch = []
    if batch: cur.executemany(f"INSERT INTO {s}.STAGE_READING VALUES (?, RTRIM(CAST(? AS VARCHAR(12))), ?, ?, RTRIM(CAST(? AS VARCHAR(10))))", batch)
    conn.commit()
    try:    # more secondary log files (an online change), so a big first load does not hit SQL0964C
        cur.callproc("SYSPROC.ADMIN_CMD", ("UPDATE DB CFG USING LOGSECOND 200",)); conn.commit()
    except Exception as e:
        conn.rollback(); print("could not raise LOGSECOND:", str(e)[:120])
    # The same MERGE as sql/03_merge.sql, run one station at a time with a commit after each,
    # so the full load (3M+ rows) never needs the whole transaction log at once.
    merge = open(os.path.join(ROOT, "sql", "03_merge.sql"), encoding="utf-8").read().split("@")[0]
    merge = "\n".join(l for l in merge.splitlines() if not l.strip().startswith("--")).replace("AQ.", s + ".")
    merge = merge.replace(f"FROM {s}.STAGE_READING)", f"FROM {s}.STAGE_READING WHERE STATION_ID = ?)")
    cur.execute(f"SELECT DISTINCT STATION_ID FROM {s}.STAGE_READING ORDER BY 1")
    for (sid,) in cur.fetchall():
        cur.execute(merge, (sid,)); conn.commit()
    cur.execute(f"SELECT COUNT(*) FROM {s}.READING"); print(f"{cur.fetchone()[0]} readings merged in {time.time()-t:.0f}s")
    cur.execute(f"SELECT COUNT(*) FROM {s}.READING_HIST"); print(f"{cur.fetchone()[0]} earlier versions kept in READING_HIST")
    t = time.time()
    d, end = date.fromisoformat(a.day_from), date.fromisoformat(a.day_to)
    # The hourly layer runs over the whole range at once, so stuck runs and jumps are seen across month edges.
    # Hours END in (from 00:00, to+1 00:00], so the last hour of the last day (23:00-24:00) is included.
    cur.callproc(f"{s}.BUILD_HOURLY", (f"{a.day_from} 00:00:00", f"{(end + timedelta(days=1)).isoformat()} 00:00:00")); conn.commit()
    if exists and a.append and not a.reaudit:
        # Only station-days whose readings are new or changed since this load began (a CPCB day is the hours
        # ending 01:00..24:00, so a reading stamped hh:mm belongs to DATE(TS)).
        cur.execute(f"""SELECT DISTINCT STATION_ID, DATE(TS) FROM {s}.READING WHERE SYS_START >= ? AND DATE(TS) BETWEEN ? AND ?
                        UNION SELECT DISTINCT STATION_ID, DATE(TS) FROM {s}.READING_HIST WHERE SYS_END >= ? AND DATE(TS) BETWEEN ? AND ?""",
                    (load_start, d, end, load_start, d, end))
        changed = set(cur.fetchall())
        # New days with no readings at all still need a verdict (NOT_COMPUTABLE), like a full audit gives them.
        cur.execute(f"""SELECT S.STATION_ID, D.DAY FROM {s}.STATION S,
                          (SELECT CAST(? AS DATE) + (N - 1) DAYS AS DAY FROM (SELECT ROW_NUMBER() OVER () AS N FROM SYSCAT.COLUMNS FETCH FIRST 400 ROWS ONLY) X) D
                        WHERE D.DAY <= CAST(? AS DATE) AND NOT EXISTS (SELECT 1 FROM {s}.VERDICT V WHERE V.STATION_ID = S.STATION_ID AND V.DAY = D.DAY)""", (d, end))
        changed = sorted(changed | set(cur.fetchall()))
        for i, (sid, day) in enumerate(changed, 1):
            cur.callproc(f"{s}.COMPUTE_AQI_AUDITED", (sid, day, 0))
            if i % 200 == 0: conn.commit()
        conn.commit(); print(f"re-audited {len(changed)} changed station-days")
    else:
        while d <= end:     # each station-day is audited independently, so commit once per month
            last = min(end, (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1))
            cur.callproc(f"{s}.AUDIT_RANGE", (d.isoformat(), last.isoformat())); conn.commit()
            print(f"audited {d} to {last}"); d = last + timedelta(days=1)
    try:    # the summary MQT is REFRESH DEFERRED: bring it up to this load
        cur.execute(f"REFRESH TABLE {s}.MQT_READING_DAY"); conn.commit()
    except Exception as e:
        conn.rollback(); print("refresh MQT:", str(e)[:120])
    # Fresh optimizer statistics after a bulk change, so plans (partition elimination, index choice) use real cardinalities.
    for tb in ("READING", "READING_HIST", "HOURLY", "VERDICT", "EVIDENCE", "STATION", "MQT_READING_DAY"):
        try:
            cur.callproc("SYSPROC.ADMIN_CMD", (f"RUNSTATS ON TABLE {s}.{tb} WITH DISTRIBUTION AND SAMPLED DETAILED INDEXES ALL",)); conn.commit()
        except Exception as e:
            conn.rollback(); print(f"runstats {tb}:", str(e)[:120])
    cur.execute(f"SELECT STATUS, COUNT(*) FROM {s}.V_DAY GROUP BY STATUS ORDER BY 1")
    print(f"audit done in {time.time()-t:.0f}s:", dict(cur.fetchall()))
    if not a.no_embed and s == "AQ":
        import requests, rules
        for _ in range(120):            # the Ollama container registers the Granite models after they download
            try:
                if any(m["name"].startswith(rules.EMBED_MODEL) for m in requests.get(rules.OLLAMA + "/api/tags", timeout=5).json()["models"]): break
            except Exception: pass
            time.sleep(5)
        rules.load_rules(os.path.join(ROOT, "data", "rules.json")); print("rule texts embedded")

def run_tolerant(conn, f, schema):
    """Run a script statement by statement, skipping objects that already exist (SQL0601N, SQL0624N trigger/key
    exists) or grants already held; used for SYSTOOLSPACE/AQ_TEMP and for migrations of a loaded schema."""
    sql = open(os.path.join(ROOT, "sql", f), encoding="utf-8").read()
    if schema: sql = re.sub(r"\bAQ\.", schema + ".", sql).replace("CREATE SCHEMA AQ@", f"CREATE SCHEMA {schema}@")
    cur, done = conn.cursor(), 0
    for stmt in sql.split("@"):
        body = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("--")).strip()
        if not body: continue
        try:
            cur.execute(body); conn.commit(); done += 1
        except Exception as e:
            conn.rollback()
            if not any(c in str(e) for c in ("SQL0601N", "SQL0624N", "SQL0554N", "SQL0612N", "SQL20490N", "SQL0605W")): raise
    return done

def migrate(conn, schema):
    """Bring a loaded schema up to the current SQL without touching its data: new column, triggers, indexes,
    views, procedures, grants. CREATE TABLE statements of existing tables are skipped as 'already exists'."""
    s = schema or "AQ"; cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM SYSCAT.COLUMNS WHERE TABSCHEMA = ? AND TABNAME = 'HOURLY' AND COLNAME = 'N_EXP'", (s,))
    if cur.fetchone()[0] == 0:
        cur.execute(f"ALTER TABLE {s}.HOURLY ADD COLUMN N_EXP SMALLINT NOT NULL DEFAULT 4"); conn.commit()
        cur.execute(f"CALL SYSPROC.ADMIN_CMD('REORG TABLE {s}.HOURLY')"); conn.commit()
    cur.execute(f"SELECT COUNT(*) FROM {s}.SETTING WHERE NAME = 'MIN_HOUR_CAPTURE'")
    if cur.fetchone()[0] == 0:
        cur.execute(f"UPDATE {s}.PLAUSIBLE SET MAX_V = CASE PARAM WHEN 'pm25' THEN 3000 ELSE 5000 END WHERE PARAM IN ('pm25', 'pm10')")
        cur.execute(f"DELETE FROM {s}.SETTING WHERE NAME = 'MIN_QUARTERS_PER_HOUR'")
        cur.execute(f"INSERT INTO {s}.SETTING VALUES ('MIN_HOUR_CAPTURE', 0.75, 'An hour is valid when at least 75% of the readings expected "
                    "that hour are plausible: 3 of 4 at 15-minute cadence; 1 of 1 when the station published hourly that day (one row an hour, "
                    "or 15-minute rows repeating one hourly value).')")
        conn.commit()
    n = sum(run_tolerant(conn, f, schema) for f in ("01_schema.sql", "04_audit.sql", "05_views.sql", "06_asklog.sql", "07_access.sql", "08_receipt.sql", "09_mqt_mask.sql"))
    print(f"schema {s}: migrations applied ({n} statements)")

if __name__ == "__main__":
    main()
