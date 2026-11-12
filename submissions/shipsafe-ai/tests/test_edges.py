"""Failure paths and edge cases, each driven by a real condition: an unreachable Db2 port, a closed
connection, malformed files, a real broken test suite, an unknown model name, a non-Python project."""

import datetime
import json
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from shipsafe.agents import FixCrew
from shipsafe.analyzers.base import SafeExecutionBoundary
from shipsafe.analyzers.dependencies import DependencyAnalyzer
from shipsafe.analyzers.external import _line_of, run_pip_audit
from shipsafe.analyzers.quality import QualityAnalyzer
from shipsafe.analyzers.security import MAX_FILE_BYTES, SecurityAnalyzer
from shipsafe.analyzers.tests import TestRunnerAnalyzer as RunnerAnalyzer
from shipsafe.api import create_app
from shipsafe.api.markdown import markdown_from_rows
from shipsafe.config import LlmConfig
from shipsafe.db2 import Db2Repository
from shipsafe.db2.pool import ConnectionPool
from shipsafe.db2.repository import connect_db2
from shipsafe.db2sql import Db2SqlChecker
from shipsafe.discovery import ProjectDiscovery
from shipsafe.findings.normalizer import FindingNormalizer
from shipsafe.guard import GuardIssue
from shipsafe.knowledge import HashingEmbeddings, PolicyKnowledgeBase, build_embeddings
from shipsafe.llm import ModelUnavailable, ollama_status, require_models
from shipsafe.models import Finding
from shipsafe.orchestration import AssessmentOrchestrator
from shipsafe.security import issue_token, role_allows
from shipsafe.services import ShipSafeServices, _short
from tests.conftest import FIXTURES


def down(config):
    """Config pointing at a closed port: a real, unreachable Db2."""
    return replace(config, db2=replace(config.db2, port=1, connect_timeout=2))


# ------------------------------------------------------------- services
def test_guard_still_answers_when_db2_is_down(config, granite, tmp_path):
    svc = ShipSafeServices(down(config), workspace_root=str(tmp_path))
    r = svc.check_code("import os\nos.system(cmd)\n", "x.py")
    assert r["verdict"] == "block"
    assert any(n.startswith("Policy citations skipped") for n in r["notes"])
    assert any(n.startswith("Not logged to Db2") for n in r["notes"])
    st = svc.status()
    assert st["db2"]["connected"] is False and st["ollama"]["running"]


def test_services_files_and_search(services, tmp_path):
    svc = ShipSafeServices(services.config, workspace_root=str(tmp_path))
    (tmp_path / "big.py").write_text("x = 1\n" * 80_000, encoding="utf-8")
    assert svc.check_files(["big.py"])["files"][0]["error"].startswith("file too large")
    assert services.search_standards("pickle untrusted data", top_k=1)[0]["doc_id"] == "POL-SEC-004"
    assert _short(Exception("bad PWD=secret; x")) == "bad PWD=***; x" and _short(Exception()) == "Exception"


# ------------------------------------------------------------ repository
def test_connect_retries_then_reports(config):
    t = time.perf_counter()
    with pytest.raises(ConnectionError):
        connect_db2(replace(config.db2, port=1, connect_timeout=1), retries=2, base_delay=0.05)
    assert time.perf_counter() - t < 20


def test_repository_failure_paths_on_a_closed_connection(repo, caplog):
    repo.conn.close()
    with pytest.raises(Exception):
        repo.initialize_schema()
    repo.audit("x", "y", "z")  # logs, never raises
    assert "audit write failed" in caplog.text
    with pytest.raises(Exception):
        repo.purge_history(30)


def test_pool_drops_a_connection_that_dies_during_use(config, db2_schema):
    pool = ConnectionPool(config.db2, size=1)
    with pool.repository() as r:
        r.conn.close()      # dies while checked out: must not go back to the pool
    with pool.repository() as r2:
        assert r2.ping() >= 0
    pool.close()


# ----------------------------------------------------------- SQL checker
def test_sql_suggestions_degrade_gracefully(repo):
    from sqlalchemy import create_engine

    broken = Db2SqlChecker(repo, engine=create_engine("ibm_db_sa://u:p@127.0.0.1:1/NOPE"))
    r = broken.check("SELECT CLIENTZ FROM GUARD_EVENTS WHERE TS > ?")
    assert r.issues[0].code == "SQL0206N" and r.issues[0].suggestion == ""
    assert Db2SqlChecker(repo)._suggest(-104, 'token "SELEC" was unexpected') == ""


