"""Claude Code pre-write hook, driven exactly like Claude Code drives it: a real subprocess with the
PreToolUse event as JSON on stdin; exit code 2 blocks the write and stderr goes back to the model."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from shipsafe.integrations import connect
from shipsafe.integrations.claude_hook import merge_hook_settings, proposed_content

ROOT = Path(__file__).resolve().parents[1]
VULNERABLE = 'import os\n\ndef run(cmd):\n    os.system(cmd)\n\ndef q(cur, name):\n    cur.execute(f"SELECT * FROM T WHERE N = \'{name}\'")\n'


def hook(event, cwd):
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "DB2_PORT": "1", "SHIPSAFE_DB2_CONNECT_TIMEOUT": "2"}
    p = subprocess.run([sys.executable, "-m", "shipsafe.cli", "guard-hook"], input=json.dumps(event), text=True,
                       capture_output=True, cwd=cwd, env=env, timeout=180, shell=False)
    return p.returncode, p.stderr


def event(tool, tool_input, cwd):
    return {"session_id": "t", "hook_event_name": "PreToolUse", "cwd": str(cwd), "tool_name": tool, "tool_input": tool_input}


def test_write_of_vulnerable_code_is_blocked_with_reasons(tmp_path):
    code, err = hook(event("Write", {"file_path": str(tmp_path / "app" / "run.py"), "content": VULNERABLE}, tmp_path), tmp_path)
    assert code == 2
    assert "ShipSafe blocked this write to" in err and "CMD-" in err and "SQLI-DYNAMIC" in err
    assert not (tmp_path / "app" / "run.py").exists()


def test_clean_write_edit_and_other_tools_pass(tmp_path):
    target = tmp_path / "m.py"
    assert hook(event("Write", {"file_path": str(target), "content": "def add(a, b):\n    return a + b\n"}, tmp_path), tmp_path)[0] == 0
    target.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    assert hook(event("Edit", {"file_path": "m.py", "old_string": "a + b", "new_string": "a - b"}, tmp_path), tmp_path)[0] == 0
    assert hook(event("Bash", {"command": "ls"}, tmp_path), tmp_path)[0] == 0
    assert hook(event("Write", {"content": "x"}, tmp_path), tmp_path)[0] == 0  # no path
    p = subprocess.run([sys.executable, "-m", "shipsafe.cli", "guard-hook"], input="not json", text=True, capture_output=True,
                       env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, timeout=120, shell=False)
    assert p.returncode == 0  # malformed input never breaks the editor


def test_edit_that_introduces_a_problem_is_blocked(tmp_path):
    target = tmp_path / "svc.py"
    target.write_text("import subprocess\n\ndef deploy(args):\n    return subprocess.run(args)\n", encoding="utf-8")
    code, err = hook(event("MultiEdit", {"file_path": str(target), "edits": [
        {"old_string": "def deploy(args):", "new_string": "def deploy(cmd):"},
        {"old_string": "subprocess.run(args)", "new_string": "subprocess.run(cmd, shell=True)"}]}, tmp_path), tmp_path)
    assert code == 2 and "svc.py" in err


def test_proposed_content():
    assert proposed_content("Write", {"content": "x"}, "old") == "x"
    assert proposed_content("Edit", {"old_string": "a", "new_string": "b"}, "a a") == "b a"
    assert proposed_content("Edit", {"old_string": "a", "new_string": "b", "replace_all": True}, "a a") == "b b"
    assert proposed_content("Edit", {"old_string": "zz", "new_string": "b"}, "a") is None
    assert proposed_content("MultiEdit", {"edits": [{"old_string": "a", "new_string": "b"}, {"old_string": "q", "new_string": "c"}]}, "a") is None
    assert proposed_content("Read", {}, "a") is None
    assert proposed_content("Write", {"content": 3}, "a") is None


def test_connect_claude_installs_the_hook_and_keeps_user_hooks(tmp_path):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"model": "x", "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "mine"}]}],
                                                            "Stop": [{"hooks": []}]}}), encoding="utf-8")
    files = connect("claude", str(tmp_path), python="/venv/bin/python")
    assert settings.resolve() in [f.resolve() for f in files]
    connect("claude", str(tmp_path), python="/venv/bin/python")  # idempotent
    cfg = json.loads(settings.read_text(encoding="utf-8"))
    assert cfg["model"] == "x" and "Stop" in cfg["hooks"]
    pre = cfg["hooks"]["PreToolUse"]
    assert pre[0]["hooks"][0]["command"] == "mine" and len(pre) == 2
    assert pre[1]["matcher"] == "Write|Edit|MultiEdit"
    assert pre[1]["hooks"][0]["command"] == '"/venv/bin/python" -m shipsafe.cli guard-hook'
    with pytest.raises(ValueError):
        merge_hook_settings("[1]", "c")


def test_bob_gets_a_long_tool_timeout_unless_the_user_set_one(tmp_path):
    connect("bob", str(tmp_path))
    assert json.loads((tmp_path / ".bob" / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]["shipsafe"]["timeout"] == 600_000
    cfg = tmp_path / ".bob" / "mcp.json"
    data = json.loads(cfg.read_text(encoding="utf-8"))
    data["mcpServers"]["shipsafe"]["timeout"] = 90_000
    cfg.write_text(json.dumps(data), encoding="utf-8")
    connect("bob", str(tmp_path))
    assert json.loads(cfg.read_text(encoding="utf-8"))["mcpServers"]["shipsafe"]["timeout"] == 90_000
