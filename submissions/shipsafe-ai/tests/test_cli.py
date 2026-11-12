"""Every CLI command through the real `shipsafe` entry point, on the live Db2 test schema and Granite."""

import json
import re
import subprocess
import sys

import pytest

from shipsafe import cli
from tests.conftest import FIXTURES


def run(monkeypatch, capsys, *args, cwd=None):
    if cwd:
        monkeypatch.chdir(cwd)
    monkeypatch.setattr(sys, "argv", ["shipsafe", *map(str, args)])
    code = 0
    try:
        cli.main()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 0
    out = capsys.readouterr()
    return code, out.out + out.err


@pytest.fixture(autouse=True)
def _live(db2_schema, granite):
    """All CLI tests talk to the live Db2 test schema and Granite."""


def test_help(monkeypatch, capsys):
    code, out = run(monkeypatch, capsys)
    assert code == 0 and "connect" in out and "setup" in out


def test_doctor_and_init_db(monkeypatch, capsys):
    code, out = run(monkeypatch, capsys, "doctor")
    assert code == 0 and "[OK]   IBM Db2" in out and "granite4:micro" in out
    code, out = run(monkeypatch, capsys, "init-db")
    assert code == 0 and "SP_PROJECT_RISK" in out


def test_check_command(monkeypatch, capsys):
    code, out = run(monkeypatch, capsys, "check", "vulnerable_project/src/api.py", "clean_project/src/service.py",
                    "nope.py", cwd=FIXTURES)
    assert code == 1 and "[BLOCK] vulnerable_project/src/api.py" in out and "Verdict: BLOCK" in out
    assert "[--]  nope.py: not a file" in out and "fix:" in out
    code, out = run(monkeypatch, capsys, "check", "clean_project/src/service.py", "--json", cwd=FIXTURES)
    assert code == 0 and json.loads(out)["verdict"] in ("clean", "warn")
    code, out = run(monkeypatch, capsys, "check", cwd=FIXTURES)
    assert code == 0 and "Nothing to check" in out


