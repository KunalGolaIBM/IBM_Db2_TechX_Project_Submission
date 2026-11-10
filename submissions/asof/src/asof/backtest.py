"""Backtest mode: check a file of past answers in batch, and report what their mistakes put at stake.

    question,draft,customer_date,channel[,doc_id]       # the CSV: UTF-8, a header row, at most 500 rows
    python -m asof.backtest run answers.csv             # check a file (doc_id auto: Db2's routing vote per row)
    python -m asof.backtest sample                      # the shipped sample, which replay mode can check
    python -m asof.backtest report 3                    # the exposure report of run 3

Every row goes through the normal check (asof/checkgraph.py) for its customer's date and lands in the hash-chained
ledger through APPEND_LEDGER, on channel 'backtest', with the run, the row and the conversation's own channel hashed
into its verdicts. Db2 then records the row's outcome, which ADD_BACKTEST_ITEM derives from that ledger row (not from
this code), and for every contradicted claim the money difference, which ADD_BACKTEST_COST reads out of the cited
clause version's RULE_JSON with JSON_VALUE (sql/11_backtest.sql). The exposure report is SQL over those tables.

How the money is computed, and where it is not: a contradicted claim that states exactly one dollar amount, cited
against a clause version that sets exactly one dollar amount, gets the difference between the two (stated minus
policy), for one occurrence. Everything else (eligibility, deadlines, weight limits, two amounts on either side) is
recorded as not computable, with the reason. It is the gap between what the answer said and what the policy said,
not a liability estimate: the data does not say how many bags, days or trips were involved, or what was paid.

A run has a row cap (500, enforced by Db2 too), a deadline after which no row starts, and fails closed one row at a
time: a row whose check fails is recorded FAILED and the run goes on; rows left when the deadline passes, or when the
before-check hook stops the run, are recorded SKIPPED. A run never ends without an outcome for every row (FINISH_BACKTEST
refuses), unless the runner itself could not go on (FAILED).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import logging
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import ibm_db_dbi

from . import db
from .domains import DOC_IDS
from .gate import NOT_A_PRICE, ClaimOutcome, Gate, GateRequest, GateResult
from .rules import _close as same_amount
from .rules import extract_quantities, rule_params

log = logging.getLogger(__name__)

CHANNEL = "backtest"  # the ledger channel of every backtest decision (CK_LEDGER_CHANNEL)
MAX_CSV_BYTES = 2 * 1024 * 1024
HARD_MAX_ROWS = 500  # CK_BACKTEST_RUN_ROWS holds Db2 to the same cap
MIN_DATE, MAX_DATE = date(2020, 1, 1), date(2035, 12, 31)  # the range the API accepts for a customer's date
REQUIRED = ("question", "draft", "customer_date", "channel")
OPTIONAL = ("doc_id",)
CHANNELS = ("chat", "email", "faq", "api")  # CK_BACKTEST_ITEM_CHANNEL
DOC_CHOICES = (*DOC_IDS, "auto")
LIMITS = {"question": 2000, "draft": 4000}  # UTF-8 bytes, as the ledger's VARCHAR columns count them
MAX_ERRORS = 50
MAX_STATED_USD = Decimal("1000000")
SAMPLE_CSV = Path(__file__).with_name("data") / "samples" / "fictional-backtest-sample.csv"  # every row is made up
SAMPLE_NAME = SAMPLE_CSV.name
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
OUTCOMES = ("WRONG", "UNCONFIRMED", "OK", "FAILED", "SKIPPED")

# Why a contradicted claim has no money difference (BACKTEST_COST.NOTE).
NO_AMOUNT = "the claim states no dollar amount: it is about eligibility, a deadline, a limit or a procedure"
ONLY_LIMIT = "the claim states a dollar limit, not an amount charged or paid"
CLAUSE_NO_AMOUNT = "the clause version sets no dollar amount: its rule is a permission, a deadline or a limit"
AMBIGUOUS = "more than one dollar amount in the claim or the clause: no single pair to compare"
SAME_AMOUNT = "the dollar amount agrees with the clause: what is wrong is something else in the claim"
OUT_OF_RANGE = "the stated amount is outside 0 to 1,000,000 dollars"
ONE_OCCURRENCE = "one occurrence: the data does not say how many bags, days, trips or items"
COST_METHOD = ("For each contradicted claim that states exactly one dollar amount, against a clause version that sets "
               "exactly one, Db2 reads the clause's amount from its RULE_JSON (JSON_VALUE) and records stated minus "
               "policy, for one occurrence. In the customer's favour: a lower fee or a larger payment than the policy "
               "(what the company could be held to, as in Moffatt). Against the customer: told to pay more or expect "
               "less. Eligibility, deadlines and limits have no amount in the data, so they are counted, not priced. "
               "This is the gap between what was said and what the policy said, not a liability estimate.")


class CsvError(ValueError):
    """An upload that cannot be run, with every problem found (up to MAX_ERRORS)."""

    def __init__(self, errors: list[dict[str, Any]], total: int | None = None):
        self.errors, self.total = errors, total if total is not None else len(errors)
        first = errors[0]
        where = f"row {first['row']}: " if first.get("row") else ""
        more = f" (and {self.total - 1} more)" if self.total > 1 else ""
        super().__init__(f"{where}{first['message']}{more}")


@dataclass(frozen=True)
class Row:
    row_no: int
    line: int
    question: str
    draft: str
    customer_date: date
    channel: str
    doc_id: str | None  # None: the run's document


@dataclass(frozen=True)
class Upload:
    name: str
    sha256: str
    rows: list[Row]


def safe_name(name: str | None) -> str:
    """A display name for the file: its base name, plain characters only, ending in .csv."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base).strip(" ._")[:120]
    return base if base.lower().endswith(".csv") else (base or "backtest") + ".csv"


