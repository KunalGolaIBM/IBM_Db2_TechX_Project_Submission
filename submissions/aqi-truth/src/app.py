"""AQI Truth web API (FastAPI). Serves the page in web/ and reads everything from Db2."""
import collections, datetime as dt, decimal, json, os, queue, re, sys, threading, time
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
sys.path.insert(0, os.path.dirname(__file__))
from db import connect_app, rows
import explain as ex, ask as asker, llm

WEB = os.path.join(os.path.dirname(__file__), "..", "web")
app = FastAPI(title="AQI Truth")
# The GitHub Pages copy of the UI may call a hosted API, so allow that origin (comma-separated list in ALLOWED_ORIGINS).
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("ALLOWED_ORIGINS", "https://debi910.github.io").split(","),
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
_local = threading.local()
def conn():
    # one Db2 connection per worker thread (FastAPI runs sync handlers in a thread pool)
    if getattr(_local, "c", None) is None: _local.c = connect_app()
    return _local.c

# Granite runs on CPU: one generation at a time, and a small per-visitor budget so a public demo stays usable.
LLM_LOCK = threading.Lock()
_hits = collections.defaultdict(collections.deque)
def throttle(request: Request, per_min=int(os.getenv("ASK_PER_MIN", "6"))):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    q, now = _hits[ip], time.time()
    while q and now - q[0] > 60: q.popleft()
    if len(q) >= per_min: raise HTTPException(429, "Too many questions from this address; try again in a minute.")
    q.append(now)

@app.get("/api/health")
def health():
    return dict(db2=rows(conn(), "SELECT COUNT(*) FROM AQ.V_DAY")[0][0] > 0, model=ex.MODEL)

PARAMS = ["pm25", "pm10", "no2", "so2", "o3", "co"]

@app.get("/api/stations")
def stations():
    return [dict(id=r[0], name=r[1], operator=r[2]) for r in rows(conn(),
        "SELECT STATION_ID, NAME, OPERATOR FROM AQ.STATION WHERE STATION_ID <> 8118 ORDER BY NAME")]

@app.get("/api/calendar")
def calendar():
    rs = rows(conn(), "SELECT STATION_ID, DAY, STATUS, AQI, NAIVE_AQI FROM AQ.V_DAY WHERE STATION_ID <> 8118 ORDER BY STATION_ID, DAY")
    return [dict(s=r[0], d=str(r[1]), st=r[2][0], a=r[3], n=r[4]) for r in rs]

@app.get("/api/stats")
def stats(start: str = "2025-09-01", end: str = "2025-12-31"):
    """Headline counts for one period (default: the Sep-Dec 2025 study period)."""
    a, b = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    r = rows(conn(), """SELECT COUNT(*), SUM(CASE WHEN STATUS='NOT_COMPUTABLE' THEN 1 ELSE 0 END),
        SUM(CASE WHEN STATUS='NOT_COMPUTABLE' AND NAIVE_AQI IS NOT NULL THEN 1 ELSE 0 END),
        SUM(CASE WHEN STATUS='NOT_COMPUTABLE' AND NAIVE_AQI > 300 THEN 1 ELSE 0 END),
        SUM(CASE WHEN STATUS='SUSPECT' THEN 1 ELSE 0 END),
        (SELECT COUNT(*) FROM AQ.READING WHERE STATION_ID <> 8118 AND PARAM IN ('pm25','pm10','no2','so2','o3','co')
            AND TS >= TIMESTAMP(CAST(? AS DATE)) AND TS < TIMESTAMP(CAST(? AS DATE)) + 1 DAY)
        FROM AQ.V_DAY WHERE DAY BETWEEN ? AND ?""", (a, b, a, b))[0]
    return dict(start=start, end=end, station_days=r[0], not_computable=r[1], shown_anyway=r[2], shown_anyway_very_poor=r[3],
                suspect=r[4], readings=r[5])