def test_check_staged_and_hook(monkeypatch, capsys, tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "bad.py").write_text("import os\nos.system(user_cmd)\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "bad.py"], check=True)
    code, out = run(monkeypatch, capsys, "check", "--staged", cwd=tmp_path)
    assert code == 1 and "CMD-SHELL" in out
    code, out = run(monkeypatch, capsys, "hook", cwd=tmp_path)
    hook = (tmp_path / ".git" / "hooks" / "pre-commit").read_text(encoding="utf-8")
    assert code == 0 and "shipsafe.cli check --staged" in hook
    (tmp_path / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\necho mine\n", encoding="utf-8")
    code, out = run(monkeypatch, capsys, "hook", cwd=tmp_path)
    assert code == 2 and "not overwriting" in out


def test_hook_outside_git(monkeypatch, capsys, tmp_path):
    code, out = run(monkeypatch, capsys, "hook", cwd=tmp_path)
    assert code == 2 and "Not a git repository" in out


def test_sql_command(monkeypatch, capsys):
    code, out = run(monkeypatch, capsys, "sql", "SELECT TOOLZ FROM GUARD_EVENTS WHERE TS > ?")
    assert code == 1 and "SQL0206N" in out
    code, out = run(monkeypatch, capsys, "sql", "SELECT 1 FROM SYSIBM.SYSDUMMY1")
    assert code == 0


def test_memory_commands(monkeypatch, capsys, tmp_path):
    proj = tmp_path / "cli-proj"
    proj.mkdir()
    code, out = run(monkeypatch, capsys, "remember", "Dates are stored as UTC TIMESTAMP", "--kind", "convention",
                    "--tag", "time", cwd=proj)
    assert code == 0 and json.loads(out)["stored"]
    code, out = run(monkeypatch, capsys, "recall", "how do we store dates", cwd=proj)
    assert code == 0 and "[convention] Dates are stored as UTC TIMESTAMP" in out
    empty = tmp_path / "empty-proj"
    empty.mkdir()
    code, out = run(monkeypatch, capsys, "recall", "anything", cwd=empty)
    assert "No memories" in out


def test_ask_and_report(monkeypatch, capsys):
    code, out = run(monkeypatch, capsys, "ask", "Where must API keys be kept?", "--category", "secrets")
    assert code == 0 and "POL-SEC-002" in out
    code, out = run(monkeypatch, capsys, "report", "--since-minutes", "120")
    assert code == 0 and "by_client" in json.loads(out)


def test_fix_command_on_clean_file(monkeypatch, capsys, workspace):
    code, out = run(monkeypatch, capsys, "fix", "app.py", "--write", cwd=workspace)
    assert code == 0 and "Nothing to fix" in out
    code, out = run(monkeypatch, capsys, "fix", "app.py", "--json", cwd=workspace)
    assert json.loads(out)["verified"] is True


def test_connect_command(monkeypatch, capsys, tmp_path):
    code, out = run(monkeypatch, capsys, "connect", "bob", "--workspace", tmp_path, "--env-file", tmp_path / "x.env")
    assert code == 0 and "IBM Bob" in out
    entry = json.loads((tmp_path / ".bob" / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]["shipsafe"]
    assert entry["env"]["SHIPSAFE_ENV_FILE"].endswith("x.env")


def test_setup_command(monkeypatch, capsys, tmp_path):
    target = tmp_path / "home" / ".env"
    code, out = run(monkeypatch, capsys, "setup", "--env-file", target)
    assert code == 0, out
    text = target.read_text(encoding="utf-8")
    assert "DB2_SCHEMA=SHIPSAFE_TEST" in text and "SHIPSAFE_CHAT_MODEL=" in text
    assert "Policy vectors in Db2" in out and "Project memory store" in out


def test_setup_without_password(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("DB2_PASSWORD", "")
    code, out = run(monkeypatch, capsys, "setup", "--env-file", tmp_path / ".env")
    assert code == 2 and "DB2_PASSWORD is not set" in out


def test_scan_history_and_assessments(monkeypatch, capsys, tmp_path):
    md = tmp_path / "r.md"
    code, out = run(monkeypatch, capsys, "scan", "--target", FIXTURES / "vulnerable_project", "--profile", "quick",
                    "--output", md)
    assert code != 0 and "BLOCKED" in md.read_text(encoding="utf-8")
    ids = re.findall(r"asm_[0-9a-f]{12}", md.read_text(encoding="utf-8"))
    code, out = run(monkeypatch, capsys, "scan", "--target", FIXTURES / "clean_project", "--profile", "quick",
                    "--format", "json", "--output", tmp_path / "r.json")
    data = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    code, out = run(monkeypatch, capsys, "scan", "--target", FIXTURES / "vulnerable_project", "--offline",
                    "--format", "sarif", "--output", tmp_path / "r.sarif")
    assert json.loads((tmp_path / "r.sarif").read_text(encoding="utf-8"))["version"] == "2.1.0"
    code, out = run(monkeypatch, capsys, "history", "--limit", "5")
    assert code == 0 and "RISK" in out.upper()
    code, out = run(monkeypatch, capsys, "assessment", "show", ids[0])
    assert code == 0 and ids[0] in out
    clean_id = data["assessment"]["assessment_id"]
    code, out = run(monkeypatch, capsys, "assessment", "compare", ids[0], clean_id)
    assert code == 0
    code, out = run(monkeypatch, capsys, "discover", "--target", FIXTURES / "vulnerable_project")
    assert code == 0 and "python" in out.lower()


def test_knowledge_ingest_and_query(monkeypatch, capsys):
    code, out = run(monkeypatch, capsys, "ingest")
    assert code == 0 and "POL-DB2-001" in out
    code, out = run(monkeypatch, capsys, "knowledge", "query", "f-string SQL injection", "--top-k", "1")
    assert code == 0 and "POL-DB2-001" in out


def test_tokens_and_audit(monkeypatch, capsys):
    code, out = run(monkeypatch, capsys, "token", "create", "--name", "cli-test", "--role", "viewer")
    assert code == 0
    tid = re.search(r"tok_[0-9a-f]+|[0-9a-f]{16,32}", out).group(0)
    code, out = run(monkeypatch, capsys, "token", "list")
    assert "cli-test" in out
    code, out = run(monkeypatch, capsys, "token", "revoke", tid)
    assert code == 0
    code, out = run(monkeypatch, capsys, "audit", "--limit", "5")
    assert code == 0