def _problem(row: int | None, line: int | None, column: str | None, message: str) -> dict[str, Any]:
    return {"row": row, "line": line, "column": column, "message": message}


def _field(name: str, value: str) -> tuple[Any, str | None]:
    """A cell's value, or None and the reason it is refused."""
    value = value.strip()
    if name in LIMITS:
        if not value:
            return None, "is empty"
        if _CONTROL.search(value):
            return None, "contains control characters"
        if len(value.encode("utf-8")) > LIMITS[name]:
            return None, f"is longer than {LIMITS[name]} bytes in UTF-8"
        return value, None
    if name == "customer_date":
        if not _ISO_DATE.match(value):
            return None, f"must be an ISO date (YYYY-MM-DD), not {value[:20]!r}"
        try:
            day = date.fromisoformat(value)
        except ValueError:
            return None, f"{value!r} is not a calendar date"
        if not MIN_DATE <= day <= MAX_DATE:
            return None, f"must be between {MIN_DATE} and {MAX_DATE}"
        return day, None
    if name == "channel":
        low = value.lower()
        return (low, None) if low in CHANNELS else (None, f"must be one of {', '.join(CHANNELS)}, not {value[:20]!r}")
    # doc_id: optional; empty means the run's document
    if not value:
        return None, None
    return (value, None) if value in DOC_CHOICES else (None, f"must be empty or one of {', '.join(DOC_CHOICES)}")