def day_payload(station: int, day: str, with_llm: bool):
    d = dt.date.fromisoformat(day)
    v = rows(conn(), "SELECT RUN_ID, STATION, OPERATOR, STATUS, AQI, NAIVE_AQI, PROMINENT, VALID_PARAMS, REASON FROM AQ.V_DAY WHERE STATION_ID=? AND DAY=?", (station, d))
    if not v: raise HTTPException(404, "no audit for that station and day")
    run, name, op, status, aqi, naive, prom, nparams, reason = v[0]
    ev = rows(conn(), """SELECT E.PARAM, E.CHECK_CODE, E.OBSERVED, E.PASSED, E.RULE_REF, R.SOURCE, R.URL
                          FROM AQ.EVIDENCE E LEFT JOIN AQ.RULE_TEXT R ON R.RULE_REF = E.RULE_REF
                         WHERE E.RUN_ID=? ORDER BY E.PASSED, E.PARAM, E.CHECK_CODE""", (run,))
    start = dt.datetime.combine(d, dt.time())
    hrs = rows(conn(), """SELECT PARAM, HOUR(HR - 1 SECOND), N_RAW, N_OK, AVG_OK, AVG_ALL, FLAT, JUMP, IS_VALID
                            FROM AQ.HOURLY WHERE STATION_ID=? AND HR > ? AND HR <= ?""", (station, start, start + dt.timedelta(days=1)))
    grid = {p: [None] * 24 for p in PARAMS}
    for p, h, nraw, nok, aok, aall, flat, jump, valid in hrs:
        if p in grid:
            grid[p][h] = dict(v=None if aok is None else round(aok, 1), raw=None if aall is None else round(aall, 1),
                              k="ok" if valid else ("stuck" if flat else ("bad" if nok == 0 else "short")), j=bool(jump))
    expl = rows(conn(), "SELECT TEXT, MODEL, RULE_REFS, VECTOR_AGREES FROM AQ.EXPLANATION WHERE RUN_ID=? ORDER BY CREATED_AT DESC FETCH FIRST 1 ROW ONLY", (run,))
    if not expl and with_llm:
        # Never make a visitor wait behind someone else's question: if Granite is busy, show the template now
        # (not stored) and let a later visit store Granite's explanation.
        if LLM_LOCK.acquire(blocking=False):
            try: e = ex.explain(conn(), run)
            finally: LLM_LOCK.release()
        else:
            e = ex.explain(conn(), run, use_llm=False, store=False)
        expl = [(e["text"], e["model"], ",".join(e["cited"]), int(e["vector_agrees"]))]
    return dict(run_id=run, station=name, operator=op, day=day, status=status, aqi=aqi, naive_aqi=naive, prominent=prom,
                valid_params=nparams, reason=reason, grid=grid,
                evidence=[dict(param=r[0], check=r[1], observed=r[2], passed=bool(r[3]), rule=r[4], source=r[5], url=r[6]) for r in ev],
                explanation=dict(text=expl[0][0], model=expl[0][1], rules=expl[0][2], vector_agrees=bool(expl[0][3])) if expl else None)

@app.get("/api/day")
def day(station: int, day: str, llm: bool = True):
    return day_payload(station, day, llm)

class Q(BaseModel):
    question: str
    fresh: bool = False      # true: always ask Granite, never reuse earlier SQL

def plain(v):
    if isinstance(v, decimal.Decimal): return float(v)
    if isinstance(v, (dt.date, dt.datetime)): return v.isoformat()
    return v

def norm(q):
    return re.sub(r"[\s?.!]+$", "", re.sub(r"\s+", " ", q.strip().lower()))[:300]

def log_ask(q, r, source, ms_model=None, ms_db2=None):
    try:
        c = conn(); c.cursor().execute(
            "INSERT INTO AQ.ASK_LOG (QUESTION, QNORM, SQL_TEXT, OUTCOME, SOURCE, MS_MODEL, MS_DB2, N_ROWS) VALUES (?,?,?,?,?,?,?,?)",
            (q[:300], norm(q), (r.get("sql") or "")[:4000] or None, r.get("outcome", "REFUSED"), source, ms_model, ms_db2,
             len(r["rows"]) if r.get("rows") is not None else None)); c.commit()
    except Exception as e:
        print("ask log failed:", str(e)[:160])

def earlier_sql(q):
    """SQL Granite wrote for this exact question before and that Db2 answered."""
    try:
        r = rows(conn(), """SELECT SQL_TEXT, ASKED_AT FROM AQ.ASK_LOG WHERE QNORM = ? AND OUTCOME = 'ANSWERED' AND SOURCE = 'GRANITE'
                            ORDER BY ID DESC FETCH FIRST 1 ROW ONLY""", (norm(q),))
        return (r[0][0], r[0][1]) if r else None
    except Exception:
        return None

def run_timed(sql):
    t = time.time(); r = asker.run(sql); ms = int((time.time() - t) * 1000)
    if r.get("rows") is not None: r["rows"] = [[plain(c) for c in row] for row in r["rows"]]
    return r, ms

def ask_events(question, fresh):
    """The question pipeline as a stream of events, so the page can show each stage as it happens."""
    yield {"e": "guard"}
    g = asker.guard(question)
    if g:
        log_ask(question, g, "GUARD"); yield {"e": "result", **g}; return
    prev = None if fresh else earlier_sql(question)
    if prev:
        sql, at = prev
        yield {"e": "reuse", "sql": sql, "at": plain(at)}
        yield {"e": "db2"}
        r, ms = run_timed(sql); log_ask(question, r, "REUSED", None, ms)
        yield {"e": "result", **r, "source": "reused", "reused_from": plain(at), "ms_db2": ms}; return
    # Granite runs in its own thread that holds the lock only while it generates. The lock is never held across a
    # yield, so a visitor who closes the tab mid-answer (or while queued) cannot leave the question box locked.
    pieces, gone = queue.Queue(), threading.Event()
    def produce():
        with LLM_LOCK:
            if gone.is_set(): pieces.put(None); return
            pieces.put({"e": "model"})
            try:
                for piece in llm.stream(asker.prompt(question), max_tokens=200, system=asker.SYSTEM, stop=asker.sql_done):
                    if gone.is_set(): break
                    pieces.put(piece)
            except Exception as e:
                pieces.put(e)
            finally:
                pieces.put(None)
    if LLM_LOCK.locked(): yield {"e": "queue"}
    threading.Thread(target=produce, daemon=True).start()
    info = {}
    try:
        while (piece := pieces.get()) is not None:
            if isinstance(piece, Exception): raise piece
            if isinstance(piece, dict) and piece.get("e") == "model": yield piece
            elif isinstance(piece, dict): info = piece
            else: yield {"e": "tok", "t": piece}
    finally:
        gone.set()
    sql = asker.extract(info.get("text", ""))
    yield {"e": "check", "sql": sql}
    yield {"e": "db2"}
    r, ms = run_timed(sql); log_ask(question, r, "GRANITE", info.get("ms_total"), ms)
    yield {"e": "result", **r, "source": "granite", "ms_model": info.get("ms_total"),
           "ms_first_token": info.get("ms_first_token"), "prompt_tokens": info.get("prompt_tokens"), "ms_db2": ms}

