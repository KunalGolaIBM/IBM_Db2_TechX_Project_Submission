"""CLI commands for the IDE add-on: setup, connect, check, fix, sql, ask, remember, recall, report, hook."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

from .config import ShipSafeConfig

LINE = "=" * 64
SETUP_KEYS = ("DB2_HOST", "DB2_PORT", "DB2_NAME", "DB2_USERNAME", "DB2_PASSWORD", "DB2_SSL", "DB2_SCHEMA",
              "OLLAMA_HOST", "SHIPSAFE_CHAT_MODEL", "SHIPSAFE_EMBED_MODEL", "SHIPSAFE_EMBEDDINGS")
HOOK = """#!/bin/sh
# ShipSafe pre-commit hook: block commits whose staged files fail the guard.
exec "{python}" -m shipsafe.cli check --staged
"""


def _print_json(data) -> None:
    print(json.dumps(data, indent=2, default=str))


def _services(args=None):
    from .services import ShipSafeServices

    return ShipSafeServices(workspace_root=getattr(args, "workspace", None) or os.getcwd())


def cmd_setup(args) -> int:
    """Store the connection in ~/.shipsafe/.env, create the Db2 schema, index policies, check Granite."""
    from .llm import ollama_status

    target = Path(args.env_file).expanduser() if args.env_file else Path.home() / ".shipsafe" / ".env"
    config = ShipSafeConfig.load()
    values = {
        "DB2_HOST": config.db2.host, "DB2_PORT": str(config.db2.port), "DB2_NAME": config.db2.database,
        "DB2_USERNAME": config.db2.username, "DB2_PASSWORD": config.db2.password,
        "DB2_SSL": "true" if config.db2.security == "SSL" else "false", "DB2_SCHEMA": config.db2.schema,
        "OLLAMA_HOST": config.llm.host, "SHIPSAFE_CHAT_MODEL": config.llm.chat_model,
        "SHIPSAFE_EMBED_MODEL": config.llm.embed_model, "SHIPSAFE_EMBEDDINGS": config.embedding_provider,
    }
    if not values["DB2_PASSWORD"]:
        print("DB2_PASSWORD is not set. Export it (or put it in ./.env) and run `shipsafe setup` again.")
        return 2
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# ShipSafe connection settings (written by `shipsafe setup`). Keep this file private.\n"
                      + "".join(f"{k}={values[k]}\n" for k in SETUP_KEYS), encoding="utf-8")
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    print(f"[OK]   Settings saved to {target}")

    st = ollama_status(config.llm)
    if not st["running"]:
        print(f"[FAIL] Ollama is not reachable at {config.llm.host}. Install it from https://ollama.com and start it.")
        return 1
    for model, ready in ((config.llm.chat_model, st["chat_model_ready"]), (config.llm.embed_model, st["embed_model_ready"])):
        if ready:
            print(f"[OK]   Granite model {model} is installed")
        elif args.pull and shutil.which("ollama"):
            print(f"[..]   Pulling {model} (one-time download)...")
            if subprocess.run(["ollama", "pull", model], shell=False).returncode != 0:
                print(f"[FAIL] Could not pull {model}")
                return 1
        else:
            print(f"[FAIL] {model} is missing. Run: ollama pull {model}  (or `shipsafe setup --pull`)")
            return 1

    from .services import ShipSafeServices

    svc = ShipSafeServices(config)
    created = svc.repository.initialize_schema(replace_views=True)
    st_db = svc.repository.check_connection()
    print(f"[OK]   IBM Db2 {st_db['version']} {st_db['host']}:{st_db['port']}/{st_db['database']} schema {st_db['schema']}"
          f" ({len(created)} objects created)")
    print(f"[OK]   Policy vectors in Db2: {svc.knowledge_base.chunk_count()} chunks")
    print(f"[OK]   Project memory store: {svc.memory.count()} memories")
    print("\nNext: run `shipsafe connect bob` inside a project folder.")
    return 0


def cmd_connect(args) -> int:
    from .integrations import connect

    env = {"SHIPSAFE_ENV_FILE": str(Path(args.env_file).expanduser().resolve())} if args.env_file else None
    files = connect(args.target, args.workspace or ".", python=args.python, env=env)
    for f in files:
        print(f"[OK] wrote {f}")
    names = {"bob": "IBM Bob", "claude": "Claude Code", "cursor": "Cursor", "vscode": "VS Code"}
    print(f"Reload {names[args.target]} in this folder; the 'shipsafe' MCP server and its tools will appear.")
    return 0


def _staged_files() -> List[str]:
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"], capture_output=True,
                         text=True, shell=False, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def cmd_check(args) -> int:
    svc = _services(args)
    paths = _staged_files() if args.staged else args.files
    if not paths:
        print("Nothing to check.")
        return 0
    result = svc.check_files(paths, client="cli")
    if args.json:
        _print_json(result)
    else:
        for f in result["files"]:
            if "error" in f:
                print(f"  [--]  {f['filename']}: {f['error']}")
                continue
            mark = {"clean": "OK  ", "warn": "WARN", "block": "BLOCK"}[f["verdict"]]
            print(f"  [{mark}] {f['filename']}  ({len(f['issues'])} issue(s), {f['duration_ms']} ms)")
            for i in f["issues"]:
                policy = f"  [{i['policy']['doc_id']}]" if i.get("policy") else ""
                print(f"         L{i['line']:<4} {i['severity']:<8} {i['rule_id']}: {i['title']}{policy}")
                print(f"               fix: {i['fix']}")
        print(f"\nVerdict: {result['verdict'].upper()}")
    return 1 if result["verdict"] == "block" else 0


def cmd_fix(args) -> int:
    svc = _services(args)
    path = svc.resolve_in_workspace(args.file)
    result = svc.fix_code(path.read_text(encoding="utf-8"), path.relative_to(svc.workspace_root).as_posix(), client="cli")
    if args.json:
        _print_json(result)
    else:
        print(result["message"])
        if result["diff"]:
            print(result["diff"])
    if args.write and result["verified"] and result["fixed_code"]:
        path.write_text(result["fixed_code"], encoding="utf-8")
        print(f"[OK] wrote {path}")
    return 0 if result["verified"] else 1


def cmd_sql(args) -> int:
    result = _services(args).check_sql(args.sql)
    _print_json(result)
    return 1 if result["verdict"] == "block" else 0


def cmd_ask(args) -> int:
    r = _services(args).ask_standards(args.question, args.category)
    print(r["answer"] + "\n\nSources:")
    for c in r["citations"]:
        print(f"  - {c['doc_id']} {c['title']} / {c['section']} (similarity {c['similarity']})")
    return 0


def cmd_remember(args) -> int:
    _print_json(_services(args).remember(args.text, kind=args.kind, tags=args.tag, client="cli"))
    return 0


def cmd_recall(args) -> int:
    hits = _services(args).recall(args.query, top_k=args.top_k)
    if args.json:
        _print_json(hits)
        return 0
    for h in hits:
        print(f"  [{h['kind']}] {h['text']}  (score {h['score']})")
    if not hits:
        print("No memories for this project yet.")
    return 0


def cmd_forget(args) -> int:
    _services(args).memory.forget(args.memory_id)
    print(f"[OK] removed {args.memory_id} from project memory")
    return 0


def cmd_report(args) -> int:
    _print_json(_services(args).session_report(args.since_minutes))
    return 0


def cmd_hook(args) -> int:
    git_dir = subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True, text=True, shell=False)
    if git_dir.returncode != 0:
        print("Not a git repository.")
        return 2
    hook = Path(git_dir.stdout.strip()) / "hooks" / "pre-commit"
    if hook.exists() and "shipsafe" not in hook.read_text(encoding="utf-8", errors="ignore"):
        print(f"{hook} already exists and is not ShipSafe's; not overwriting.")
        return 2
    hook.write_text(HOOK.format(python=Path(sys.executable).as_posix()), encoding="utf-8")
    try:
        os.chmod(hook, 0o700)  # executable by the owner only
    except OSError:
        pass
    print(f"[OK] installed {hook}")
    return 0


def register(sub) -> dict:
    p = sub.add_parser("setup", help="Save the Db2/Ollama connection, create the schema, check Granite")
    p.add_argument("--env-file", help="Where to store settings (default ~/.shipsafe/.env)")
    p.add_argument("--pull", action="store_true", help="Pull missing Granite models with `ollama pull`")
    p = sub.add_parser("connect", help="Register ShipSafe with an AI IDE in this folder")
    p.add_argument("target", choices=["bob", "claude", "cursor", "vscode"])
    p.add_argument("--workspace", default=".")
    p.add_argument("--python", help="Interpreter that has ShipSafe installed (default: this one)")
    p.add_argument("--env-file", help="Settings file to pass to the server")
    p = sub.add_parser("check", help="Check files with the IDE guard (exit 1 on block)")
    p.add_argument("files", nargs="*")
    p.add_argument("--staged", action="store_true", help="Check the files staged in git")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("fix", help="Fix a file with the Granite crew and verify the result")
    p.add_argument("file")
    p.add_argument("--write", action="store_true", help="Write the fix if it is verified")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("sql", help="Validate a SQL statement on Db2 without running it")
    p.add_argument("sql")
    p = sub.add_parser("ask", help="Ask the team standards (Granite + Db2 vector search)")
    p.add_argument("question")
    p.add_argument("--category")
    p = sub.add_parser("remember", help="Save a project decision to Db2 memory")
    p.add_argument("text")
    p.add_argument("--kind", default="decision", choices=["decision", "convention", "gotcha", "todo"])
    p.add_argument("--tag", action="append", default=[])
    p = sub.add_parser("recall", help="Search project memory")
    p.add_argument("query")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("forget", help="Delete a project memory by id (ids are shown by recall --json)")
    p.add_argument("memory_id")
    p = sub.add_parser("report", help="What ShipSafe caught per IDE (Db2 stored procedure)")
    p.add_argument("--since-minutes", type=int, default=1440)
    p = sub.add_parser("hook", help="Install a git pre-commit hook that runs `shipsafe check --staged`")
    return {"setup": cmd_setup, "connect": cmd_connect, "check": cmd_check, "fix": cmd_fix, "sql": cmd_sql,
            "ask": cmd_ask, "remember": cmd_remember, "recall": cmd_recall, "forget": cmd_forget, "report": cmd_report, "hook": cmd_hook}