def parse_csv(data: bytes, name: str | None = None, max_rows: int = HARD_MAX_ROWS) -> Upload:
    """The rows of an uploaded CSV, or CsvError listing what is wrong. Nothing runs unless every row is valid."""
    max_rows = min(max_rows, HARD_MAX_ROWS)
    if not data:
        raise CsvError([_problem(None, None, None, "the file is empty")])
    if len(data) > MAX_CSV_BYTES:
        raise CsvError([_problem(None, None, None, f"the file is larger than {MAX_CSV_BYTES // (1024 * 1024)} MB")])
    if b"\x00" in data:
        raise CsvError([_problem(None, None, None, "the file contains NUL bytes: it is not a text CSV")])
    try:
        text = data.decode("utf-8-sig")  # strict; a leading byte-order mark is dropped
    except UnicodeDecodeError as exc:
        raise CsvError([_problem(None, None, None, f"the file is not UTF-8 text (invalid byte at offset {exc.start})")]) \
            from None
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    errors: list[dict[str, Any]] = []
    rows: list[Row] = []
    try:
        header = next(reader, None)
        if header is None:
            raise CsvError([_problem(None, None, None, "the file is empty")])
        names = [h.strip().lower() for h in header]
        unknown = [n for n in names if n not in REQUIRED + OPTIONAL]
        missing = [n for n in REQUIRED if n not in names]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if unknown or missing or dupes:
            parts = ([f"missing column(s) {', '.join(missing)}"] if missing else []) + \
                    ([f"unknown column(s) {', '.join(repr(u[:30]) for u in unknown)}"] if unknown else []) + \
                    ([f"repeated column(s) {', '.join(dupes)}"] if dupes else [])
            raise CsvError([_problem(None, 1, None, "header: " + "; ".join(parts) + f". Expected {','.join(REQUIRED)}"
                                                    " and optionally doc_id")])
        count = 0
        for record in reader:
            if not any(cell.strip() for cell in record):  # a blank line is not a row
                continue
            count += 1
            if count > max_rows:
                raise CsvError([_problem(None, None, None, f"more than {max_rows} rows: a backtest run holds at most "
                                                           f"{max_rows}; split the file")])
            line = reader.line_num
            if len(record) != len(names):
                errors.append(_problem(count, line, None, f"has {len(record)} fields; the header has {len(names)}"))
                continue
            values: dict[str, Any] = {}
            for col, cell in zip(names, record, strict=True):
                value, why = _field(col, cell)
                if why:
                    errors.append(_problem(count, line, col, f"{col} {why}"))
                values[col] = value
            rows.append(Row(count, line, values.get("question") or "", values.get("draft") or "",
                            values.get("customer_date") or MIN_DATE, values.get("channel") or "", values.get("doc_id")))
    except csv.Error as exc:
        errors.append(_problem(None, reader.line_num, None, f"the file is not valid CSV: {exc}"))
    if errors:
        raise CsvError(errors[:MAX_ERRORS], len(errors))
    if not rows:
        raise CsvError([_problem(None, None, None, "the file has a header but no rows")])
    return Upload(safe_name(name), hashlib.sha256(data).hexdigest(), rows)


# ---------- money ----------
@dataclass(frozen=True)
class Money:
    claim_no: int
    rule_key: str | None  # None: not computable, `note` says why
    stated_usd: Decimal | None
    note: str


def money_of(claim: ClaimOutcome) -> Money:
    """What a contradicted claim stated in dollars against what its clause version sets, when there is exactly one of
    each. Db2 reads the clause's side itself (ADD_BACKTEST_COST); this only finds the key and the claim's amount."""
    no = claim.claim_no
    amounts = [q for q in extract_quantities(NOT_A_PRICE.sub(" ", claim.text)) if q.value_in("usd") is not None]
    values = [q for q in amounts if not q.limit]
    keys = [p for p in rule_params(claim.clause.rule if claim.clause else {}) if p.unit == "usd" and not p.limit]
    if not amounts:
        return Money(no, None, None, NO_AMOUNT)
    if not values:
        return Money(no, None, None, ONLY_LIMIT)
    if not keys:
        return Money(no, None, None, CLAUSE_NO_AMOUNT)
    if len(values) > 1 or len(keys) > 1:
        return Money(no, None, None, AMBIGUOUS)
    stated, key = values[0].value_in("usd") or 0.0, keys[0]
    if same_amount(stated, key.value, "usd"):
        return Money(no, None, None, SAME_AMOUNT)
    amount = Decimal(str(stated)).quantize(Decimal("0.01"))
    if not Decimal(0) <= amount <= MAX_STATED_USD:
        return Money(no, None, None, OUT_OF_RANGE)
    return Money(no, key.key, amount, ONE_OCCURRENCE)


# ---------- running ----------
class Stop(Exception):  # noqa: N818 - a request to stop, not an error
    """Raised by a before-check hook to end a run: this row and every row after it are recorded SKIPPED (RUN_STOPPED)
    and the run STOPPED, with the exception's text as its note."""


# The hook a spend cap on live checks plugs into (another part of AsOf owns that cap; nothing here meters spend). It
# is called before each row's check and raises Stop to end the run there. The default lets every row run.
BeforeCheck = Callable[[Row], None]


def no_limit(row: Row) -> None:
    return None


PROCEDURES = frozenset({"START_BACKTEST", "ADD_BACKTEST_ITEM", "ADD_BACKTEST_COST", "FINISH_BACKTEST"})