def check_question(q: Q, request: Request):
    if len(q.question) > 300: raise HTTPException(400, "question too long")
    if not q.question.strip(): raise HTTPException(400, "empty question")
    throttle(request)

@app.post("/api/ask/stream")
def ask_stream(q: Q, request: Request):
    check_question(q, request)
    def gen():
        try:
            for ev in ask_events(q.question, q.fresh):
                yield json.dumps(ev, default=str) + "\n"
        except Exception as e:
            yield json.dumps({"e": "result", "refused": True, "why": f"server error: {str(e)[:160]}"}) + "\n"
    # no-transform / X-Accel-Buffering: ask proxies in front of the app not to hold the stream back
    return StreamingResponse(gen(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})

@app.post("/api/ask")
def ask_q(q: Q, request: Request):
    check_question(q, request)
    out = {}
    for ev in ask_events(q.question, q.fresh): out = ev
    out.pop("e", None); return out

RECEIPT_COLS = ("result", "receipt_id", "run_id", "status", "aqi", "issued_at", "receipt_hash", "prev_hash", "input_hash",
                "n_readings", "n_now", "chain_ok", "history_ok", "data_same", "rules_same", "changed", "example")

def verify(station, d):
    r = rows(conn(), "SELECT * FROM TABLE(AQ.VERIFY_RECEIPT(?, ?)) X", (station, d))
    if not r: raise HTTPException(404, "no receipt for that station and day")
    return {k: plain(v) for k, v in zip(RECEIPT_COLS, r[0])}

@app.get("/api/receipt")
def receipt(station: int, day: str):
    """Db2 re-checks the day's receipt: hash chain, inputs replayed AS OF the issue time, current inputs, rules."""
    return verify(station, dt.date.fromisoformat(day))

TAMPER_LOCK = threading.Lock()
@app.post("/api/receipt/tamper")
def tamper(station: int, day: str, request: Request):
    """AQ.TAMPER_TEST: inside a savepoint, overwrite one input reading, verify, roll back, verify again."""
    throttle(request)
    d = dt.date.fromisoformat(day)
    with TAMPER_LOCK:
        t = time.time()
        out = conn().cursor().callproc("AQ.TAMPER_TEST", (station, d, "", "", "", ""))
        ms = int((time.time() - t) * 1000)
    touched, during, detail, after = out[2:]
    return dict(touched=touched, during=during, during_detail=detail, after=after, ms=ms, receipt=verify(station, d))

@app.get("/api/explain")
def explain_day(station: int, day: str):
    """Granite's two sentences for one station-day (stored once, then read from AQ.EXPLANATION)."""
    return day_payload(station, day, True)["explanation"]

@app.get("/api/asklog")
def asklog():
    """Recent questions and how they were answered: a public view of the append-only log."""
    rs = rows(conn(), """SELECT ASKED_AT, QUESTION, OUTCOME, SOURCE, MS_MODEL, MS_DB2, N_ROWS FROM AQ.ASK_LOG
                         ORDER BY ID DESC FETCH FIRST 20 ROWS ONLY""")
    return [dict(at=plain(r[0]), question=r[1], outcome=r[2], source=r[3], ms_model=r[4], ms_db2=r[5], rows=r[6]) for r in rs]

def prepare():
    """At startup: load Granite into memory and have Granite answer the sample questions once (logged like any
    visitor's), so their SQL can be reused instantly. Schema changes are the loader's job (src/load.py)."""
    for _ in range(120):
        try: llm.warm(); break
        except Exception: time.sleep(5)
    try:
        samples = [a["question"] for a in json.load(open(os.path.join(WEB, "data", "asks.json")))["answers"]]
    except Exception:
        samples = []
    for q in samples:
        if asker.guard(q) or earlier_sql(q): continue
        try:
            for _ in ask_events(q, True): pass
        except Exception as e:
            print("sample question failed:", q, str(e)[:120])
    print("startup ready: model warm, sample questions answered")

@app.on_event("startup")
def _startup():
    if os.getenv("WARM", "1") == "1": threading.Thread(target=prepare, daemon=True).start()

@app.get("/")
def index():
    return FileResponse(os.path.join(WEB, "index.html"))
app.mount("/", StaticFiles(directory=WEB), name="web")
