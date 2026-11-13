"""Backtest mode without Db2: the CSV validation, the money rule, the runner's fail-closed behaviour and the sample.

tests/test_db2_backtest.py runs the sample through Db2's procedures in replay mode and checks the report's numbers.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date
from pathlib import Path

import pytest
from fakes import clause

from asof import backtest, db, replay
from asof.gate import ClaimOutcome, GateResult

ROOT = Path(__file__).resolve().parents[1]
GOOD = ("question,draft,customer_date,channel\n"
        "How much is the first checked bag?,The first checked bag is $35.,2026-07-15,chat\n")


def parse(text: str | bytes, **kw) -> backtest.Upload:
    return backtest.parse_csv(text.encode("utf-8") if isinstance(text, str) else text, "past.csv", **kw)


def problems(text: str | bytes, **kw) -> list[dict]:
    with pytest.raises(backtest.CsvError) as err:
        parse(text, **kw)
    return err.value.errors


# ---------- the CSV ----------
def test_a_valid_file_parses_with_rows_numbered_from_one():
    up = parse("﻿Question , Draft,customer_date,CHANNEL,doc_id\n"
               "q1,d1,2026-03-10,Chat,\n\n"
               "\"q2, with a comma\",\"line one\nline two\",2026-06-02,email,FERNHOLLOW-FEES\n")
    assert [(r.row_no, r.question, r.draft, r.customer_date, r.channel, r.doc_id) for r in up.rows] == [
        (1, "q1", "d1", date(2026, 3, 10), "chat", None),
        (2, "q2, with a comma", "line one\nline two", date(2026, 6, 2), "email", "FERNHOLLOW-FEES")]
    assert up.rows[1].line == 5 and up.name == "past.csv" and re.fullmatch(r"[0-9a-f]{64}", up.sha256)


@pytest.mark.parametrize(("data", "message"), [
    (b"", "the file is empty"),
    (b"question,draft,customer_date,channel\n", "has a header but no rows"),
    (b"question,draft\x00,customer_date,channel\n", "NUL bytes"),
    ("question,draft,customer_date,channel\nCafé,d,2026-03-10,chat\n".encode("latin-1"), "not UTF-8"),
    (b"question,draft,channel\nq,d,chat\n", "missing column(s) customer_date"),
    (b"question,draft,customer_date,channel,notes\nq,d,2026-03-10,chat,x\n", "unknown column(s) 'notes'"),
    (b"question,draft,customer_date,channel,channel\nq,d,2026-03-10,chat,chat\n", "repeated column(s) channel"),
    (b"question,draft,customer_date,channel\n\"q,d,2026-03-10,chat\n", "not valid CSV"),
])
def test_file_level_problems_are_refused_with_a_clear_message(data, message):
    assert message in problems(data)[0]["message"]


def test_the_size_cap_is_checked_before_anything_is_parsed():
    big = GOOD.encode() + b"x" * backtest.MAX_CSV_BYTES
    assert "larger than 2 MB" in problems(big)[0]["message"]


def test_the_row_cap_is_the_setting_and_never_more_than_500():
    rows = "".join(f"q{i},d,2026-03-10,chat\n" for i in range(4))
    assert "more than 3 rows" in problems("question,draft,customer_date,channel\n" + rows, max_rows=3)[0]["message"]
    many = "".join(f"q{i},d,2026-03-10,chat\n" for i in range(501))
    assert "more than 500 rows" in problems("question,draft,customer_date,channel\n" + many, max_rows=9999)[0]["message"]
    assert len(parse("question,draft,customer_date,channel\n" + many[: many.index("q500")]).rows) == 500


@pytest.mark.parametrize(("row", "column", "message"), [
    (",d,2026-03-10,chat", "question", "question is empty"),
    ("q,  ,2026-03-10,chat", "draft", "draft is empty"),
    ("q," + "é" * 2001 + ",2026-03-10,chat", "draft", "longer than 4000 bytes"),   # 2001 characters, 4002 bytes
    ("q\x07,d,2026-03-10,chat", "question", "control characters"),
    ("q,d,10/03/2026,chat", "customer_date", "must be an ISO date"),
    ("q,d,2026-02-30,chat", "customer_date", "not a calendar date"),
    ("q,d,2019-12-31,chat", "customer_date", "between 2020-01-01 and 2035-12-31"),
    ("q,d,2026-03-10,sms", "channel", "must be one of chat, email, faq, api"),
    ("q,d,2026-03-10,chat,OTHER-AIRLINE", "doc_id", "must be empty or one of"),
    ("q,d,2026-03-10", None, "has 3 fields; the header has 4"),
])
def test_every_bad_field_is_named_with_its_row_and_line(row, column, message):
    header = "question,draft,customer_date,channel" + (",doc_id" if row.count(",") == 4 else "")
    errors = problems(f"{header}\nok,ok,2026-03-10,chat{',' if 'doc_id' in header else ''}\n{row}\n")
    assert len(errors) == 1
    assert (errors[0]["row"], errors[0]["line"], errors[0]["column"]) == (2, 3, column)
    assert message in errors[0]["message"]


def test_every_problem_is_counted_and_the_first_fifty_are_listed():
    rows = "".join(f"q,d,not-a-date,chat\n" for _ in range(60))  # noqa: F541
    with pytest.raises(backtest.CsvError) as err:
        parse("question,draft,customer_date,channel\n" + rows)
    assert err.value.total == 60 and len(err.value.errors) == 50
    assert str(err.value).startswith("row 1: customer_date must be an ISO date") and "(and 59 more)" in str(err.value)


def test_sql_and_markup_in_a_cell_are_only_text():
    up = parse("question,draft,customer_date,channel\n\"'); DROP TABLE ASOF.ANSWER_LEDGER; --\","
               "<script>alert(1)</script>,2026-03-10,api\n")
    assert up.rows[0].question.startswith("');") and up.rows[0].draft == "<script>alert(1)</script>"


@pytest.mark.parametrize(("given", "shown"), [("../../etc/passwd", "passwd.csv"), (None, "backtest.csv"),
                                              ("Q3 answers.CSV", "Q3 answers.CSV"), ("a<b>.csv", "a_b_.csv")])
def test_the_file_name_kept_is_a_plain_base_name(given, shown):
    assert backtest.safe_name(given) == shown


def test_the_csv_limits_match_the_api_and_db2():
    from asof import api

    assert (backtest.MIN_DATE, backtest.MAX_DATE) == (api.MIN_DATE, api.MAX_DATE)
    assert api.body_limit("POST", "/api/backtests") == backtest.MAX_CSV_BYTES
    assert api.body_limit("POST", "/api/gate") == api.MAX_BODY_BYTES
    sql = (ROOT / "src/asof/sql/11_backtest.sql").read_text(encoding="utf-8")
    assert f"ROW_COUNT BETWEEN 1 AND {backtest.HARD_MAX_ROWS}" in sql
    channels = re.search(r"CK_BACKTEST_ITEM_CHANNEL CHECK \(SOURCE_CHANNEL IN \(([^)]*)\)", sql).group(1)
    assert tuple(c.strip(" '") for c in channels.split(",")) == backtest.CHANNELS


def test_the_ledger_channel_list_is_the_same_in_both_sql_files():
    """01_tables.sql creates the check for new ledgers; 11_backtest.sql replaces it on ledgers made before backtests."""
    pattern = re.compile(r"CONSTRAINT CK_LEDGER_CHANNEL CHECK \(CHANNEL IN \(([^)]*)\)\)")
    lists = [pattern.search((ROOT / "src/asof/sql" / f).read_text(encoding="utf-8")).group(1)
             for f in ("01_tables.sql", "11_backtest.sql")]
    assert lists[0] == lists[1] and "'backtest'" in lists[0]


# ---------- the money rule ----------
def contradicted(text: str, clause_id: str, on: date, no: int = 1) -> ClaimOutcome:
    return ClaimOutcome(no, text, "baggage", "amount", "CONTRADICTED", "CONTRADICTED", "MISMATCH", [],
                        clause(clause_id, on), None, "r")


@pytest.mark.parametrize(("text", "clause_id", "on", "key", "stated", "note"), [
    ("The first checked bag costs $35 each way.", "BAG-001", date(2026, 7, 15), "first_bag_fee_usd", "35.00", None),
    ("Dogs fly free in the cabin.", "PET-001", date(2026, 5, 5), "pet_fee_usd", "0.00", None),
    ("You can claim the fare after you travel.", "BRV-002", date(2026, 3, 10), None, None, backtest.NO_AMOUNT),
    ("Overdrafts of up to $50 are free of any fee.", "OVD-002", date(2026, 3, 10), None, None,
     backtest.CLAUSE_NO_AMOUNT),  # OVD-002 sets only a limit (max_no_fee_overdraft_usd)
    ("Bags cost $35, and $50 for the second.", "BAG-001", date(2026, 7, 15), None, None, backtest.AMBIGUOUS),
    ("We cover overdrafts of up to $50.", "OVD-001", date(2026, 3, 10), None, None, backtest.ONLY_LIMIT),
    ("A name change costs $50.", "CHG-004", date(2026, 4, 1), None, None, backtest.CLAUSE_NO_AMOUNT),
    ("Paper statements cost $3 a month.", "MTF-003", date(2026, 3, 10), None, None, backtest.AMBIGUOUS),
    ("A 12 kg dog flies for $100.", "PET-001", date(2026, 5, 5), None, None, backtest.SAME_AMOUNT),
    ("Feel free to bring a bag for $45.", "BAG-001", date(2026, 7, 15), "first_bag_fee_usd", "45.00", None),
])
def test_a_money_difference_needs_one_amount_on_each_side(text, clause_id, on, key, stated, note):
    m = backtest.money_of(contradicted(text, clause_id, on))
    assert (m.rule_key, None if m.stated_usd is None else str(m.stated_usd)) == (key, stated)
    assert m.note == (note or backtest.ONE_OCCURRENCE)
    assert len(m.note) >= 10  # ADD_BACKTEST_COST refuses a shorter reason


def test_an_amount_outside_what_db2_accepts_is_not_priced():
    m = backtest.money_of(contradicted("The first bag costs $2,000,000.", "BAG-001", date(2026, 7, 15)))
    assert m.rule_key is None and m.note == backtest.OUT_OF_RANGE


# ---------- the runner, with Db2's procedures recorded instead of called ----------
class Procs:
    """Stands in for the four procedures; derives an outcome from the fake gate's decision as Db2 would."""

    def __init__(self, refuse_item: bool = False):
        self.calls: list[tuple[str, tuple]] = []
        self.refuse_item = refuse_item

    def __call__(self, name, params):
        self.calls.append((name, params))
        if name == "START_BACKTEST":
            return (*params[:-1], 7)
        if name == "ADD_BACKTEST_ITEM":
            ledger_id, reason = params[5], params[6]
            if ledger_id and self.refuse_item:
                raise db.DatabaseError("refused", "75094")
            if not ledger_id:
                return (*params[:-1], "SKIPPED" if reason.startswith("RUN_") else "FAILED")
            return (*params[:-1], {1: "WRONG", 2: "OK"}.get(ledger_id % 10, "UNCONFIRMED"))
        return params

    def items(self):
        return [(p[1], p[5], p[6]) for n, p in self.calls if n == "ADD_BACKTEST_ITEM"]

    def named(self, name):
        return [p for n, p in self.calls if n == name]


