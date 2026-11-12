"""Platform pieces on real resources: Db2 connection pool recovery, git discovery, pip-audit against
PyPI/OSV, path allowlisting, structured logging, and the remaining API routes."""

import json
import logging
import subprocess
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from shipsafe.analyzers.base import SafeExecutionBoundary, redact_secrets
from shipsafe.analyzers.external import run_pip_audit
from shipsafe.db2.pool import ConnectionPool, Db2Unavailable
from shipsafe.discovery import ProjectDiscovery
from shipsafe.logging_setup import JsonFormatter, configure_logging
from shipsafe.security import issue_token
from shipsafe.security.paths import TargetNotAllowed, list_workspaces, resolve_target
from tests.conftest import FIXTURES


# ------------------------------------------------------------------- pool
def test_pool_replaces_a_dead_connection(config, db2_schema):
    pool = ConnectionPool(config.db2, size=1)
    with pool.repository() as repo:
        first = repo
        repo.ping()
    first.conn.close()                     # the server-side session is gone, as after a Db2 restart
    with pool.repository() as repo:
        assert repo is not first           # stale connection detected by ping and replaced
        assert repo.ping() >= 0
    assert pool.healthy()
    pool.close()


def test_pool_reports_unreachable_db2(config):
    pool = ConnectionPool(replace(config.db2, port=1, connect_timeout=2), size=1, connect_retries=1)
    with pytest.raises(Db2Unavailable):
        with pool.repository():
            pass
    assert pool.healthy() is False


def test_pool_times_out_when_exhausted(config, db2_schema):
    pool = ConnectionPool(config.db2, size=1, checkout_timeout=0.2)
    with pool.repository():
        with pytest.raises(Db2Unavailable, match="Timed out"):
            with pool.repository():
                pass
    pool.close()


# ------------------------------------------------------------- discovery
def test_discovery_reads_real_git_state(tmp_path):
    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "init")
    (tmp_path / "app.py").write_text("print('changed')\n", encoding="utf-8")
    d = ProjectDiscovery(str(tmp_path)).discover().to_dict()
    assert d["current_branch"] == "main" and len(d["head_commit"]) == 12
    assert "app.py" in d["changed_files"]
    assert "python" in [lang.lower() for lang in d["languages"]]


# ------------------------------------------------------------- pip-audit

def test_pip_audit_against_pypi_osv(tmp_path):
    (tmp_path / "requirements.txt").write_text("PyYAML==5.3.1\n", encoding="utf-8")
    run, findings = run_pip_audit(SafeExecutionBoundary(str(tmp_path)), "asm_pa")
    assert run.tool_name == "pip-audit"
    if run.status == "failed" and not findings:
        pytest.fail(f"pip-audit could not reach PyPI/OSV: {run.message}")
    assert any(f.rule_id == "CVE-2020-14343" and f.line_start == 1 for f in findings)


def test_pip_audit_without_manifest(tmp_path):
    run, findings = run_pip_audit(SafeExecutionBoundary(str(tmp_path)), "asm_pb")
    assert run.status == "skipped" and findings == []


# ------------------------------------------------------- safe execution
def test_safe_execution_boundary(tmp_path):
    b = SafeExecutionBoundary(str(tmp_path), max_timeout_seconds=5)
    with pytest.raises(PermissionError):
        b.validate_path_containment("../outside")
    with pytest.raises(ValueError):
        b.run_command([])
    assert b.run_command(["definitely-not-a-real-binary-xyz"])[0] == 127
    import sys
    code, out, err, _ = b.run_command([sys.executable, "-c", "print('token=abcdefgh12345')"])
    assert code == 0 and "abcdefgh12345" not in out
    code, *_ = b.run_command([sys.executable, "-c", "import time; time.sleep(10)"], timeout=1)
    assert code == -1
    assert redact_secrets("") == ""


# ------------------------------------------------------------ allowlisting
def test_resolve_target_and_workspaces():
    roots = [str(FIXTURES)]
    assert resolve_target("clean_project", roots) == (FIXTURES / "clean_project").resolve()
    assert resolve_target(str(FIXTURES / "clean_project"), roots).name == "clean_project"
    for bad in ("", "a\x00b", "../..", str(FIXTURES.parent), "clean_project/src/service.py"):
        with pytest.raises(TargetNotAllowed):
            resolve_target(bad, roots)
    names = {w["name"] for w in list_workspaces(roots + ["/definitely/missing"])}
    assert {"clean_project", "vulnerable_project"} <= names


# ----------------------------------------------------------------- logging
def test_json_logging_redacts_secrets(capsys):
    configure_logging("json", "INFO")
    log = logging.getLogger("shipsafe.test")
    log.info("connect PWD=hunter2; token %s", "ss_abcdef123456", extra={"request_id": "r1", "status": 200})
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        log.exception("failed")
    lines = [json.loads(l) for l in capsys.readouterr().err.strip().splitlines()]
    assert lines[0]["msg"] == "connect PWD=***; token ss_***" and lines[0]["request_id"] == "r1"
    assert "RuntimeError" in lines[1]["exc"]
    configure_logging("text", "WARNING")
    assert isinstance(JsonFormatter(), logging.Formatter)


# --------------------------------------------------------------- API routes
@pytest.fixture(scope="module")
def api(config, db2_schema):
    from shipsafe.api import create_app

    pool = ConnectionPool(config.db2, size=2)
    tid, token, digest = issue_token()
    with pool.repository() as repo:
        repo.create_token(tid, "platform-admin", "admin", digest)
    client = TestClient(create_app(replace(config, use_bandit=False), pool))
    yield client, {"Authorization": f"Bearer {token}"}
    pool.close()


def test_api_listing_compare_and_reindex(api):
    client, h = api
    a = client.post("/api/scans", json={"target": "vulnerable_project", "profile": "quick"}, headers=h).json()
    b = client.post("/api/scans", json={"target": "clean_project", "profile": "quick"}, headers=h).json()
    import time
    for _ in range(600):
        jobs = [client.get(f"/api/scans/{j['job_id']}", headers=h).json() for j in (a, b)]
        if all(j["status"] in ("done", "failed") for j in jobs):
            break
        time.sleep(0.1)
    ids = [j["assessment_id"] for j in jobs]
    assert client.get("/api/scans", headers=h).json()["items"]
    assert client.get("/api/assessments?limit=5", headers=h).json()["items"]
    cmp = client.get(f"/api/compare?previous={ids[0]}&current={ids[1]}", headers=h)
    assert cmp.status_code == 200 and "resolved_count" in cmp.json()
    assert client.get("/api/compare?previous=nope&current=nope2", headers=h).status_code == 404
    assert client.get("/api/assessments/nope", headers=h).status_code == 404
    assert client.get(f"/api/assessments/{ids[0]}/report?format=json", headers=h).json()
    assert client.get(f"/api/assessments/{ids[0]}/report?format=pdf", headers=h).status_code == 422
    assert client.get("/api/scans/nope", headers=h).status_code == 404
    assert any(w["name"] == "clean_project" for w in client.get("/api/workspaces", headers=h).json()["items"])
    assert client.get("/api/policies", headers=h).json()["chunks"] > 0
    re = client.post("/api/policies/reindex", headers=h)
    assert re.status_code == 200 and "POL-DB2-001" in re.json()["documents"]
    assert client.get("/api/audit?action=policies.reindexed", headers=h).json()["items"]
    assert client.get("/", headers=h).status_code == 200
    assert client.get("/api/does-not-exist", headers=h).status_code == 404
