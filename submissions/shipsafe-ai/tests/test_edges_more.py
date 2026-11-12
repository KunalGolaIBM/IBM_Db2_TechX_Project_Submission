"""The last reachable branches, each with a real input: crashing test suites, unreadable files,
a scan job whose knowledge base fails, CLI output for new findings, and server start-up."""

import time
from dataclasses import replace

import pytest

from shipsafe.analyzers.ast_rules import analyze_python
from shipsafe.analyzers.base import SafeExecutionBoundary
from shipsafe.analyzers.dependencies import DependencyAnalyzer
from shipsafe.analyzers.quality import QualityAnalyzer
from shipsafe.analyzers.secrets import SecretAnalyzer
from shipsafe.analyzers.tests import TestRunnerAnalyzer as RunnerAnalyzer
from shipsafe.db2.pool import ConnectionPool
from shipsafe.db2sql import Db2SqlChecker
from shipsafe.discovery import ProjectDiscovery
from tests.conftest import FIXTURES


def test_more_rule_branches():
    assert [h.rule_id for h in analyze_python('cur.execute(f"SELECT * FROM T WHERE A = {a[0]}")')] == ["SQLI-DYNAMIC"]
    src = ("def f(conn, x):\n    stmt = ibm_db.prepare(conn, 'SELECT A FROM T WHERE I = ?')\n"
           "    res = ibm_db.execute(stmt, (x,))\n    return ibm_db.fetch_tuple(res)\n")
    assert [(h.rule_id, h.line) for h in analyze_python(src)] == [("DB2-API-MISUSE", 4)]


def test_test_suite_that_dies_before_reporting(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "test_dies.py").write_text("import os\nos._exit(3)\n", encoding="utf-8")
    run, findings = RunnerAnalyzer(SafeExecutionBoundary(str(tmp_path))).scan("asm_die")
    assert findings[0].title == "Test Suite Could Not Run"


def test_unreadable_and_out_of_scope_files(tmp_path):
    (tmp_path / "notes.py").mkdir()                     # a directory named like a source file
    (tmp_path / "in.py").write_text("try:\n    a()\nexcept:\n    pass\n", encoding="utf-8")
    (tmp_path / "out.py").write_text("try:\n    a()\nexcept:\n    pass\n", encoding="utf-8")
    run, findings = QualityAnalyzer(SafeExecutionBoundary(str(tmp_path))).scan("asm_q2", target_scope=["in.py", "notes.py"])
    assert [f.file_path for f in findings] == ["in.py"]
    (tmp_path / "requirements.txt").write_bytes(b"\xff\xfe\x00bad")  # not UTF-8
    run, findings = DependencyAnalyzer(SafeExecutionBoundary(str(tmp_path))).scan("asm_d2")
    assert findings == []


def test_secret_scanner_skips_and_scope(tmp_path):
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "k.py").write_text('k = "AKIAABCDEFGHIJKLMNOP"\n', encoding="utf-8")
    (tmp_path / "logo.png").write_bytes(b"AKIAABCDEFGHIJKLMNOP")
    (tmp_path / "a.py").write_text('k = "AKIAABCDEFGHIJKLMNOP"\n', encoding="utf-8")
    (tmp_path / "b.py").write_text('k = "AKIAZZZZZZZZZZZZZZZZ"\n', encoding="utf-8")
    (tmp_path / "big.txt").write_text("x" * 600_000, encoding="utf-8")
    run, findings = SecretAnalyzer(SafeExecutionBoundary(str(tmp_path))).scan("asm_sec", target_scope=["a.py", "big.txt"])
    assert [f.file_path for f in findings] == ["a.py"]


def test_spec_files_detected(tmp_path):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "app.spec.ts").write_text("test('x', () => {})\n", encoding="utf-8")
    assert "vitest/jest" in ProjectDiscovery(str(tmp_path)).discover().to_dict()["test_frameworks"]


