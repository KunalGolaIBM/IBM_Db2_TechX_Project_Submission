"""The headline banner (asof/headline.py): every number recomputed from the published result files and compared with
the README and the unseen-results report, so the banner and the docs cannot drift; the latest run per split is found
without naming a file; a missing file drops only its number."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_api import FakeAssistant, FakeGate

from asof import headline
from asof.api import create_app
from asof.config import Settings
from asof.eval import FROZEN
from asof.eval.unseen.run import score

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "docs" / "eval"
WORDS = {"nine": 9, "eight": 8, "ten": 10}


def latest_totals() -> tuple[int, int, int, int, int]:
    """The README's Safety figures, recomputed here independently: the newest run of each frozen split."""
    newest: dict[str, dict] = {}
    for p in EVAL.glob("*.json"):
        run = json.loads(p.read_text())
        s = run.get("split")
        if s in FROZEN and run["cases_sha256"] == FROZEN[s] and (s not in newest or run["started_at"] > newest[s]["started_at"]):
            newest[s] = run
    o = [r["summary"]["overall"] for r in newest.values()]
    return (len(newest), sum(x["false_allows"] for x in o), sum(x["wrong_drafts"] for x in o),
            sum(x["false_blocks"] for x in o), sum(x["correct_drafts"] for x in o))


def test_the_frozen_number_matches_the_files_and_the_readme():
    n, fa, wrong, fb, correct = latest_totals()
    item = next(i for i in headline.compute() if i["id"] == "frozen")
    assert (item["splits"], item["false_allows"], item["wrong_drafts"], item["false_blocks"], item["correct_drafts"]) \
        == (n, fa, wrong, fb, correct) and n == len(FROZEN)
    assert f"{fa} of {wrong} wrong drafts released" in item["text"] and f"{fb} of {correct} correct" in item["text"]
    readme = (ROOT / "README.md").read_text()
    m = re.search(r"Latest run: (\d+) of (\d+) wrong drafts released across (\w+) frozen splits, (\d+) of (\d+) correct "
                  r"drafts (?:held|stopped)", readme)
    assert m, "the README's Safety row changed shape; update this test with it"
    assert (int(m[1]), int(m[2]), WORDS.get(m[3], m[3]), int(m[4]), int(m[5])) == (fa, wrong, n, fb, correct), \
        "the README's Safety row and the latest frozen-split runs disagree"


def test_the_unseen_number_matches_the_files_and_the_published_report():
    runs = [json.loads(p.read_text()) for p in (EVAL / "unseen").glob("run-*.json")]
    first = next(r for r in runs if r["first_run"])
    grades = json.loads((EVAL / "unseen" / "grades.json").read_text())[f"run-{first['run']}"]
    asof, plain = score(first["records"], grades, "asof"), score(first["records"], grades, "plain_judge")
    item = next(i for i in headline.compute() if i["id"] == "unseen")
    assert item["asof"] == {"false_allows": asof["false_allow"]["k"], "wrong_drafts": asof["false_allow"]["n"],
                            "false_blocks": asof["false_block"]["k"], "correct_drafts": asof["false_block"]["n"]}
    assert item["plain_judge"]["false_blocks"] == plain["false_block"]["k"]
    report = (ROOT / "docs" / "eval" / "unseen-results.md").read_text()
    section = report.split("### First run (final)", 1)[1].split("###", 1)[0]
    for label, metric in (("False allow", "false_allow"), ("False block", "false_block")):
        row = next(line for line in section.splitlines() if line.startswith(f"| {label}:"))
        published = [tuple(map(int, c)) for c in re.findall(r"(\d+) of (\d+),", row)]
        assert published[1:] == [(plain[metric]["k"], plain[metric]["n"]), (asof[metric]["k"], asof[metric]["n"])], label
    assert f"AsOf made the right call on {asof['ideal']['k']} of {asof['ideal']['n']} drafts" in item["text"]
    assert f"a plain LLM judge on {plain['ideal']['k']} of {plain['ideal']['n']}" in item["text"]
    assert f"let {asof['false_allow']['k']} of {asof['false_allow']['n']} wrong drafts through" in item["text"]


def test_the_copy_in_the_package_matches_the_files():
    """Installed, there is no docs/ folder: the banner reads data/headline.json. Regenerate it after a new run with
    `python -m asof.headline`."""
    shipped = json.loads(headline.GENERATED.read_text())["items"]
    assert shipped == headline.compute(), "data/headline.json is stale: run python -m asof.headline"


