"""Read-only natural-language questions over the audited views.
Granite writes one SELECT; code checks it (sqlglot: single SELECT, only AQ.V_DAY / AQ.V_CHECK, row cap);
Db2 runs it as AQREADER, an authorization ID that can read those two views and nothing else."""
import os, re, sys
import sqlglot
from sqlglot import exp
sys.path.insert(0, os.path.dirname(__file__))
import ibm_db, ibm_db_dbi

ALLOWED = {"V_DAY", "V_CHECK"}
OUT_OF_SCOPE = re.compile(r"\b(predict\w*|forecast\w*|tomorrow|next week|will it|will the|should i|safe|unsafe|health\w*|child\w*|kids?|mask|fraud|who is responsible|responsible for)\b", re.I)
SCHEMA = """Db2 views (schema AQ):
AQ.V_DAY(STATION VARCHAR, OPERATOR VARCHAR, DAY DATE, STATUS VARCHAR -- 'VALID'|'SUSPECT'|'NOT_COMPUTABLE',
         AQI SMALLINT -- audited AQI, NULL when NOT_COMPUTABLE, NAIVE_AQI SMALLINT -- plain average, PROMINENT VARCHAR, VALID_PARAMS SMALLINT, REASON VARCHAR)
AQ.V_CHECK(STATION VARCHAR, DAY DATE, PARAM VARCHAR -- pm25|pm10|no2|so2|o3|co|ALL, CHECK_CODE VARCHAR -- COVERAGE|PLAUSIBLE|STUCK|JUMP|SUBINDEX|MIN_PARAMS,
           OBSERVED VARCHAR, PASSED SMALLINT -- 1 passed 0 failed, RULE_REF VARCHAR)
Station names look like 'Chandni Chowk, Delhi - IITM' (always match with LIKE '%Chandni Chowk%'). Data covers 2025-09-01 to 2025-12-31 and 2026-10-01 to 2026-11-05.
AQI is NULL on NOT_COMPUTABLE days: add AQI IS NOT NULL when ranking by AQI. A failed check has PASSED = 0."""
EXAMPLES = """Q: Which stations had the most days with no computable AQI?
SQL: SELECT STATION, COUNT(*) AS DAYS FROM AQ.V_DAY WHERE STATUS = 'NOT_COMPUTABLE' GROUP BY STATION ORDER BY DAYS DESC
Q: On Diwali 2025 (21 October) which stations were suspect?
SQL: SELECT STATION, AQI, NAIVE_AQI FROM AQ.V_DAY WHERE DAY = '2025-10-21' AND STATUS = 'SUSPECT'
Q: How many jump checks failed at Okhla in November?
SQL: SELECT COUNT(*) FROM AQ.V_CHECK WHERE STATION LIKE '%Okhla%' AND CHECK_CODE = 'JUMP' AND PASSED = 0 AND DAY BETWEEN '2025-11-01' AND '2025-11-30'"""
SYSTEM = "You translate questions into a single read-only Db2 SQL SELECT over the given views."

TIMEOUT_S = int(os.getenv("ASK_TIMEOUT_S", "10"))   # Db2 cancels a question-box query that runs longer than this
MAX_ROWS = 50

def reader():
    """A raw ibm_db connection as AQREADER (SELECT on AQ.V_DAY and AQ.V_CHECK only)."""
    from db import dsn
    return ibm_db.connect(dsn(os.getenv('DB2_READER_USER', 'aqreader'), os.environ['DB2_READER_PASSWORD']), "", "")

class Refused(Exception):
    pass