class Gate:
    deadline_s = 300.0

    def __init__(self, results=None, raise_on=()):
        self.llm = type("L", (), {"info": "fake:model"})()
        self.results, self.raise_on, self.seen, self.held = results or {}, set(raise_on), [], []

    def check(self, req):
        self.seen.append(req)
        row = req.backtest["row"]
        if row in self.raise_on:
            raise RuntimeError("boom")
        ledger_id, claims = self.results.get(row, (row * 10 + 2, []))
        return GateResult("rid", "PASS", "ALL_SUPPORTED", "", claims, [], None, 1, "fake:model", ledger_id=ledger_id,
                          error=None if ledger_id else "ledger unavailable: down")

    def hold(self, req, reason, model):
        self.held.append((req, reason))
        return GateResult("rid", "ESCALATED", reason, "", [], [], None, 0, model, ledger_id=req.backtest["row"] * 10 + 3)


def upload(n: int, doc: str | None = "AURELIA-CSP") -> backtest.Upload:
    rows = [backtest.Row(i, i + 1, f"q{i}", f"d{i}", date(2026, 3, 10), "chat", doc) for i in range(1, n + 1)]
    return backtest.Upload("t.csv", "0" * 64, rows)


def runner(gate, procs, **kw) -> backtest.Backtest:
    bt = backtest.Backtest(gate, connect=lambda: None, **kw)
    bt._proc = procs  # type: ignore[method-assign]
    return bt