def _call(conn: ibm_db_dbi.Connection, name: str, params: tuple[Any, ...]) -> tuple[Any, ...]:
    """CALL one of the four backtest procedures (only those names) with bound parameters, and commit."""
    if name not in PROCEDURES:
        raise ValueError(f"not a backtest procedure: {name!r}")
    cur = conn.cursor()
    try:
        out = cur.callproc(name, params)
        conn.commit()
        return tuple(out)
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        raise db.wrap_error(exc, f"{name} failed") from None
    finally:
        cur.close()


class Backtest:
    """Runs uploads through the check, one row at a time, and records each outcome in Db2."""

    def __init__(self, gate: Gate, connect: Callable[[], ibm_db_dbi.Connection], schema: str = db.SCHEMA,
                 router: Any = None, before_check: BeforeCheck | None = None,
                 clock: Callable[[], float] = time.monotonic):
        self.gate, self.connect, self.schema = gate, connect, schema
        self.router = router  # asof.router.Router, for rows on doc_id auto
        self.before_check = before_check or no_limit
        self.clock = clock

    def _proc(self, name: str, params: tuple[Any, ...]) -> tuple[Any, ...]:
        conn = self.connect()
        try:
            db.use_schema(conn, self.schema)
            return _call(conn, name, params)
        finally:
            conn.close()

    def start(self, upload: Upload, doc_id: str, deadline_s: float, requested_by: str | None = None,
              sample: bool = False) -> int:
        """Open a run in Db2 (START_BACKTEST) and return its ID. The rows run with run()."""
        if doc_id not in DOC_CHOICES:
            raise ValueError(f"doc_id must be one of {', '.join(DOC_CHOICES)}")
        stale_s = int(min(86400, max(60, 2 * self.gate.deadline_s + 60)))  # a live row never goes this long
        out = self._proc("START_BACKTEST", (upload.name[:200], upload.sha256, len(upload.rows), doc_id,
                                            self.gate.llm.info[:200], int(sample), int(max(1, min(deadline_s, 86400))),
                                            stale_s, requested_by or "", 0))
        return int(out[-1])

    def run(self, run_id: int, upload: Upload, doc_id: str, deadline_s: float, requested_by: str | None = None) -> str:
        """Check every row, record each outcome, close the run. Returns the run's final status."""
        deadline_at = self.clock() + deadline_s
        status, note = "DONE", None
        rows = upload.rows
        try:
            for i, row in enumerate(rows):
                if self.clock() > deadline_at:
                    self._skip(run_id, rows[i:], "RUN_DEADLINE", "not checked: the run's deadline passed")
                    status = "DEADLINE"
                    note = f"the run's {deadline_s:.0f} s deadline passed after {i} of {len(rows)} rows"
                    break
                try:
                    self.before_check(row)
                except Stop as exc:
                    self._skip(run_id, rows[i:], "RUN_STOPPED", f"not checked: {exc}"[:300])
                    status, note = "STOPPED", f"stopped before row {row.row_no}: {exc}"[:400]
                    break
                self._row(run_id, row, doc_id, requested_by)
        except Exception as exc:  # noqa: BLE001 - Db2 would not record an outcome: the run cannot account for its rows
            log.exception("backtest run %s stopped", run_id)
            status, note = "FAILED", f"the run stopped: {str(exc)[:300]}"
        try:
            self._proc("FINISH_BACKTEST", (run_id, status, note or ""))
        except db.DatabaseError as exc:  # V_BACKTEST_RUNS shows it INTERRUPTED once it has been stale long enough
            log.error("backtest run %s could not be closed (%s): %s", run_id, status, exc)
            return "FAILED"
        log.info("backtest run %s: %s", run_id, status)
        return status

    def _skip(self, run_id: int, rows: list[Row], reason: str, detail: str) -> None:
        for row in rows:
            self._item(run_id, row, "", 0, reason, detail)

    def _item(self, run_id: int, row: Row, doc_id: str, ledger_id: int, reason: str, detail: str | None) -> str:
        out = self._proc("ADD_BACKTEST_ITEM", (run_id, row.row_no, row.customer_date, row.channel, doc_id, ledger_id,
                                               reason, (detail or "")[:300], " " * 12))
        return str(out[-1]).strip()

    def check_row(self, run_id: int, row: Row, default_doc: str, requested_by: str | None) -> tuple[GateResult, str]:
        """The normal check of one row, recorded on channel 'backtest' (routed first when its document is auto)."""
        doc = row.doc_id or default_doc
        tag = {"run_id": run_id, "row": row.row_no, "source_channel": row.channel}
        if doc != "auto":
            req = GateRequest(row.question, row.draft, row.customer_date, doc, CHANNEL, requested_by, backtest=tag)
            return self.gate.check(req), doc
        if self.router is None:
            raise RuntimeError("this row's document is auto, and no router was given")
        r = self.router.route(row.question, row.draft, row.customer_date)
        req = GateRequest(row.question, row.draft, row.customer_date, r.doc_id or r.leader, CHANNEL, requested_by,
                          r.as_json(), backtest=tag)
        result = self.gate.check(req) if r.doc_id else self.gate.hold(req, "ROUTE_UNCERTAIN", f"router:{r.method}")
        return result, req.doc_id

    def _row(self, run_id: int, row: Row, default_doc: str, requested_by: str | None) -> None:
        try:
            result, doc = self.check_row(run_id, row, default_doc, requested_by)
        except Exception as exc:  # noqa: BLE001 - the check fails closed itself; this is routing or anything around it
            log.warning("backtest run %s row %s: check failed: %s", run_id, row.row_no, exc)
            self._item(run_id, row, "", 0, "CHECK_ERROR", f"{type(exc).__name__}: {str(exc)[:200]}")
            return
        if result.ledger_id is None:  # the decision could not be recorded: nothing to point at
            self._item(run_id, row, doc, 0, "LEDGER_UNAVAILABLE", result.error)
            return
        try:
            outcome = self._item(run_id, row, doc, result.ledger_id, "", result.error)
        except db.DatabaseError as exc:  # Db2 refused the link: record the row as failed, with why
            log.error("backtest run %s row %s: outcome refused: %s", run_id, row.row_no, exc)
            self._item(run_id, row, "", 0, "CHECK_ERROR", f"Db2 refused the outcome (SQLSTATE {exc.sqlstate})")
            return
        if outcome != "WRONG":
            return
        for claim in result.claims:  # the first pass: what the past answer said
            if claim.verdict == "CONTRADICTED" and claim.clause is not None:
                self._cost(run_id, row.row_no, money_of(claim))

    def _cost(self, run_id: int, row_no: int, m: Money) -> None:
        try:
            self._proc("ADD_BACKTEST_COST", (run_id, row_no, m.claim_no, m.rule_key or "", m.stated_usd or Decimal(0),
                                             m.note, Decimal(0)))
        except db.DatabaseError as exc:
            if m.rule_key is None:
                raise
            log.warning("backtest run %s row %s claim %s: amount refused: %s", run_id, row_no, m.claim_no, exc)
            self._proc("ADD_BACKTEST_COST", (run_id, row_no, m.claim_no, "", Decimal(0),
                                             f"Db2 could not read {m.rule_key} from the clause (SQLSTATE {exc.sqlstate})"[:200],
                                             Decimal(0)))