def test_sql_suggest_without_a_quoted_name(repo):
    assert Db2SqlChecker(repo)._suggest(-206, "no quoted identifier here") == ""


def test_scan_job_when_the_knowledge_base_fails(config, db2_schema):
    from shipsafe.api.jobs import JobManager

    def broken_kb(repo):
        raise RuntimeError("vector store offline")

    jm = JobManager(replace(config, use_bandit=False), ConnectionPool(config.db2, size=1), broken_kb, lambda *a, **k: None)
    job = jm.submit(str(FIXTURES / "clean_project"), "quick", "tester")
    for _ in range(600):
        j = jm.get(job["job_id"])
        if j["status"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert j["status"] == "done" and j["persisted"] if "persisted" in j else j["status"] == "done"
    jm.shutdown()


def test_scan_job_degraded_when_db2_is_down(config):
    from shipsafe.api.jobs import JobManager

    dead = replace(config.db2, port=1, connect_timeout=2)
    jm = JobManager(replace(config, use_bandit=False), ConnectionPool(dead, size=1, connect_retries=1),
                    lambda repo: None, lambda *a, **k: None)
    job = jm.submit(str(FIXTURES / "clean_project"), "quick", "tester")
    for _ in range(600):
        j = jm.get(job["job_id"])
        if j["status"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert j["status"] == "done" and any("unavailable" in w for w in j["warnings"])
    jm.shutdown()


def test_api_audit_survives_db2_outage(config, tmp_path):
    from fastapi.testclient import TestClient

    from shipsafe.api import create_app

    cfg = replace(config, db2=replace(config.db2, port=1, connect_timeout=2), auth_enabled=False, use_bandit=False)
    with TestClient(create_app(cfg, ConnectionPool(cfg.db2, size=1, connect_retries=1))) as client:
        r = client.post("/api/scans", json={"target": "clean_project", "profile": "quick"})
        assert r.status_code == 202  # the audit write failed, the request did not


def test_bootstrap_server(config, db2_schema, capsys):
    from shipsafe.cli import bootstrap_server

    pool = ConnectionPool(config.db2, size=1)
    with pool.repository() as repo:
        for t in repo.list_tokens():
            repo.revoke_token(t["TOKEN_ID"])
    bootstrap_server(config, pool)
    out = capsys.readouterr().out
    assert "[OK] IBM Db2" in out and "admin API token was created" in out
    bootstrap_server(config, pool)                      # second start: no new token
    assert "admin API token" not in capsys.readouterr().out
    pool.close()
    dead = ConnectionPool(replace(config.db2, port=1, connect_timeout=2), size=1, connect_retries=1)
    bootstrap_server(config, dead)
    assert "[WARN] IBM Db2 not reachable yet" in capsys.readouterr().out


def test_cli_compare_shows_new_findings_and_fix_diff(monkeypatch, capsys, db2_schema, granite, tmp_path):
    import re

    from tests.test_cli import run

    code, out = run(monkeypatch, capsys, "scan", "--target", FIXTURES / "clean_project", "--profile", "quick",
                    "--output", tmp_path / "a.md")
    first = re.findall(r"asm_[0-9a-f]{12}", (tmp_path / "a.md").read_text(encoding="utf-8"))[0]
    code, out = run(monkeypatch, capsys, "scan", "--target", FIXTURES / "vulnerable_project", "--profile", "quick",
                    "--output", tmp_path / "b.md")
    second = re.findall(r"asm_[0-9a-f]{12}", (tmp_path / "b.md").read_text(encoding="utf-8"))[0]
    code, out = run(monkeypatch, capsys, "assessment", "compare", first, second)
    assert "  + [CRITICAL]" in out
    (tmp_path / "w").mkdir()
    (tmp_path / "w" / "r.py").write_text('import os\nos.system(user_cmd)\n', encoding="utf-8")
    code, out = run(monkeypatch, capsys, "fix", "r.py", cwd=tmp_path / "w")
    assert "--- a/r.py" in out