def check_sql(sql):
    sql = sql.strip().rstrip(";")
    # Models often write LIMIT n; Db2 uses FETCH FIRST n ROWS ONLY.
    sql = re.sub(r"\s+LIMIT\s+(\d+)\s*$", r" FETCH FIRST \1 ROWS ONLY", sql, flags=re.I)
    sql = re.sub(r"--[^\n]*", "", sql)
    # Db2 sorts NULL as the highest value; an AQI ranking must not put refused (NULL) days first.
    sql = re.sub(r"\b((?:\w+\.)?(?:NAIVE_)?AQI|MAX\(\s*(?:\w+\.)?AQI\s*\))\s+DESC\b(?!\s+NULLS)", r"\1 DESC NULLS LAST", sql, flags=re.I)
    # Users type short names ("ITO", "Punjabi Bagh"); stored names are longer, so exact matches become LIKE.
    sql = re.sub(r"\bSTATION\s*=\s*'([^',]+)[^']*'", lambda m: f"STATION LIKE '%{m.group(1).strip()}%'", sql, flags=re.I)
    try:
        trees = sqlglot.parse(re.sub(r"FETCH\s+FIRST\s+\d+\s+ROWS\s+ONLY", "", sql, flags=re.I))
    except Exception as e:
        raise Refused(f"could not parse the generated SQL ({e.__class__.__name__})")
    if len(trees) != 1 or not isinstance(trees[0], exp.Select):
        raise Refused("only a single SELECT is allowed")
    tables = {t.name.upper() for t in trees[0].find_all(exp.Table)}
    if not tables or not tables <= ALLOWED or any((t.db or "").upper() not in ("AQ", "") for t in trees[0].find_all(exp.Table)):
        raise Refused(f"query touches tables outside the audited views: {sorted(tables - ALLOWED) or sorted(tables)}")
    for j in trees[0].find_all(exp.Join):
        if not (j.args.get("on") or j.args.get("using")):
            raise Refused("a join without a join condition (cross join) is not allowed")
    if len(list(trees[0].find_all(exp.Table))) > 3:
        raise Refused("at most three view references are allowed")
    # Row cap: add one, or clamp a larger one, to MAX_ROWS.
    sql = re.sub(r"FETCH\s+FIRST\s+(\d+)\s+ROWS?\s+ONLY", lambda m: f"FETCH FIRST {min(int(m.group(1)), MAX_ROWS)} ROWS ONLY", sql, flags=re.I)
    if not re.search(r"FETCH\s+FIRST", sql, re.I):
        sql += f" FETCH FIRST {MAX_ROWS} ROWS ONLY"
    return sql

TEMPLATE = "{schema}\n\n{examples}\n\nWrite one Db2 SELECT for the question. Reply with SQL only, no explanation.\nQ: {question}\nSQL:"

def prompt(question):
    return TEMPLATE.format(schema=SCHEMA, examples=EXAMPLES, question=question)

def guard(question):
    """Refuse forecasts, health advice and blame before any model call."""
    if OUT_OF_SCOPE.search(question):
        return dict(refused=True, why="AQI Truth only answers questions about what the monitors recorded and how the audit judged it. "
                                      "It does not predict air quality or give health advice.")

def extract(raw):
    sql = re.sub(r"^```\w*|```$", "", raw.strip(), flags=re.M).strip().split("\n\n")[0]
    return re.sub(r"^SQL:\s*", "", sql)

def sql_done(text):
    """Granite has finished its one statement: stop generating instead of paying for trailing tokens."""
    t = text.strip()
    return t.endswith(";") or "\n\n" in t.lstrip("`\n") or bool(re.search(r"FETCH\s+FIRST\s+\d+\s+ROWS?\s+ONLY\s*$", t, re.I))

def run(sql, conn=None):
    """Check the SQL and run it as AQREADER. Returns the answer dict."""
    try:
        sql = check_sql(sql)
    except Refused as e:
        return dict(refused=True, why=f"The generated query was blocked: {e}.", sql=sql, outcome="BLOCKED")
    own = conn is None
    h = reader() if own else getattr(conn, "conn_handler", conn)
    try:
        # SQL_ATTR_QUERY_TIMEOUT: the Db2 client cancels the statement after TIMEOUT_S seconds (SQL0952N).
        st = ibm_db.prepare(h, sql, {ibm_db.SQL_ATTR_QUERY_TIMEOUT: TIMEOUT_S})
        ibm_db.execute(st)
        cols = [ibm_db.field_name(st, i) for i in range(ibm_db.num_fields(st))]
        data, r = [], ibm_db.fetch_tuple(st)
        while r:
            data.append(list(r)); r = ibm_db.fetch_tuple(st)
    except Exception as e:
        msg = str(e) + " " + (ibm_db.stmt_errormsg() or "")
        why = (f"Db2 cancelled the query after {TIMEOUT_S} s." if "SQL0952N" in msg or "timeout" in msg.lower()
               else f"Db2 rejected the query: {msg.strip()[-160:]}")
        return dict(refused=True, why=why, sql=sql, outcome="DB2_ERROR")
    finally:
        if own: ibm_db.close(h)
    return dict(refused=False, sql=sql, columns=cols, rows=data, outcome="ANSWERED")

def ask(question, conn=None, model=None):
    """Guard, then the LangChain chain in chain.py (prompt template -> Granite -> parser -> SQL checks -> Db2 as AQREADER)."""
    g = guard(question)
    if g: return g
    from chain import answer_chain
    return answer_chain(conn, model).invoke({"question": question})

if __name__ == "__main__":
    print(ask(" ".join(sys.argv[1:])))