# ------------------------------------------------------------- analyzers
def test_quality_analyzer_on_real_files(tmp_path):
    (tmp_path / "broken.py").write_text("def f(:\n", encoding="utf-8")
    (tmp_path / "bare.py").write_text("try:\n    x()\nexcept:\n    pass\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "skip.py").write_text("def f(:\n", encoding="utf-8")
    run, findings = QualityAnalyzer(SafeExecutionBoundary(str(tmp_path))).scan("asm_q", target_scope=["broken.py", "bare.py"])
    assert {f.rule_id for f in findings} == {"E999-SYNTAX", "E722-BARE-EXCEPT"}


def test_security_analyzer_scope_and_skips(tmp_path):
    (tmp_path / "a.py").write_text("eval(x)\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("eval(y)\n", encoding="utf-8")
    (tmp_path / "venv").mkdir()
    (tmp_path / "venv" / "c.py").write_text("eval(z)\n", encoding="utf-8")
    (tmp_path / "huge.py").write_text("x = 1\n" * (MAX_FILE_BYTES // 6 + 10), encoding="utf-8")
    run, findings = SecurityAnalyzer(SafeExecutionBoundary(str(tmp_path))).scan("asm_s", target_scope=["a.py", "huge.py"])
    assert [f.file_path for f in findings] == ["a.py"]


def test_test_runner_skip_and_broken_suite(tmp_path):
    run, _ = RunnerAnalyzer(SafeExecutionBoundary(str(tmp_path))).scan("asm_t")
    assert run.status == "skipped"
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "test_x.py").write_text("import module_that_does_not_exist\n", encoding="utf-8")
    run, findings = RunnerAnalyzer(SafeExecutionBoundary(str(tmp_path))).scan("asm_t2")
    assert findings and findings[0].severity in ("high", "critical")


def test_dependency_and_pip_audit_edges(tmp_path):
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "requirements.txt").write_text("pyyaml==5.1\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("# only a comment\n\nrequests==2.31.0\n", encoding="utf-8")
    run, findings = DependencyAnalyzer(SafeExecutionBoundary(str(tmp_path))).scan("asm_d")
    assert findings == []  # the .venv manifest is ignored, requests 2.31.0 is not in the advisory list
    assert _line_of("requirements.txt", "x", {}) == 1
    assert _line_of("missing.txt", "x", {"_root": str(tmp_path)}) == 1
    (tmp_path / "requirements.txt").write_text("this-package-does-not-exist-shipsafe==0.0.1\n", encoding="utf-8")
    run, findings = run_pip_audit(SafeExecutionBoundary(str(tmp_path)), "asm_pa2")
    assert findings == [] and run.status in ("failed", "passed")


def test_safe_execution_cwd_and_errors(tmp_path):
    (tmp_path / "sub").mkdir()
    b = SafeExecutionBoundary(str(tmp_path))
    assert b.validate_path_containment("sub") == (tmp_path / "sub").resolve()
    code, out, _, _ = b.run_command([sys.executable, "-c", "import os; print(os.getcwd())"], cwd="sub")
    assert code == 0 and out.strip().endswith("sub")
    assert b.run_command([sys.executable, "-c", "print(1)", 123])[0] == -1  # invalid argument type


# ------------------------------------------------------------- discovery
def test_discovery_of_non_python_project(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "x"}', encoding="utf-8")
    (tmp_path / "app.ts").write_text("export const a = 1;\n", encoding="utf-8")
    (tmp_path / "vitest.config.ts").write_text("export default {}\n", encoding="utf-8")
    (tmp_path / "go.mod").write_text("module x\n", encoding="utf-8")
    (tmp_path / "pom.xml").write_text("<project/>\n", encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (tmp_path / "main.tf").write_text("terraform {}\n", encoding="utf-8")
    (tmp_path / "util.js").write_text("module.exports = 1;\n", encoding="utf-8")
    d = ProjectDiscovery(str(tmp_path)).discover().to_dict()
    assert {"typescript", "go", "java", "javascript"} <= {l.lower() for l in d["languages"]}
    assert "sast_bandit" in d["skipped_checks"]
    assert "infrastructure_trivy" in d["applicable_checks"]


# ---------------------------------------------------------------- engine
def test_engine_without_db2_and_on_a_non_python_project(config, tmp_path):
    (tmp_path / "index.js").write_text("document.body.innerHTML = location.hash;\n", encoding="utf-8")
    res = AssessmentOrchestrator(replace(config, pip_audit="always"), None, None).run_assessment(str(tmp_path), profile="pre-pr")
    assert not res.persisted and any("not saved" in w for w in res.warnings)
    assert any(f.rule_id == "JS-INNERHTML" for f in res.findings)
    assert {t.tool_name for t in res.tool_runs if t.status == "skipped"} >= {"bandit", "dependencies", "tests"}


def test_engine_rolls_back_and_reports_when_saving_fails(config, db2_schema, granite):
    repo = Db2Repository(config.db2, init_schema=False)
    kb = PolicyKnowledgeBase(repo, config.embedding_provider, config.embedding_dimension, config.llm)
    repo.conn.close()  # Db2 goes away after the scan starts
    res = AssessmentOrchestrator(config, repo, kb).run_assessment(str(FIXTURES / "vulnerable_project"), profile="quick")
    assert not res.persisted
    assert any("Policy retrieval unavailable" in w for w in res.warnings)
    assert any("not saved to Db2" in w for w in res.warnings)


def test_engine_with_pip_audit_always(config, tmp_path):
    (tmp_path / "requirements.txt").write_text("PyYAML==5.3.1\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    res = AssessmentOrchestrator(replace(config, pip_audit="always", use_bandit=False), None, None).run_assessment(
        str(tmp_path), profile="quick")
    assert any(t.tool_name == "pip-audit" for t in res.tool_runs)


# ---------------------------------------------------------- small units
def test_normalizer_groups_and_merge_order():
    low = Finding.create("a", "bandit", "B602", "security", "low", "low", "t", "d", file_path="f.py", line_start=1)
    high = Finding.create("a", "rules", "CMD-SHELL", "security", "high", "high", "t2", "d", file_path="f.py", line_start=1)
    merged = FindingNormalizer.deduplicate([low, high])
    assert len(merged) == 1 and merged[0].severity == "high"
    g = FindingNormalizer.group_by_severity([low, high])
    assert len(g["low"]) == 1 and len(g["high"]) == 1
    assert set(FindingNormalizer.group_by_category([low])) == {"security"}


def test_embeddings_and_models():
    emb = build_embeddings("hashing", 16)
    assert isinstance(emb, HashingEmbeddings) and len(emb.embed_documents(["a", "b"])) == 2
    with pytest.raises(ValueError):
        build_embeddings("openai")
    assert role_allows("admin", "viewer") and not role_allows("nobody", "viewer")
    assert markdown_from_rows({"ASSESSMENT_ID": "a", "PROJECT_ID": "prj", "PROJECT_NAME": "p", "CRITICAL_COUNT": 0, "HIGH_COUNT": 0, "MEDIUM_COUNT": 0, "LOW_COUNT": 0, "STATUS": "PASS", "GATE_REASON": "",
                               "PROFILE": "quick", "STARTED_AT": 0}, [], [])


def test_model_availability_errors(granite):
    with pytest.raises(ModelUnavailable, match="not reachable"):
        require_models(LlmConfig(host="http://127.0.0.1:1"))
    with pytest.raises(ModelUnavailable, match="not installed"):
        require_models(replace(granite, chat_model="granite-does-not-exist:1b"))
    with pytest.raises(ModelUnavailable, match="Embedding model"):
        require_models(replace(granite, embed_model="nope-embed:1"), chat=False, embed=True)
    assert ollama_status(LlmConfig(host="ftp://x"))["running"] is False


def test_fix_crew_without_policy_lookup(granite):
    issue = GuardIssue("CODE-EVAL", "critical", "security", "eval", 1, "eval(x)", "why", "fix")
    assert FixCrew(granite)._standards([issue]) == ("(none available)", [])


def test_policy_store_rejects_empty_directory(repo, config, granite, tmp_path):
    kb = PolicyKnowledgeBase(repo, config.embedding_provider, config.embedding_dimension, config.llm)
    with pytest.raises(FileNotFoundError):
        kb.ingest_directory(str(tmp_path))


# -------------------------------------------------------------- API edges
def test_api_when_db2_is_down_and_without_auth(config, tmp_path, monkeypatch):
    import shipsafe.api.app as app_mod

    monkeypatch.setattr(app_mod, "WEB_DIST", tmp_path / "no-ui-built")
    cfg = replace(down(config), auth_enabled=False, cors_origins=["http://localhost:5173"])
    with TestClient(create_app(cfg, ConnectionPool(cfg.db2, size=1, connect_retries=1))) as client:
        assert client.get("/api/ready").status_code == 503
        assert client.get("/api/me").json()["role"] == "admin"          # local development principal
        assert client.get("/api/overview").status_code == 503            # Db2Unavailable -> JSON 503
        assert "web UI" in client.get("/").text
        r = client.options("/api/health", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
        assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert app_mod._jsonable(b"\xffok") == "�ok"
    assert app_mod._jsonable(datetime.date(2026, 1, 2)) == "2026-01-02"


def test_api_token_edges_and_spa_files(config, db2_schema):
    pool = ConnectionPool(config.db2, size=1)
    tid, token, digest = issue_token()
    with pool.repository() as r:
        r.create_token(tid, "edge-admin", "admin", digest)
    with TestClient(create_app(config, pool)) as client:
        h = {"Authorization": f"Bearer {token}"}
        assert client.delete(f"/api/tokens/{tid}", headers=h).status_code == 400   # own token
        assert client.delete("/api/tokens/doesnotexist", headers=h).status_code == 404
        assert client.get("/api/assessments/missing/report", headers=h).status_code == 404
        assert client.get("/favicon.svg").status_code in (200, 404)
        assert client.get("/some/client/route").status_code == 200              # SPA fallback


# ------------------------------------------------------- jobs and CLI edges
def test_job_manager_degraded_failed_and_eviction(config, tmp_path):
    from shipsafe.api.jobs import JobManager, RateLimiter

    events = []
    jm = JobManager(replace(down(config), use_bandit=False), ConnectionPool(down(config).db2, size=1, connect_retries=1),
                    kb_factory=lambda repo: (_ for _ in ()).throw(RuntimeError("kb down")),
                    audit=lambda *a, **k: events.append(a[1]), keep=1)
    ok = jm.submit(str(FIXTURES / "clean_project"), "quick", "tester")
    bad = jm.submit(str(tmp_path / "does-not-exist"), "quick", "tester")
    for _ in range(300):
        j = jm.get(bad["job_id"])
        if j and j["status"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert jm.get(ok["job_id"]) is None          # evicted (keep=1)
    assert j["status"] in ("done", "failed")
    assert jm.list() if hasattr(jm, "list") else True
    jm.shutdown()
    rl = RateLimiter(1)
    assert rl.allow("k") and not rl.allow("k")
    rl._hits["k"][0] -= 120                      # an old hit leaves the window
    assert rl.allow("k")


def test_cli_edges(monkeypatch, capsys, db2_schema, granite, tmp_path):
    from tests.test_cli import run

    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:1")
    import importlib, shipsafe.config as c
    code, out = run(monkeypatch, capsys, "setup", "--env-file", tmp_path / "a.env")
    assert code == 1 and "Ollama is not reachable" in out
    monkeypatch.setenv("OLLAMA_HOST", granite.host)
    monkeypatch.setenv("SHIPSAFE_CHAT_MODEL", "granite-does-not-exist:1b")
    code, out = run(monkeypatch, capsys, "setup", "--env-file", tmp_path / "b.env")
    assert code == 1 and "is missing" in out
    import os
    ollama_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama"
    monkeypatch.setenv("PATH", f"{ollama_dir}{os.pathsep}{os.environ['PATH']}")
    code, out = run(monkeypatch, capsys, "setup", "--pull", "--env-file", tmp_path / "c.env")
    assert code == 1 and "Could not pull" in out
    monkeypatch.setenv("SHIPSAFE_CHAT_MODEL", granite.chat_model)
    code, out = run(monkeypatch, capsys, "assessment", "show", "asm_missing")
    assert code == 1 and "not found" in out
    code, out = run(monkeypatch, capsys, "doctor")
    assert code == 0
    monkeypatch.setenv("DB2_PORT", "1")
    code, out = run(monkeypatch, capsys, "doctor")
    assert code == 1 and "[FAIL] IBM Db2 connection" in out
    r = subprocess.run([sys.executable, "-m", "shipsafe.cli", "--help"], capture_output=True, text=True)
    assert r.returncode == 0 and "connect" in r.stdout


def test_mcp_services_default(monkeypatch, tmp_path):
    from shipsafe import mcp_server

    monkeypatch.setattr(mcp_server, "_services", None)
    monkeypatch.setenv("SHIPSAFE_WORKSPACE", str(tmp_path))
    assert mcp_server.services().workspace_root == tmp_path.resolve()
    monkeypatch.setattr(mcp_server, "_services", None)


def test_serve_command_starts_and_answers(config, db2_schema, tmp_path):
    import os
    import socket
    import urllib.request

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "DB2_SCHEMA": config.db2.schema, "SHIPSAFE_ALLOWED_ROOTS": str(FIXTURES)}
    proc = subprocess.Popen([sys.executable, "-m", "shipsafe.cli", "serve", "--port", str(port)], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True)
    try:
        for _ in range(120):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as r:  # noqa: S310
                    assert json.loads(r.read())["status"] == "ok"
                    break
            except OSError:
                time.sleep(0.5)
        else:
            pytest.fail("shipsafe serve did not start")
    finally:
        proc.terminate()
        proc.wait(timeout=30)
    bad = subprocess.run([sys.executable, "-m", "shipsafe.cli", "serve", "--port", str(port)],
                         env={**env, "SHIPSAFE_LOG_FORMAT": "xml"}, capture_output=True, text=True, timeout=60)
    assert bad.returncode == 2 and "Configuration errors" in bad.stdout