# ---------- the exposure report (SQL over Db2) ----------
# Every statement is a literal; names are unqualified (db.use_schema binds the schema).
_RUN_COLS = ("run_id", "source_name", "sha256", "rows", "doc_id", "model", "sample", "state", "note", "created_at",
             "requested_by", "deadline_at", "last_progress_at", "finished_at", "items", "wrong", "unconfirmed", "ok",
             "failed", "skipped")
SQL_RUN = ("SELECT RUN_ID, SOURCE_NAME, SOURCE_SHA256, ROW_COUNT, DOC_ID, MODEL_INFO, IS_SAMPLE, STATE, NOTE, CREATED_AT, "
           "REQUESTED_BY, DEADLINE_AT, LAST_PROGRESS_AT, FINISHED_AT, ITEMS, WRONG, UNCONFIRMED, OK, FAILED, SKIPPED "
           "FROM V_BACKTEST_RUNS WHERE RUN_ID = ?")
SQL_RUNS = ("SELECT RUN_ID, SOURCE_NAME, SOURCE_SHA256, ROW_COUNT, DOC_ID, MODEL_INFO, IS_SAMPLE, STATE, NOTE, CREATED_AT, "
            "REQUESTED_BY, DEADLINE_AT, LAST_PROGRESS_AT, FINISHED_AT, ITEMS, WRONG, UNCONFIRMED, OK, FAILED, SKIPPED "
            "FROM V_BACKTEST_RUNS ORDER BY RUN_ID DESC FETCH FIRST ? ROWS ONLY")