@pytest.fixture
def eval_copy(tmp_path) -> Path:
    shutil.copytree(EVAL, tmp_path / "eval")
    return tmp_path / "eval"


def test_the_latest_run_of_each_split_is_picked_without_naming_a_file(eval_copy):
    newest = max((json.loads(p.read_text()) for p in eval_copy.glob("test__*.json")
                  if json.loads(p.read_text())["cases_sha256"] == FROZEN["test"]), key=lambda r: r["started_at"])
    later = newest | {"started_at": "2099-01-01T00:00:00+00:00", "git_commit": "fffffff"}
    later["summary"] = {"overall": newest["summary"]["overall"] | {"false_allows": 3}}
    (eval_copy / "test__openrouter__any-model__fffffff.json").write_text(json.dumps(later))
    other = later | {"started_at": "2100-01-01T00:00:00+00:00", "cases_sha256": "0" * 64}  # not the pinned case file
    other["summary"] = {"overall": newest["summary"]["overall"] | {"false_allows": 99}}
    (eval_copy / "test__openrouter__any-model__eeeeeee.json").write_text(json.dumps(other))
    (eval_copy / "broken__x.json").write_text("{not json")
    runs = headline.frozen_runs(eval_copy)
    assert runs["test"]["file"] == "test__openrouter__any-model__fffffff.json"
    item = headline.frozen_result(eval_copy)
    assert item is not None and item["false_allows"] == latest_totals()[1] + 3


def test_a_missing_split_drops_the_frozen_number_only(eval_copy):
    for p in eval_copy.glob("list-test__*.json"):
        p.unlink()
    items = headline.compute(eval_copy)
    assert [i["id"] for i in items] == ["unseen"]


@pytest.mark.parametrize("missing", ["grades.json", "run-*.json"])
def test_a_missing_unseen_file_drops_the_unseen_number_only(eval_copy, missing):
    for p in (eval_copy / "unseen").glob(missing):
        p.unlink()
    assert [i["id"] for i in headline.compute(eval_copy)] == ["frozen"]


def test_an_ungraded_rewrite_drops_the_unseen_number(eval_copy):
    grades = json.loads((eval_copy / "unseen" / "grades.json").read_text())
    grades["run-1"].pop(next(iter(grades["run-1"])))
    (eval_copy / "unseen" / "grades.json").write_text(json.dumps(grades))
    assert headline.unseen_result(eval_copy) is None


def test_no_files_at_all_means_no_banner(tmp_path):
    assert headline.compute(tmp_path) == []


def test_an_installed_package_reads_the_generated_copy_and_fails_soft_without_it(monkeypatch, tmp_path):
    monkeypatch.setattr(headline, "EVAL_DIR", tmp_path / "no-docs")
    headline.banner.cache_clear()
    try:
        assert [i["id"] for i in headline.banner()] == ["frozen", "unseen"]
        monkeypatch.setattr(headline, "GENERATED", tmp_path / "missing.json")
        headline.banner.cache_clear()
        assert headline.banner() == []
    finally:
        headline.banner.cache_clear()


def test_healthz_serves_the_banner_and_both_pages_render_it(monkeypatch):
    from asof import db

    monkeypatch.setattr("asof.db.connect", lambda *a, **k: (_ for _ in ()).throw(db.DatabaseError("down", "08001")))
    body = TestClient(create_app(Settings(_env_file=None), gate=FakeGate(), assistant=FakeAssistant())).get("/healthz").json()
    assert [i["id"] for i in body["headline"]] == ["frozen", "unseen"]
    assert all(set(i) == {"id", "text", "short", "href"} and i["href"].startswith("https://github.com/JustJay7/asof/")
               for i in body["headline"])
    ui = ROOT / "src" / "asof" / "ui"
    assert "headlineView()" in (ui / "app.js").read_text() and "health.headline" in (ui / "app.js").read_text()
    assert "headline(health.headline)" in (ui / "chat.js").read_text() and 'id="headline"' in (ui / "chat.html").read_text()


def test_the_banner_links_point_at_headings_that_exist():
    assert (ROOT / "docs" / "evaluation.md").read_text().count("\n## The frozen test splits\n") == 1
    assert (ROOT / "docs" / "eval" / "unseen-results.md").is_file()