def test_every_row_is_checked_on_channel_backtest_with_its_provenance_hashed():
    procs, gate = Procs(), Gate()
    bt = runner(gate, procs)
    assert bt.start(upload(2), "auto", 60) == 7
    assert procs.named("START_BACKTEST")[0][:4] == ("t.csv", "0" * 64, 2, "auto")
    assert bt.run(7, upload(2), "auto", 60) == "DONE"
    assert [(r.channel, r.doc_id, r.backtest) for r in gate.seen] == [
        ("backtest", "AURELIA-CSP", {"run_id": 7, "row": 1, "source_channel": "chat"}),
        ("backtest", "AURELIA-CSP", {"run_id": 7, "row": 2, "source_channel": "chat"})]
    assert procs.items() == [(1, 12, ""), (2, 22, "")]
    assert procs.named("FINISH_BACKTEST") == [(7, "DONE", "")]


def test_a_failed_check_or_ledger_is_one_failed_row_and_the_run_goes_on():
    procs = Procs()
    gate = Gate(results={2: (None, [])}, raise_on={1})
    assert runner(gate, procs).run(7, upload(3), "auto", 60) == "DONE"
    assert procs.items() == [(1, 0, "CHECK_ERROR"), (2, 0, "LEDGER_UNAVAILABLE"), (3, 32, "")]


