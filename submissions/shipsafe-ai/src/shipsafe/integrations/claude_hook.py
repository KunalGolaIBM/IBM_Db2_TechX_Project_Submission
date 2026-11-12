"""Claude Code pre-write hook: ShipSafe checks every Write/Edit/MultiEdit BEFORE it happens.

Claude Code runs `shipsafe guard-hook` for each file write (PreToolUse hook) and sends the tool call
as JSON on stdin. We rebuild the file content the tool would produce, check it with the same guard as
`shipsafe_check_code`, and exit with code 2 on a blocking verdict: Claude Code then cancels the write
and shows our reasons to the model, which has to fix the code first. This makes the check enforced
rather than requested.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

WRITE_TOOLS = ("Write", "Edit", "MultiEdit")
HOOK_MATCHER = "|".join(WRITE_TOOLS)
BLOCK = 2  # Claude Code: exit code 2 blocks the tool call and feeds stderr back to the model


def _replace(text: str, old: str, new: str, replace_all: bool = False) -> Optional[str]:
    if not old or old not in text:
        return None
    return text.replace(old, new) if replace_all else text.replace(old, new, 1)


def proposed_content(tool: str, tool_input: Dict[str, Any], current: str) -> Optional[str]:
    """The file content after the tool call, or None when it cannot be worked out (let the tool report it)."""
    if tool == "Write":
        content = tool_input.get("content")
        return content if isinstance(content, str) else None
    if tool == "Edit":
        return _replace(current, tool_input.get("old_string", ""), tool_input.get("new_string", ""),
                        bool(tool_input.get("replace_all")))
    if tool == "MultiEdit":
        text: Optional[str] = current
        for edit in tool_input.get("edits") or []:
            if text is None:
                return None
            text = _replace(text, edit.get("old_string", ""), edit.get("new_string", ""), bool(edit.get("replace_all")))
        return text
    return None


def evaluate(event: Dict[str, Any], services) -> Tuple[int, str]:
    """Return (exit code, message) for one PreToolUse event."""
    tool = event.get("tool_name")
    tool_input = event.get("tool_input") or {}
    path = tool_input.get("file_path") or ""
    if tool not in WRITE_TOOLS or not path:
        return 0, ""
    file = Path(path)
    if not file.is_absolute():
        file = Path(event.get("cwd") or ".") / file
    try:
        current = file.read_text(encoding="utf-8") if file.is_file() else ""
    except (OSError, UnicodeDecodeError):
        return 0, ""  # binary or unreadable: not ours to judge
    content = proposed_content(tool, tool_input, current)
    if content is None:
        return 0, ""
    try:
        rel = str(file.resolve().relative_to(Path(event.get("cwd") or ".").resolve()))
    except ValueError:
        rel = file.name
    result = services.check_code(content, rel, client="claude-code", cite_policies=False, tool="pre_write_hook")
    if result["verdict"] != "block":
        return 0, ""
    lines = [f"ShipSafe blocked this write to {rel}: fix these issues first, then write the file again.",
             "(Call the shipsafe_fix_code MCP tool for a verified fix if it is connected.)"]
    for issue in result["issues"]:
        if issue["severity"] in ("critical", "high"):
            lines.append(f"- line {issue['line']} [{issue['severity']}] {issue['rule_id']}: {issue['title']}. Fix: {issue['fix']}")
    return BLOCK, "\n".join(lines)


def hook_settings(command: str) -> Dict[str, Any]:
    """The `.claude/settings.json` fragment that runs the hook before every file write."""
    return {"hooks": {"PreToolUse": [{"matcher": HOOK_MATCHER, "hooks": [{"type": "command", "command": command, "timeout": 120}]}]}}


def merge_hook_settings(existing: Optional[str], command: str) -> str:
    """Add (or update) ShipSafe's PreToolUse hook, keeping every other setting and hook."""
    config: Dict[str, Any] = json.loads(existing) if existing and existing.strip() else {}
    if not isinstance(config, dict):
        raise ValueError(".claude/settings.json is not a JSON object")
    hooks = config.setdefault("hooks", {})
    pre = [h for h in hooks.get("PreToolUse", []) if not any("guard-hook" in str(x.get("command", "")) for x in h.get("hooks", []))]
    pre.append(hook_settings(command)["hooks"]["PreToolUse"][0])
    hooks["PreToolUse"] = pre
    return json.dumps(config, indent=2) + "\n"
