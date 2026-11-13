"""The backtest routes without Db2: upload validation, the run handed to the background, one run at a time, the
roles, the public demo's refusal, and the Backtest page being part of the console."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_api import FakeAssistant, FakeGate

from asof import backtest
from asof.api import create_app, required_role
from asof.config import Settings

UI = Path(__file__).resolve().parents[1] / "src" / "asof" / "ui"
CSV = b"question,draft,customer_date,channel\nHow much is the first bag?,It is $35.,2026-07-15,chat\n"
TEXT_CSV = {"content-type": "text/csv"}


class FakeConn:
    def rollback(self):
        pass

    def close(self):
        pass


@pytest.fixture
def started(monkeypatch):
    """Backtest.start and .run recorded instead of reaching Db2."""
    seen: dict = {"start": [], "run": []}

    def start(self, upload, doc_id, deadline_s, requested_by=None, sample=False):
        seen["start"].append((upload, doc_id, deadline_s, requested_by, sample, self.router is not None))
        return 41

    def run(self, run_id, upload, doc_id, deadline_s, requested_by=None):
        seen["run"].append((run_id, len(upload.rows), doc_id))
        return "DONE"

    monkeypatch.setattr(backtest.Backtest, "start", start)
    monkeypatch.setattr(backtest.Backtest, "run", run)
    monkeypatch.setattr("asof.db.connect", lambda *a, **k: FakeConn())
    monkeypatch.setattr("asof.router.Router.__init__", lambda self, *a, **k: None)
    monkeypatch.setattr("asof.api.get_embeddings", lambda name: None)
    return seen


def client(launch=lambda work: work(), **settings) -> TestClient:
    app = create_app(Settings(_env_file=None, llm_provider="replay", asof_router_agent="off", **settings),
                     gate=FakeGate(), assistant=FakeAssistant(), backtest_launch=launch)
    return TestClient(app, raise_server_exceptions=False)


def test_a_valid_upload_starts_a_run_in_the_background(started):
    r = client().post("/api/backtests?doc_id=FERNHOLLOW-FEES&name=march.csv", content=CSV, headers=TEXT_CSV)
    assert r.status_code == 202 and r.json() == {"run_id": 41, "rows": 1, "state": "RUNNING"}
    upload, doc, deadline, who, sample, routed = started["start"][0]
    assert (upload.name, doc, deadline, who, sample, routed) == ("march.csv", "FERNHOLLOW-FEES", 1800.0, None, False, False)
    assert started["run"] == [(41, 1, "FERNHOLLOW-FEES")]


def test_the_shipped_sample_is_marked_as_the_sample_and_rows_on_auto_get_the_router(started):
    c = client()
    sample = c.get("/api/backtests/sample")
    assert sample.status_code == 200 and sample.headers["content-type"].startswith("text/csv")
    assert sample.content == backtest.SAMPLE_CSV.read_bytes()
    assert c.post("/api/backtests", content=sample.content, headers=TEXT_CSV).status_code == 202
    assert c.post("/api/backtests", content=CSV, headers=TEXT_CSV).status_code == 202  # doc_id auto, no doc_id column
    (_, doc1, _, _, sample1, routed1), (_, doc2, _, _, sample2, routed2) = started["start"]
    assert (doc1, sample1, routed1) == ("auto", True, False)  # every sample row names its document
    assert (doc2, sample2, routed2) == ("auto", False, True)


def test_one_run_at_a_time_and_the_next_one_starts_when_it_ends(started):
    waiting = []
    c = client(launch=waiting.append)  # the run never finishes until we say so
    assert c.post("/api/backtests", content=CSV, headers=TEXT_CSV).status_code == 202
    r = c.post("/api/backtests", content=CSV, headers=TEXT_CSV)
    assert r.status_code == 409 and "already running" in r.json()["detail"]
    waiting.pop()()
    assert c.post("/api/backtests", content=CSV, headers=TEXT_CSV).status_code == 202


@pytest.mark.parametrize(("body", "headers", "status", "message"), [
    (CSV, {"content-type": "application/json"}, 415, "Content-Type: text/csv"),
    (b"question,draft\nq,d\n", TEXT_CSV, 422, "missing column(s) customer_date, channel"),
    (CSV.replace(b"2026-07-15", b"15/07/2026"), TEXT_CSV, 422, "row 1: customer_date must be an ISO date"),
])
def test_a_bad_upload_is_refused_before_anything_runs(started, body, headers, status, message):
    r = client().post("/api/backtests", content=body, headers=headers)
    assert r.status_code == status and message in r.text
    assert started["start"] == []


def test_every_row_problem_comes_back_with_its_row_and_line(started):
    r = client().post("/api/backtests", content=CSV + b"q,d,2026-07-15,sms\n,d,2026-07-15,chat\n", headers=TEXT_CSV)
    body = r.json()
    assert r.status_code == 422 and body["total_errors"] == 2
    assert [(e["row"], e["line"], e["column"]) for e in body["errors"]] == [(2, 3, "channel"), (3, 4, "question")]


def test_a_file_over_the_cap_is_refused_by_size(started):
    r = client().post("/api/backtests", content=b"x" * (backtest.MAX_CSV_BYTES + 1), headers=TEXT_CSV)
    assert r.status_code == 413


def test_the_row_cap_setting_applies_to_uploads(started):
    r = client(asof_backtest_max_rows=1).post("/api/backtests", content=CSV + CSV.split(b"\n", 1)[1], headers=TEXT_CSV)
    assert r.status_code == 422 and "more than 1 rows" in r.json()["error"]


def test_an_unknown_document_is_refused_by_validation(started):
    r = client().post("/api/backtests?doc_id=OTHER", content=CSV, headers=TEXT_CSV)
    assert r.status_code == 422 and started["start"] == []


def test_a_report_that_does_not_exist_is_a_404(monkeypatch):
    monkeypatch.setattr("asof.db.connect", lambda *a, **k: FakeConn())
    monkeypatch.setattr(backtest, "report", lambda conn, run_id, schema: None)
    assert client().get("/api/backtests/99").status_code == 404
    assert client().get("/api/backtests/0").status_code == 422


def test_starting_a_run_needs_the_checker_role_and_reading_one_the_auditor_role():
    assert required_role("POST", "/api/backtests") == "checker"
    assert required_role("GET", "/api/backtests") == "auditor"
    assert required_role("GET", "/api/backtests/3") == "auditor"


def test_the_public_demo_refuses_uploads_and_runs_but_serves_the_sample(monkeypatch):
    def no_db(*_a, **_k):
        raise AssertionError("a refused action must not reach Db2")

    monkeypatch.setattr("asof.db.connect", no_db)
    app = create_app(Settings(_env_file=None, asof_public_demo=True, llm_provider="replay"), gate=FakeGate(),
                     assistant=FakeAssistant(), rate_limit=50, read_limit=50)
    c = TestClient(app, client=("127.0.0.1", 51000), raise_server_exceptions=False)
    r = c.post("/api/backtests", content=backtest.SAMPLE_CSV.read_bytes(), headers=TEXT_CSV)
    assert r.status_code == 403
    assert r.json()["detail"].startswith("Disabled in the public demo: uploading and running a backtest")
    assert "quickstart" in r.json()["detail"]
    assert c.get("/api/backtests/sample").status_code == 200


def test_the_backtest_page_is_a_console_tab_and_renders_only_through_the_escaping_template():
    c = client()
    index = c.get("/ui/")
    assert index.status_code == 200 and 'href="#/backtest" data-route="backtest"' in index.text
    js = c.get("/ui/app.js").text
    assert "backtest: Backtest" in js and "async function Backtest(" in js
    section = js[js.index("// ---------- Backtest ----------"):js.index("// ---------- Analytics ----------")]
    assert "innerHTML" not in section and "insertAdjacentHTML" not in section and "eval(" not in section
    assert '"content-type": "text/csv"' in section  # the upload is the CSV itself, like the PDF upload
    assert "/api/backtests/sample" in section and "health.demo" in section
    assert re.search(r"\.bt-stats\s*\{", (UI / "app.css").read_text(encoding="utf-8"))