def test_a_refused_outcome_is_recorded_as_a_failed_row():
    procs = Procs(refuse_item=True)
    assert runner(Gate(), procs).run(7, upload(1), "auto", 60) == "DONE"
    assert procs.items() == [(1, 12, ""), (1, 0, "CHECK_ERROR")]
    assert "SQLSTATE 75094" in procs.named("ADD_BACKTEST_ITEM")[-1][7]


def test_no_row_starts_after_the_deadline_and_the_rest_are_skipped():
    procs, clock = Procs(), iter([0.0, 1.0, 2.0, 99.0])
    bt = runner(Gate(), procs, clock=lambda: next(clock))
    assert bt.run(7, upload(4), "auto", 10) == "DEADLINE"
    assert procs.items() == [(1, 12, ""), (2, 22, ""), (3, 0, "RUN_DEADLINE"), (4, 0, "RUN_DEADLINE")]
    assert procs.named("FINISH_BACKTEST")[0][1:] == ("DEADLINE", "the run's 10 s deadline passed after 2 of 4 rows")


def test_the_spend_hook_can_stop_a_run_before_any_row():
    def cap(row):
        if row.row_no == 2:
            raise backtest.Stop("today's spend cap for live checks is reached")

    procs = Procs()
    assert runner(Gate(), procs, before_check=cap).run(7, upload(3), "auto", 60) == "STOPPED"
    assert procs.items() == [(1, 12, ""), (2, 0, "RUN_STOPPED"), (3, 0, "RUN_STOPPED")]
    assert procs.named("FINISH_BACKTEST")[0][1:] == ("STOPPED", "stopped before row 2: today's spend cap for live "
                                                     "checks is reached")


def test_when_db2_will_not_record_an_outcome_the_run_ends_failed_and_says_why():
    procs = Procs()
    real = procs.__call__

    def down(name, params):
        if name == "ADD_BACKTEST_ITEM" and params[1] == 2:
            raise db.DatabaseError("ADD_BACKTEST_ITEM failed: SQL30081N", "08001")
        return real(name, params)

    bt = runner(Gate(results={2: (None, [])}), procs)
    bt._proc = down  # type: ignore[method-assign]
    assert bt.run(7, upload(3), "auto", 60) == "FAILED"
    assert procs.named("FINISH_BACKTEST")[0][1] == "FAILED" and "SQL30081N" in procs.named("FINISH_BACKTEST")[0][2]


