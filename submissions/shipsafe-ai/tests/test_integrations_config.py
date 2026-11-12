"""IDE connection files and configuration loading (real files in temporary folders)."""

import json
import sys

import pytest

from shipsafe.config import Db2Config, LlmConfig, ShipSafeConfig, env_files
from shipsafe.integrations import TARGETS, connect, merge_config, server_command


def test_server_command_uses_this_interpreter():
    assert server_command() == {"command": sys.executable, "args": ["-m", "shipsafe.mcp_server"]}
    assert server_command("/py")["command"] == "/py"


def test_merge_preserves_other_servers_and_user_options():
    existing = json.dumps({"mcpServers": {"other": {"command": "x"}, "shipsafe": {"alwaysAllow": ["a"], "command": "old"}}})
    merged = json.loads(merge_config(existing, {"command": "new", "args": []}))
    assert merged["mcpServers"]["other"] == {"command": "x"}
    assert merged["mcpServers"]["shipsafe"] == {"alwaysAllow": ["a"], "command": "new", "args": []}
    assert json.loads(merge_config(None, {"command": "c"}))["mcpServers"]["shipsafe"]["command"] == "c"
    assert json.loads(merge_config('{"mcpServers": []}', {"command": "c"}))["mcpServers"]["shipsafe"]
    with pytest.raises(ValueError):
        merge_config("[1]", {"command": "c"})


@pytest.mark.parametrize("target, path, key", [
    ("bob", ".bob/mcp.json", "mcpServers"),
    ("claude", ".mcp.json", "mcpServers"),
    ("cursor", ".cursor/mcp.json", "mcpServers"),
    ("vscode", ".vscode/mcp.json", "servers"),
])
def test_connect_writes_each_ide_config(tmp_path, target, path, key):
    files = connect(target, str(tmp_path), python="/venv/python", env={"SHIPSAFE_ENV_FILE": "/x/.env"})
    cfg = json.loads((tmp_path / path).read_text(encoding="utf-8"))
    entry = cfg[key]["shipsafe"]
    assert entry["command"] == "/venv/python" and entry["args"] == ["-m", "shipsafe.mcp_server"]
    expected_env = {"SHIPSAFE_ENV_FILE": "/x/.env"}
    if target in ("bob", "vscode"):
        expected_env["SHIPSAFE_WORKSPACE"] = "${workspaceFolder}"  # these editors start the server outside the project
    assert entry["env"] == expected_env
    assert (entry.get("type") == "stdio") == (target in ("claude", "vscode"))
    assert (tmp_path / path).resolve() in [f.resolve() for f in files]
    connect(target, str(tmp_path))  # idempotent
    assert len(json.loads((tmp_path / path).read_text(encoding="utf-8"))[key]) == 1


def test_bob_rules_file(tmp_path):
    connect("bob", str(tmp_path))
    rules = (tmp_path / ".bob" / "rules" / "shipsafe.md").read_text(encoding="utf-8")
    for tool in ("shipsafe_check_code", "shipsafe_fix_code", "shipsafe_check_sql", "shipsafe_recall", "shipsafe_remember"):
        assert tool in rules


def test_unknown_target():
    assert set(TARGETS) == {"bob", "claude", "cursor", "vscode"}
    with pytest.raises(ValueError):
        connect("notepad", ".")


def test_db2_config_from_env(monkeypatch):
    for k in ("DB2_NAME", "DB2_DATABASE", "DB2_SSL", "DB2_SECURITY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("DB2_HOST", "db.example")
    monkeypatch.setenv("DB2_PORT", "50001")
    monkeypatch.setenv("DB2_NAME", "TESTDB")
    monkeypatch.setenv("DB2_SSL", "true")
    cfg = Db2Config.from_env()
    assert (cfg.host, cfg.port, cfg.database, cfg.security) == ("db.example", 50001, "TESTDB", "SSL")
    assert cfg.connection_string().endswith("SECURITY=SSL;")
    monkeypatch.delenv("DB2_SSL")
    monkeypatch.delenv("DB2_NAME")
    monkeypatch.setenv("DB2_DATABASE", "LEGACY")
    monkeypatch.setenv("DB2_SECURITY", "none")
    cfg = Db2Config.from_env()
    assert cfg.database == "LEGACY" and cfg.security == "NONE" and "SECURITY" not in cfg.connection_string()


def test_llm_config_from_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://gpu-box:11434/")
    monkeypatch.setenv("SHIPSAFE_CHAT_MODEL", "granite4:tiny-h")
    cfg = LlmConfig.from_env()
    assert cfg.host == "http://gpu-box:11434" and cfg.chat_model == "granite4:tiny-h"


def test_validate_reports_every_problem():
    cfg = ShipSafeConfig(db2=Db2Config(password="", security="TLS", schema="bad schema"), embedding_provider="openai",
                         llm=LlmConfig(host="gpu:11434"), pip_audit="sometimes", log_format="xml", pool_size=0,
                         auth_enabled=False, api_host="0.0.0.0")
    problems = " | ".join(cfg.validate())
    for word in ("DB2_PASSWORD", "DB2_SECURITY", "DB2_SCHEMA", "SHIPSAFE_EMBEDDINGS", "OLLAMA_HOST",
                 "SHIPSAFE_PIP_AUDIT", "SHIPSAFE_LOG_FORMAT", "POOL_SIZE", "SHIPSAFE_AUTH"):
        assert word in problems
    assert ShipSafeConfig(db2=Db2Config(password="x")).validate() == []


def test_env_files_priority(tmp_path, monkeypatch):
    custom = tmp_path / "custom.env"
    custom.write_text("A=1\n", encoding="utf-8")
    monkeypatch.setenv("SHIPSAFE_ENV_FILE", str(custom))
    monkeypatch.chdir(tmp_path)
    assert env_files()[0] == custom
    monkeypatch.setenv("SHIPSAFE_ENV_FILE", str(tmp_path / "missing.env"))
    assert custom not in env_files()