SQL_LATEST_SAMPLE = "SELECT MAX(RUN_ID) FROM BACKTEST_RUN WHERE IS_SAMPLE = 1 AND STATUS = 'DONE'"
SQL_BY_CLAUSE = ("SELECT CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, MAX(CLAUSE_BUS_END), COUNT(DISTINCT ROW_NO), "
                 "COUNT(*), SUM(CASE WHEN COST_STATUS = 'COMPUTED' THEN 1 ELSE 0 END), COALESCE(SUM(ABS(DIFF_USD)), 0) "
                 "FROM V_BACKTEST_CONTRADICTIONS WHERE RUN_ID = ? "
                 "GROUP BY CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START ORDER BY 5 DESC, 8 DESC, 1, 3")
SQL_MONEY = ("SELECT COALESCE(COST_STATUS, 'NOT_RECORDED'), COALESCE(FAVOURS, 'NONE'), COUNT(*), "
             "COALESCE(SUM(ABS(DIFF_USD)), 0) FROM V_BACKTEST_CONTRADICTIONS WHERE RUN_ID = ? "
             "GROUP BY COALESCE(COST_STATUS, 'NOT_RECORDED'), COALESCE(FAVOURS, 'NONE')")
SQL_NOT_COMPUTABLE = ("SELECT COALESCE(COST_NOTE, 'no money record was written for this claim'), COUNT(*) "
                      "FROM V_BACKTEST_CONTRADICTIONS WHERE RUN_ID = ? AND COALESCE(COST_STATUS, '') <> 'COMPUTED' "
                      "GROUP BY COALESCE(COST_NOTE, 'no money record was written for this claim') ORDER BY 2 DESC, 1")
SQL_CONTRADICTIONS = ("SELECT ROW_NO, CLAIM_NO, CLAIM_TEXT, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_BUS_END, "
                      "RULE_CHECK, COST_STATUS, RULE_KEY, STATED_USD, POLICY_USD, DIFF_USD, FAVOURS, COST_NOTE "
                      "FROM V_BACKTEST_CONTRADICTIONS WHERE RUN_ID = ? ORDER BY ROW_NO, CLAIM_NO")
# The costliest wrong answers, with their redacted text read as the runtime user (the ledger's column masks show it
# only to role ASOF_TEXT_READER).
SQL_COSTLIEST = ("SELECT X.ROW_NO, X.TOTAL FROM (SELECT ROW_NO, SUM(ABS(DIFF_USD)) AS TOTAL "
                 "FROM V_BACKTEST_CONTRADICTIONS WHERE RUN_ID = ? AND COST_STATUS = 'COMPUTED' GROUP BY ROW_NO) X "
                 "ORDER BY X.TOTAL DESC, X.ROW_NO FETCH FIRST ? ROWS ONLY")
SQL_ITEMS = ("SELECT I.ROW_NO, I.CUSTOMER_DATE, I.SOURCE_CHANNEL, I.DOC_ID, I.LEDGER_ID, I.OUTCOME, I.REASON_CODE, "
             "I.DETAIL, L.DECISION, L.QUESTION_REDACTED, L.DRAFT_REDACTED, L.FINAL_ANSWER "
             "FROM BACKTEST_ITEM I LEFT JOIN ANSWER_LEDGER L ON L.LEDGER_ID = I.LEDGER_ID "
             "WHERE I.RUN_ID = ? ORDER BY I.ROW_NO")
COSTLIEST = 5


def _s(v: Any) -> Any:
    return v.strip() if isinstance(v, str) else v


def _usd(v: Any) -> float | None:
    return None if v is None else float(v)


