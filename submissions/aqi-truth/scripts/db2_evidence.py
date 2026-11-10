"""One command that proves the Db2 claims against the live database and writes docs/DB2_VERIFICATION.md.
Usage: python scripts/db2_evidence.py [--out docs/DB2_VERIFICATION.md]
Every check runs real SQL and records what Db2 answered. Exits non-zero if any check fails.
Nothing here changes the audit data: write attempts are expected to fail, and anything that could succeed is rolled
back. The temporal check works on a throwaway schema (AQV) built from the same sql/01_schema.sql, then dropped."""
import argparse, datetime as dt, os, platform, re, sys, time
import ibm_db
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from db import connect, connect_app, run_script, rows
import ask

results = []

def check(name, claim, sql, run, expect):
    """run() returns the observed text; expect(observed) says whether it backs the claim."""
    try:
        obs = run()
    except Exception as e:
        obs = f"error: {err(e)}"
    ok = bool(expect(obs))
    results.append((name, claim, sql.strip(), obs, ok))
    print(("PASS " if ok else "FAIL ") + name + ": " + obs[:150])

def err(e):
    m = re.search(r"(SQL\d{4,5}[NWC]).*?SQLSTATE=(\w{5})", str(e), re.S)
    return f"{m.group(1)} SQLSTATE={m.group(2)}" if m else str(e)[-200:]