def test_money_is_recorded_for_every_contradicted_claim_of_a_wrong_answer_only():
    wrong = [contradicted("The first checked bag costs $35 each way.", "BAG-001", date(2026, 7, 15), 1),
             ClaimOutcome(2, "Bags are welcome.", "baggage", "procedure", "SUPPORTED", "SUPPORTED", "NOT_APPLICABLE",
                          [], clause("BAG-001", date(2026, 7, 15)), "q", "r"),
             contradicted("You can claim the fare after you travel.", "BRV-002", date(2026, 3, 10), 3)]
    procs = Procs()
    gate = Gate(results={1: (11, wrong), 2: (22, wrong)})  # 11: WRONG; 22: OK, so no money even with contradictions
    runner(gate, procs).run(7, upload(2), "auto", 60)
    assert [(p[1], p[2], p[3], p[4]) for p in procs.named("ADD_BACKTEST_COST")] == [
        (1, 1, "first_bag_fee_usd", backtest.Decimal("35.00")), (1, 3, "", backtest.Decimal(0))]


def test_rows_on_auto_are_routed_and_a_close_call_is_held_not_guessed():
    class Route:
        def __init__(self, doc):
            self.doc_id, self.leader, self.method = doc, "AURELIA-CSP", "db2" if doc else "ask"

        def as_json(self):
            return {"doc_id": self.doc_id}

    class Router:
        def route(self, q, d, on):
            return Route("FERNHOLLOW-FEES" if q == "q1" else None)

    procs, gate = Procs(), Gate()
    runner(gate, procs, router=Router()).run(7, upload(2, doc=None), "auto", 60)
    assert [(r.doc_id, r.route) for r in gate.seen] == [("FERNHOLLOW-FEES", {"doc_id": "FERNHOLLOW-FEES"})]
    assert [(req.doc_id, reason) for req, reason in gate.held] == [("AURELIA-CSP", "ROUTE_UNCERTAIN")]
    assert [p[4] for p in procs.named("ADD_BACKTEST_ITEM")] == ["FERNHOLLOW-FEES", "AURELIA-CSP"]


def test_a_row_on_auto_without_a_router_fails_closed():
    procs = Procs()
    runner(Gate(), procs).run(7, upload(1, doc=None), "auto", 60)
    assert procs.items() == [(1, 0, "CHECK_ERROR")]


# ---------- the sample ----------
def test_the_sample_is_twenty_fictional_rows_over_both_policies_around_version_changes():
    up = backtest.sample_upload()
    assert len(up.rows) == 20 and backtest.SAMPLE_CSV.name.startswith("fictional-")
    assert {r.doc_id for r in up.rows} == {"AURELIA-CSP", "FERNHOLLOW-FEES"}
    assert {r.channel for r in up.rows} == set(backtest.CHANNELS)
    moffatt = {r.customer_date for r in up.rows if "bereavement fare after I travel" in r.question}
    assert moffatt == {date(2026, 3, 10), date(2026, 6, 2)}  # BRV-002 v1, then v2 from 1 May


def test_every_sample_row_is_an_input_replay_mode_has_a_recording_for():
    """Recorded checks, the inbox's recorded replies, and one recorded rewrite (the July bag fee answer)."""
    rec = replay.Recording.load()
    known = {(c["doc_id"], c["question"], c["draft_checked"], c["as_of"]) for c in rec.scenarios["checks"]}
    known |= {(r["doc_id"], r["question"], r["reply"], r["as_of"]) for r in replay.review_scenarios()}
    known.add(("AURELIA-CSP", "How much is the first checked bag?",
               "The first checked bag costs $40 each way on Economy fares.", "2026-07-15"))
    rows = list(csv.DictReader(io.StringIO(backtest.SAMPLE_CSV.read_text(encoding="utf-8"))))
    assert [r for r in rows if (r["doc_id"], r["question"], r["draft"], r["customer_date"]) not in known] == []