def _run(row: tuple[Any, ...]) -> dict[str, Any]:
    out = dict(zip(_RUN_COLS, map(_s, row), strict=True))
    out["sample"] = bool(out["sample"])
    for k in ("items", "wrong", "unconfirmed", "ok", "failed", "skipped", "rows"):
        out[k] = int(out[k])
    out["unaccounted"] = out["rows"] - out["items"]  # rows with no outcome: only a FAILED or INTERRUPTED run has any
    return out


def list_runs(conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA, limit: int = 20) -> list[dict[str, Any]]:
    db.use_schema(conn, schema)
    return [_run(r) for r in db.query(conn, SQL_RUNS, (limit,))]


def latest_sample(conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA) -> int | None:
    db.use_schema(conn, schema)
    found = db.query(conn, SQL_LATEST_SAMPLE)
    return int(found[0][0]) if found and found[0][0] is not None else None


def report(conn: ibm_db_dbi.Connection, run_id: int, schema: str = db.SCHEMA) -> dict[str, Any] | None:
    """The exposure report of one run: outcome counts, wrong answers by clause version, the money at stake and where
    it could not be computed, the costliest examples and every row's outcome. Read as the runtime user."""
    db.use_schema(conn, schema)
    found = db.query(conn, SQL_RUN, (run_id,))
    if not found:
        return None
    run = _run(found[0])
    contradictions: dict[int, list[dict[str, Any]]] = {}
    for r in db.query(conn, SQL_CONTRADICTIONS, (run_id,)):
        contradictions.setdefault(int(r[0]), []).append({
            "claim_no": int(r[1]), "claim": r[2], "clause_id": _s(r[3]), "version": _s(r[4]), "from": r[5],
            "to": r[6], "rule_check": _s(r[7]), "money": _s(r[8]) or "NOT_RECORDED", "rule_key": _s(r[9]),
            "stated_usd": _usd(r[10]), "policy_usd": _usd(r[11]), "diff_usd": _usd(r[12]), "favours": _s(r[13]),
            "note": r[14]})
    items = []
    for r in db.query(conn, SQL_ITEMS, (run_id,)):
        row_no = int(r[0])
        items.append({"row": row_no, "customer_date": r[1], "channel": _s(r[2]), "doc_id": _s(r[3]),
                      "ledger_id": int(r[4]) if r[4] is not None else None, "outcome": _s(r[5]), "reason": _s(r[6]),
                      "detail": r[7], "decision": _s(r[8]), "question": r[9], "draft": r[10], "final_answer": r[11],
                      "contradicted": contradictions.get(row_no, [])})
    by_row = {i["row"]: i for i in items}
    money = {"computed_claims": 0, "not_computable_claims": 0, "total_abs_usd": 0.0,
             "customer_favour_usd": 0.0, "customer_favour_claims": 0, "company_favour_usd": 0.0, "company_favour_claims": 0}
    for status, favours, n, total in db.query(conn, SQL_MONEY, (run_id,)):
        status, favours, n, total = status.strip(), favours.strip(), int(n), float(total)
        if status == "COMPUTED":
            money["computed_claims"] += n
            money["total_abs_usd"] += total
            if favours == "CUSTOMER":
                money["customer_favour_usd"] += total
                money["customer_favour_claims"] += n
            elif favours == "COMPANY":
                money["company_favour_usd"] += total
                money["company_favour_claims"] += n
        else:
            money["not_computable_claims"] += n
    by_clause = [{"clause_id": _s(c), "version": _s(v), "from": f, "to": t, "wrong_answers": int(w),
                  "contradicted_claims": int(n), "priced_claims": int(p), "abs_usd": float(u)}
                 for c, v, f, t, w, n, p, u in db.query(conn, SQL_BY_CLAUSE, (run_id,))]
    costliest = [{**{k: by_row[int(r)][k] for k in ("row", "customer_date", "channel", "ledger_id", "decision",
                                                     "question", "draft", "final_answer", "contradicted")},
                  "abs_usd": float(total)} for r, total in db.query(conn, SQL_COSTLIEST, (run_id, COSTLIEST))]
    not_computable = [{"reason": why, "claims": int(n)} for why, n in db.query(conn, SQL_NOT_COMPUTABLE, (run_id,))]
    return {"run": run, "contradicted_claims": sum(len(v) for v in contradictions.values()), "money": money,
            "by_clause": by_clause, "costliest": costliest, "not_computable": not_computable, "items": items,
            "cost_method": COST_METHOD}


