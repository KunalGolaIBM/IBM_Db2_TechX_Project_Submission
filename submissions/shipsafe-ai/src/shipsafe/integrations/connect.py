"""Register the ShipSafe MCP server with AI IDEs.

| IDE         | File written (project scope)     | Shape                                  |
|-------------|----------------------------------|----------------------------------------|
| IBM Bob     | .bob/mcp.json + .bob/rules/...   | {"mcpServers": {"shipsafe": {...}}}    |
| Claude Code | .mcp.json + .claude/settings.json | MCP server + PreToolUse write hook     |
| Cursor      | .cursor/mcp.json                 | {"mcpServers": {"shipsafe": {...}}}    |
| VS Code     | .vscode/mcp.json                 | {"servers": {"shipsafe": {...}}}       |

Existing entries for other servers, and user options on ours (for example
Bob's "alwaysAllow"), are preserved.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

SERVER_NAME = "shipsafe"
RULES_FILE = Path(__file__).with_name("bob_rules.md")
TARGETS = ("bob", "claude", "cursor", "vscode")
WORKSPACE_VAR = "${workspaceFolder}"
BOB_TIMEOUT_MS = 600_000  # Bob cancels MCP tools after 60 s by default; Granite fixes can take longer


def server_command(python: Optional[str] = None) -> Dict[str, object]:
    """Launch command for the MCP server using this interpreter (works without PATH changes)."""
    return {"command": python or sys.executable, "args": ["-m", "shipsafe.mcp_server"]}


def merge_config(existing: Optional[str], entry: Dict[str, object], key: str = "mcpServers",
                 defaults: Optional[Dict[str, object]] = None) -> str:
    config: Dict[str, object] = {}
    if existing and existing.strip():
        config = json.loads(existing)
        if not isinstance(config, dict):
            raise ValueError("existing MCP config is not a JSON object")
    servers = config.get(key)
    if not isinstance(servers, dict):
        servers = {}
    previous = servers.get(SERVER_NAME) if isinstance(servers.get(SERVER_NAME), dict) else {}
    servers[SERVER_NAME] = {**(defaults or {}), **previous, **entry}
    config[key] = servers
    return json.dumps(config, indent=2) + "\n"


def _write_merged(path: Path, entry: Dict[str, object], key: str = "mcpServers",
                  defaults: Optional[Dict[str, object]] = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else None
    path.write_text(merge_config(existing, entry, key, defaults), encoding="utf-8")
    return path


def connect(target: str, workspace: str = ".", python: Optional[str] = None,
            env: Optional[Dict[str, str]] = None) -> List[Path]:
    """Write the config for `target` into `workspace`. Returns the files written."""
    if target not in TARGETS:
        raise ValueError(f"unknown target {target!r}; choose from {', '.join(TARGETS)}")
    root = Path(workspace).resolve()
    entry: Dict[str, object] = server_command(python)
    if target in ("bob", "vscode"):
        # Both editors start the server outside the project; they expand ${workspaceFolder} in env themselves.
        entry["env"] = {"SHIPSAFE_WORKSPACE": WORKSPACE_VAR, **(env or {})}
    elif env:
        entry["env"] = dict(env)
    if target == "bob":
        rules = root / ".bob" / "rules" / "shipsafe.md"
        rules.parent.mkdir(parents=True, exist_ok=True)
        rules.write_text(RULES_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        return [_write_merged(root / ".bob" / "mcp.json", entry, defaults={"timeout": BOB_TIMEOUT_MS}), rules]
    if target == "claude":
        from .claude_hook import merge_hook_settings

        settings = root / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        existing = settings.read_text(encoding="utf-8") if settings.is_file() else None
        command = f'"{Path(str(entry["command"])).as_posix()}" -m shipsafe.cli guard-hook'
        settings.write_text(merge_hook_settings(existing, command), encoding="utf-8")
        return [_write_merged(root / ".mcp.json", {"type": "stdio", **entry}), settings]
    if target == "cursor":
        return [_write_merged(root / ".cursor" / "mcp.json", entry)]
    return [_write_merged(root / ".vscode" / "mcp.json", {"type": "stdio", **entry}, key="servers")]