def attempt(conn, sql, params=()):
    """Run a statement that should be refused; roll back whatever happens. Returns 'ok' or the Db2 error."""
    cur = conn.cursor()
    try:
        cur.execute(sql, params); return "statement succeeded (rolled back)"
    except Exception as e:
        return err(e)
    finally:
        conn.rollback()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=os.path.join(ROOT, "docs", "DB2_VERIFICATION.md"))
    a = ap.parse_args()
    own = connect(autocommit=False)
    app = connect_app(); app.set_autocommit(False)
    rd = ask.reader(); ibm_db.autocommit(rd, ibm_db.SQL_AUTOCOMMIT_OFF)
    level = rows(own, "SELECT SERVICE_LEVEL FROM TABLE(SYSPROC.ENV_GET_INST_INFO()) X")[0][0]
    users = dict(owner=rows(own, "VALUES SESSION_USER")[0][0], app=rows(app, "VALUES SESSION_USER")[0][0].strip())

    # 1. System-period temporal: an update keeps the old version, and FOR SYSTEM_TIME AS OF returns it.
    def temporal():
        cur = own.cursor()
        if rows(own, "SELECT COUNT(*) FROM SYSCAT.SCHEMATA WHERE SCHEMANAME = 'AQV'")[0][0]:
            cur.callproc("SYSPROC.ADMIN_DROP_SCHEMA", ("AQV", None, "ERRSCHEMA", "ERRTABLE")); own.commit()
        run_script(own, os.path.join(ROOT, "sql", "01_schema.sql"), schema="AQV")
        cur.execute("INSERT INTO AQV.READING (STATION_ID, PARAM, TS, VALUE) VALUES (1, 'pm25', '2025-10-21 22:00:00', 210)"); own.commit()
        t1 = rows(own, "VALUES CURRENT TIMESTAMP")[0][0]; time.sleep(1.1)
        cur.execute("UPDATE AQV.READING SET VALUE = 999 WHERE STATION_ID = 1"); own.commit()
        now = rows(own, "SELECT VALUE FROM AQV.READING WHERE STATION_ID = 1")[0][0]
        then = rows(own, "SELECT VALUE FROM AQV.READING FOR SYSTEM_TIME AS OF ? WHERE STATION_ID = 1", (t1,))[0][0]
        hist = rows(own, "SELECT COUNT(*) FROM AQV.READING_HIST")[0][0]
        cur.callproc("SYSPROC.ADMIN_DROP_SCHEMA", ("AQV", None, "ERRSCHEMA", "ERRTABLE")); own.commit()
        return f"current value {now:g}; AS OF before the update {then:g}; {hist} row in READING_HIST"
    check("Temporal AS OF", "Revising a reading keeps the old version, and FOR SYSTEM_TIME AS OF returns it.",
          """INSERT ... VALUE = 210; COMMIT; UPDATE ... SET VALUE = 999; COMMIT;
SELECT VALUE FROM AQV.READING FOR SYSTEM_TIME AS OF <time before the update> WHERE STATION_ID = 1""",
          temporal, lambda o: "AS OF before the update 210" in o and "current value 999" in o)
    check("Live revision history", "The live READING table is versioned; READING_HIST holds every revised published value.",
          "SELECT COUNT(*) FROM AQ.READING_HIST; SELECT COUNT(*) FROM AQ.V_REVISION",
          lambda: "%s earlier versions; versioning: %s" % (
              rows(own, "SELECT COUNT(*) FROM AQ.READING_HIST")[0][0],
              "on" if rows(own, "SELECT COUNT(*) FROM SYSCAT.PERIODS WHERE TABSCHEMA = 'AQ' AND TABNAME = 'READING' AND HISTORYTABNAME = 'READING_HIST'")[0][0] else "off"),
          lambda o: "versioning: on" in o)

    # 2. Append-only ledgers: SQL PL triggers SIGNAL SQLSTATE 75001 even for the schema owner.
    run1 = rows(own, "SELECT MIN(RUN_ID) FROM AQ.EVIDENCE")[0][0]
    for tbl, sql in (("EVIDENCE", f"UPDATE AQ.EVIDENCE SET PASSED = 1 - PASSED WHERE RUN_ID = {run1}"),
                     ("EVIDENCE", f"DELETE FROM AQ.EVIDENCE WHERE RUN_ID = {run1}"),
                     ("VERDICT", f"UPDATE AQ.VERDICT SET AQI = 1 WHERE RUN_ID = {run1}"),
                     ("VERDICT", f"DELETE FROM AQ.VERDICT WHERE RUN_ID = {run1}")):
        check(f"Trigger blocks {sql.split()[0]} on {tbl} (owner)", f"Even the schema owner cannot rewrite {tbl}.", sql,
              lambda sql=sql: attempt(own, sql), lambda o: "SQLSTATE=75001" in o)

    # 3. Least privilege. The question box (AQREADER) and the web app (AQAPP) are separate Db2 IDs.
    for sql in ("INSERT INTO AQ.ASK_LOG (QUESTION, QNORM, OUTCOME, SOURCE) VALUES ('x', 'x', 'ANSWERED', 'GUARD')",
                "DELETE FROM AQ.VERDICT", "SELECT COUNT(*) FROM AQ.READING"):
        def as_reader(sql=sql):
            try:
                st = ibm_db.exec_immediate(rd, sql); return "statement succeeded"
            except Exception:
                return err(ibm_db.stmt_errormsg())
            finally:
                ibm_db.rollback(rd)
        target = re.search(r"AQ\.\w+", sql).group(0)
        check(f"AQREADER refused: {sql.split()[0]} {target}",
              "The question box's ID can only SELECT from AQ.V_DAY and AQ.V_CHECK.", sql, as_reader, lambda o: "42501" in o)
    check("AQAPP may append to the question log", "The web app's ID can INSERT into ASK_LOG (rolled back here).",
          "INSERT INTO AQ.ASK_LOG (QUESTION, QNORM, OUTCOME, SOURCE) VALUES (...)",
          lambda: attempt(app, "INSERT INTO AQ.ASK_LOG (QUESTION, QNORM, OUTCOME, SOURCE) VALUES ('evidence', 'evidence', 'ANSWERED', 'GUARD')"),
          lambda o: o.startswith("statement succeeded"))
    for sql in ("DELETE FROM AQ.ASK_LOG", "UPDATE AQ.EXPLANATION SET GROUNDED = 1", "TRUNCATE TABLE AQ.EVIDENCE IMMEDIATE",
                "TRUNCATE TABLE AQ.RECEIPT IMMEDIATE", "TRUNCATE TABLE AQ.ASK_LOG IMMEDIATE", "INSERT INTO AQ.VERDICT (STATION_ID, DAY, STATUS, VALID_PARAMS, REASON, DATA_AS_OF) VALUES (1, CURRENT DATE, 'VALID', 3, 'x', CURRENT TIMESTAMP)"):
        check(f"AQAPP refused: {' '.join(sql.split()[:3])}", "The web app's ID cannot delete, rewrite or truncate (TRUNCATE skips triggers, so this is the privilege that stops it).",
              sql, lambda sql=sql: attempt(app, sql), lambda o: "42501" in o or "SQLSTATE=75001" in o)

    # 4. Row access control: the same SELECT returns different rows for different IDs.
    q = "SELECT COUNT(*) FROM AQ.VERDICT WHERE STATION_ID = 8118"
    check("RCAC row permission", "Db2 hides out-of-scope verdict rows (US Embassy monitor) from every ID without the AQAUDITOR role.",
          q + "   -- as the owner (AQAUDITOR) and as AQAPP",
          lambda: f"owner sees {rows(own, q)[0][0]} rows; AQAPP sees {rows(app, q)[0][0]} rows",
          lambda o: re.match(r"owner sees ([1-9]\d*) rows; AQAPP sees 0 rows", o))

    # 5. The question box cannot run away: Db2's query timeout cancels a heavy statement.
    heavy = "SELECT COUNT(*) FROM AQ.V_CHECK A JOIN AQ.V_CHECK B ON A.PARAM = B.PARAM"
    def timeout():
        old = ask.TIMEOUT_S; ask.TIMEOUT_S = 2
        try:
            t = time.time(); r = ask.run(heavy); return f"{r.get('why') or r.get('rows')} ({time.time() - t:.1f} s)"
        finally:
            ask.TIMEOUT_S = old
    check("Query timeout", "A question-box query is cancelled by Db2 after the timeout (SQL_ATTR_QUERY_TIMEOUT).",
          heavy + "   -- run as AQREADER with a 2 s timeout", timeout, lambda o: "cancelled" in o)
    check("Cross join refused before Db2", "The SQL checker refuses a join without a join condition.",
          "SELECT * FROM AQ.V_DAY, AQ.V_CHECK", lambda: ask.run("SELECT * FROM AQ.V_DAY, AQ.V_CHECK", conn=rd).get("why", "ran"),
          lambda o: "cross join" in o)

    # 6. Verifiable receipts: every verdict has a SHA-256 receipt chained to the one before; a changed input is caught.
    check("Receipt chain", "Every receipt recomputes from its fields and links to the receipt before it.",
          "SELECT RECEIPTS, BROKEN FROM AQ.V_RECEIPT_CHAIN",
          lambda: "%s receipts, %s broken" % tuple(rows(own, "SELECT RECEIPTS, BROKEN FROM AQ.V_RECEIPT_CHAIN")[0]),
          lambda o: o.endswith(", 0 broken") and not o.startswith("0 "))
    check("Receipt verifies", "The receipt of Chandni Chowk, 23 Oct 2025 matches: chain, history AS OF issue time, current data, rules.",
          "SELECT RESULT, CHAIN_OK, HISTORY_OK, DATA_SAME, RULES_SAME FROM TABLE(AQ.VERIFY_RECEIPT(11603, '2025-10-23'))",
          lambda: " ".join(str(x) for x in rows(app, "SELECT RESULT, CHAIN_OK, HISTORY_OK, DATA_SAME, RULES_SAME FROM TABLE(AQ.VERIFY_RECEIPT(11603, '2025-10-23')) X")[0]),
          lambda o: o == "MATCH 1 1 1 1")
    def tamper():
        out = app.cursor().callproc("AQ.TAMPER_TEST", (11603, dt.date(2025, 10, 23), "", "", "", "")); app.commit()
        return "touched %s; during: %s (%s); after rollback: %s" % tuple(out[2:])
    check("Tampering is caught", "Overwriting one input reading makes the receipt report DATA_CHANGED with the old value from history; rolled back, it matches again.",
          "CALL AQ.TAMPER_TEST(11603, '2025-10-23', ?, ?, ?, ?)   -- as AQAPP; savepoint, UPDATE x10, verify, rollback, verify",
          tamper, lambda o: "during: DATA_CHANGED" in o and "from history" in o and o.endswith("after rollback: MATCH"))
    check("Receipts are append-only", "Even the owner cannot edit a receipt.",
          "UPDATE AQ.RECEIPT SET AQI = 1 WHERE RECEIPT_ID = <first>",
          lambda: attempt(own, "UPDATE AQ.RECEIPT SET AQI = 1 WHERE RECEIPT_ID = (SELECT MIN(RECEIPT_ID) FROM AQ.RECEIPT)"),
          lambda o: "SQLSTATE=75001" in o)

    # 7. Range partitioning: a one-day query reads one monthly data partition.
    def plan():
        cur = own.cursor()
        try:
            cur.execute("CALL SYSPROC.SYSINSTALLOBJECTS('EXPLAIN', 'C', NULL, CURRENT SCHEMA)"); own.commit()
        except Exception:
            own.rollback()     # explain tables already there
        cur.execute("DELETE FROM EXPLAIN_INSTANCE"); own.commit()
        cur.execute("EXPLAIN PLAN FOR SELECT AVG(VALUE) FROM AQ.READING WHERE TS >= '2025-10-21 00:00:00' AND TS < '2025-10-22 00:00:00'"); own.commit()
        arg = dict(rows(own, "SELECT RTRIM(ARGUMENT_TYPE), RTRIM(ARGUMENT_VALUE) FROM EXPLAIN_ARGUMENT WHERE ARGUMENT_TYPE IN ('DPNUMPRT', 'DPLSTPRT')"))
        total = rows(own, "SELECT COUNT(*) FROM SYSCAT.DATAPARTITIONS WHERE TABSCHEMA = 'AQ' AND TABNAME = 'READING'")[0][0]
        own.commit()
        return f"partitions accessed: {arg.get('DPNUMPRT', '?')} of {total} (list {arg.get('DPLSTPRT', '?')})"
    check("Partition elimination", "AQ.READING is range-partitioned by month; the optimizer reads only the partition a query needs.",
          "EXPLAIN PLAN FOR SELECT AVG(VALUE) FROM AQ.READING WHERE TS >= '2025-10-21' AND TS < '2025-10-22'",
          plan, lambda o: o.startswith("partitions accessed: 1 of"))
    # 8. Materialized query table: the optimizer rewrites a query on AQ.READING to the summary table.
    mq = "SELECT STATION_ID, DATE(TS) AS DAY, COUNT(*) FROM AQ.READING GROUP BY STATION_ID, DATE(TS)"
    def mqt():
        cur = own.cursor(); seen = {}
        for age in ("ANY", "0"):    # ANY lets the optimizer use the deferred MQT; 0 forbids it (the baseline)
            cur.execute(f"SET CURRENT REFRESH AGE {age}"); cur.execute("DELETE FROM EXPLAIN_INSTANCE"); own.commit()
            cur.execute("EXPLAIN PLAN FOR " + mq); own.commit()
            tabs = sorted({r[0].strip() for r in rows(own, "SELECT OBJECT_NAME FROM EXPLAIN_STREAM WHERE OBJECT_SCHEMA = 'AQ' AND OBJECT_NAME IS NOT NULL")})
            cost = rows(own, "SELECT TOTAL_COST FROM EXPLAIN_OPERATOR WHERE OPERATOR_TYPE = 'RETURN'")[0][0]
            seen[age] = (", ".join(tabs), round(cost))
        cur.execute("SET CURRENT REFRESH AGE 0"); own.commit()
        refreshed = rows(own, "SELECT REFRESH_TIME FROM SYSCAT.TABLES WHERE TABSCHEMA = 'AQ' AND TABNAME = 'MQT_READING_DAY'")[0][0]
        return (f"with REFRESH AGE ANY the plan reads {seen['ANY'][0]} (cost {seen['ANY'][1]:,} timerons); "
                f"with REFRESH AGE 0 it reads {seen['0'][0]} (cost {seen['0'][1]:,}). MQT refreshed {refreshed}")
    check("MQT query rewrite", "A REFRESH DEFERRED materialized query table of readings per station-pollutant-day. A query written against "
          "AQ.READING is rewritten by the optimizer to read the small MQT instead, when CURRENT REFRESH AGE ANY allows it.",
          "EXPLAIN PLAN FOR " + mq + "   -- once with CURRENT REFRESH AGE ANY, once with 0", mqt,
          lambda o: o.startswith("with REFRESH AGE ANY the plan reads MQT_READING_DAY (") and "with REFRESH AGE 0 it reads READING (" in o)

    # 9. Column mask: the same SELECT shows a visitor's e-mail and phone number only to the auditor.
    probe = "Email me at someone" + chr(64) + "example.com or call 9876543210: is ITO severe?"
    def masked(conn):
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO AQ.ASK_LOG (QUESTION, QNORM, OUTCOME, SOURCE) VALUES (?, 'evidence-probe', 'REFUSED', 'GUARD')", (probe,))
            cur.execute("SELECT QUESTION FROM AQ.ASK_LOG WHERE QNORM = 'evidence-probe' ORDER BY ID DESC FETCH FIRST 1 ROW ONLY")
            return cur.fetchone()[0]
        finally:
            conn.rollback()
    check("Column mask", "Db2 redacts e-mail addresses and phone numbers that visitors type into the question box, in AQ.ASK_LOG.QUESTION, "
          "for every ID without the AQAUDITOR role. The stored text is unchanged.",
          "SELECT QUESTION FROM AQ.ASK_LOG ...   -- the same row read as AQAPP and as the owner (inserted, then rolled back)",
          lambda: f"AQAPP sees: {masked(app)} | owner sees: {masked(own)}",
          lambda o: "AQAPP sees: Email me at [e-mail removed] or call [number removed]" in o and ("owner sees: " + probe) in o)

    check("Optimizer statistics", "The loader runs RUNSTATS through SYSPROC.ADMIN_CMD after each load.",
          "SELECT TABNAME, STATS_TIME, CARD FROM SYSCAT.TABLES WHERE TABSCHEMA = 'AQ' AND TABNAME IN ('READING', 'VERDICT')",
          lambda: "; ".join(f"{t.strip()}: {c} rows, stats {s}" for t, s, c in rows(own, "SELECT TABNAME, STATS_TIME, CARD FROM SYSCAT.TABLES WHERE TABSCHEMA = 'AQ' AND TABNAME IN ('READING', 'VERDICT') ORDER BY 1")),
          lambda o: "stats None" not in o and o.count("stats") == 2)

    failed = [r for r in results if not r[4]]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out = [f"# Db2 verification\n",
           f"Generated by `python scripts/db2_evidence.py` on {stamp} against {level.strip()} "
           f"(owner `{users['owner']}`, app `{users['app']}`, reader `{os.getenv('DB2_READER_USER', 'aqreader').upper()}`). "
           f"Host `{os.getenv('CODESPACE_NAME') or platform.node()}`. "
           f"**{len(results) - len(failed)} of {len(results)} checks passed.** Each row is real SQL and what Db2 answered; "
           "write attempts were rolled back or refused.\n",
           "| # | Check | Claim | Result | What Db2 answered |", "|---|---|---|---|---|"]
    for i, (name, claim, sql, obs, ok) in enumerate(results, 1):
        out.append(f"| {i} | {name} | {claim} | {'PASS' if ok else '**FAIL**'} | {obs.replace('|', '/')} |")
    out.append("\n## SQL run\n")
    for i, (name, _, sql, _, _) in enumerate(results, 1):
        out.append(f"{i}. **{name}**\n\n```sql\n{sql}\n```\n")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w", encoding="utf-8").write("\n".join(out))
    print(f"wrote {a.out}: {len(results) - len(failed)}/{len(results)} passed")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