# ---------- the sample and the command line ----------
def sample_upload() -> Upload:
    return parse_csv(SAMPLE_CSV.read_bytes(), SAMPLE_NAME)


def run_upload(gate: Gate, connect: Callable[[], ibm_db_dbi.Connection], upload: Upload, doc_id: str = "auto",
               deadline_s: float = 1800.0, schema: str = db.SCHEMA, router: Any = None, sample: bool = False,
               before_check: BeforeCheck | None = None) -> tuple[int, str]:
    """Start and finish one run in this thread. Returns (run_id, final status)."""
    bt = Backtest(gate, connect, schema, router=router, before_check=before_check)
    run_id = bt.start(upload, doc_id, deadline_s, sample=sample)
    return run_id, bt.run(run_id, upload, doc_id, deadline_s)


def _summary(rep: dict[str, Any]) -> str:
    r, m = rep["run"], rep["money"]
    lines = [f"Backtest run {r['run_id']} ({r['source_name']}, {r['rows']} rows, {r['model']}): {r['state']}",
             f"  wrong {r['wrong']}, unconfirmed {r['unconfirmed']}, ok {r['ok']}, failed {r['failed']}, "
             f"skipped {r['skipped']}",
             f"  {rep['contradicted_claims']} contradicted claims; {m['computed_claims']} priced: "
             f"${m['total_abs_usd']:.2f} in all, ${m['customer_favour_usd']:.2f} in the customer's favour, "
             f"${m['company_favour_usd']:.2f} against the customer; {m['not_computable_claims']} not computable"]
    lines += [f"  {c['clause_id']} {c['version']}: {c['wrong_answers']} wrong answer(s), ${c['abs_usd']:.2f}"
              for c in rep["by_clause"]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m asof.backtest", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="check a CSV of past answers")
    p_run.add_argument("file", type=Path)
    p_run.add_argument("--doc-id", default="auto", choices=DOC_CHOICES, help="for rows without a doc_id (default auto)")
    sub.add_parser("sample", help="check the shipped sample (replay mode can)")
    p_rep = sub.add_parser("report", help="print the exposure report of a run")
    p_rep.add_argument("run_id", type=int)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)

    from .config import ConfigError, get_settings
    from .embeddings import get_embeddings
    from .llm import LLMError, build_llm
    from .router import Router

    settings = get_settings()
    connect = db.ConnectionPool(settings, "app").connect
    try:
        if args.command == "report":
            with db.connection(settings, "app") as conn:
                rep = report(conn, args.run_id)
            if rep is None:
                print(f"No backtest run {args.run_id}.")
                return 1
            print(_summary(rep))
            return 0
        if args.command == "sample":
            upload = sample_upload()
        else:
            if args.file.stat().st_size > MAX_CSV_BYTES:
                print(f"{args.file} is larger than {MAX_CSV_BYTES // (1024 * 1024)} MB.")
                return 1
            upload = parse_csv(args.file.read_bytes(), args.file.name, settings.asof_backtest_max_rows)
        llm, emb = build_llm(settings), get_embeddings(settings.embedding_model)
        from .anchor import AnchorLog

        gate = Gate(llm, emb, connect, deadline_s=settings.asof_check_deadline_s, anchors=AnchorLog.from_settings(settings))
        run_id, status = run_upload(gate, connect, upload, "auto" if args.command == "sample" else args.doc_id,
                                    settings.asof_backtest_deadline_s, router=Router(emb, connect),
                                    sample=args.command == "sample")
        with db.connection(settings, "app") as conn:
            print(_summary(report(conn, run_id) or {}))
        return 0 if status in ("DONE", "DEADLINE", "STOPPED") else 1
    except CsvError as exc:
        print(f"The file cannot be run: {exc}")
        for e in exc.errors[:20]:
            print(f"  {'row ' + str(e['row']) if e['row'] else 'file'}: {e['message']}")
        return 1
    except (ConfigError, LLMError, db.DatabaseError) as exc:
        print(f"Backtest failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
