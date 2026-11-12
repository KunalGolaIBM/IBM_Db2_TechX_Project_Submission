"""ShipSafe MCP server: production-readiness tools for IBM Bob and any MCP-capable AI IDE.

Run:  shipsafe-mcp            (stdio; this is what Bob / Claude Code / Cursor / VS Code launch)

The assistant is expected to call `shipsafe_check_code` before it writes a file,
`shipsafe_fix_code` when a check blocks, `shipsafe_check_sql` before it ships a
query, and `shipsafe_recall` / `shipsafe_remember` to keep project decisions in
IBM Db2 across sessions. The bundled Bob rules file tells Bob exactly that.
"""

import asyncio
import functools
import json
import logging
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional

from mcp.server.fastmcp import Context, FastMCP

from . import __version__
from .services import ShipSafeServices

log = logging.getLogger("shipsafe.mcp")

INSTRUCTIONS = (
    "ShipSafe keeps code production-ready while you write it. Before writing or editing a source file, call "
    "shipsafe_check_code with the full new content. If the verdict is 'block', fix the issues (or call "
    "shipsafe_fix_code) and check again before writing. Validate every SQL statement for IBM Db2 with "
    "shipsafe_check_sql. At the start of a task call shipsafe_recall for project decisions; when the user "
    "makes a decision worth keeping, call shipsafe_remember. Use shipsafe_ask_standards for team rules."
)

mcp = FastMCP("shipsafe", instructions=INSTRUCTIONS)
_services: Optional[ShipSafeServices] = None
# Tool work runs on one worker thread, never on the server's event loop: CrewAI refuses to run its crew
# synchronously inside a running loop, and a long Granite fix must not freeze the MCP transport.
# One worker keeps calls in order, as before, so Db2 connections are never shared across threads.
_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="shipsafe-tool")


async def _run(fn, *args, **kwargs) -> str:
    loop = asyncio.get_running_loop()
    return _json(await loop.run_in_executor(_worker, functools.partial(fn, *args, **kwargs)))


_services_lock = threading.Lock()


def services() -> ShipSafeServices:
    global _services
    with _services_lock:  # the warm-up thread and the tool worker may both get here first
        if _services is None:
            _services = ShipSafeServices(workspace_root=os.getenv("SHIPSAFE_WORKSPACE") or os.getcwd())
    return _services


def _client(ctx: Optional[Context]) -> str:
    """Name of the calling IDE as it introduced itself in `initialize` (e.g. 'bob', 'claude-code')."""
    try:
        info = ctx.session.client_params.clientInfo  # type: ignore[union-attr]
        return (info.name or "unknown")[:32]
    except Exception:
        return "unknown"


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


@mcp.tool()
async def shipsafe_check_code(code: str, filename: str, ctx: Context = None) -> str:
    """Check code BEFORE writing it to a file. Returns verdict clean|warn|block, each issue with line, why,
    how to fix and the team policy (from IBM Db2) it violates. Pass the complete new file content and its
    path (the extension selects the language). Do not write the file while the verdict is 'block'."""
    client = _client(ctx)
    return await _run(lambda: services().check_code(code, filename, client=client))


@mcp.tool()
async def shipsafe_check_files(paths: List[str], ctx: Context = None) -> str:
    """Check existing files in the workspace (paths relative to the workspace root, max 50)."""
    client = _client(ctx)
    return await _run(lambda: services().check_files(paths, client=client))


@mcp.tool()
async def shipsafe_fix_code(code: str, filename: str, ctx: Context = None) -> str:
    """Fix the issues ShipSafe found, using a CrewAI crew on local IBM Granite. The result is re-checked
    with the same deterministic checks; only use fixed_code when verified is true. Returns a unified diff."""
    client = _client(ctx)
    return await _run(lambda: services().fix_code(code, filename, client=client))


@mcp.tool()
async def shipsafe_check_sql(sql: str) -> str:
    """Validate one SQL statement against the live IBM Db2 database without executing it: syntax, unknown
    tables or columns (with 'did you mean' suggestions), result columns, plus risky patterns such as
    UPDATE/DELETE without WHERE or string-formatted values instead of ? parameter markers."""
    return await _run(lambda: services().check_sql(sql))


@mcp.tool()
async def shipsafe_db2_schema(schema: Optional[str] = None, tables: Optional[List[str]] = None) -> str:
    """Describe tables, columns, keys and indexes of an IBM Db2 schema so the SQL you write matches the
    real database. Defaults to the ShipSafe schema; pass `tables` to limit the output."""
    return await _run(lambda: services().db2_schema(schema, tables))


@mcp.tool()
async def shipsafe_ask_standards(question: str, category: Optional[str] = None) -> str:
    """Ask what the team's engineering standard is (e.g. 'how must we store API keys?'). Answered by IBM
    Granite from policies retrieved with IBM Db2 vector search, with citations."""
    return await _run(lambda: services().ask_standards(question, category))


@mcp.tool()
async def shipsafe_remember(text: str, kind: str = "decision", tags: Optional[List[str]] = None,
                      project: Optional[str] = None, ctx: Context = None) -> str:
    """Save a project decision, convention, gotcha or todo to long-term memory in IBM Db2 (vector store),
    so it is available in later sessions. kind: decision | convention | gotcha | todo."""
    client = _client(ctx)
    return await _run(lambda: services().remember(text, kind=kind, project=project, tags=tags, client=client))


@mcp.tool()
async def shipsafe_recall(query: str, project: Optional[str] = None, top_k: int = 5, kind: Optional[str] = None) -> str:
    """Find earlier project decisions and conventions relevant to the current task (semantic search in
    IBM Db2). Call this at the start of a task."""
    return await _run(lambda: services().recall(query, project=project, top_k=top_k, kind=kind))


@mcp.tool()
async def shipsafe_readiness_check(workspace: str = ".", profile: str = "pre-pr") -> str:
    """Full production-readiness gate for the workspace (secrets, code rules, Bandit, dependencies with
    known CVEs, tests). Saved to IBM Db2 with a risk trend computed by a Db2 stored procedure.
    profile: quick | pre-pr | deep."""
    return await _run(lambda: services().readiness_check(workspace, profile))


@mcp.tool()
async def shipsafe_session_report(since_minutes: int = 1440) -> str:
    """What ShipSafe caught for each IDE in the given window (checks, blocks, issues, verified fixes),
    computed by a Db2 stored procedure."""
    return await _run(lambda: services().session_report(since_minutes))


@mcp.tool()
async def shipsafe_status() -> str:
    """Health of the IBM Db2 connection and the local Granite models."""
    return await _run(lambda: services().status())


def preload_native_modules() -> None:
    """Import every module that loads native DLLs before the stdio transport starts.

    On Windows, loading some native libraries (numpy/OpenBLAS, ibm_db's CLI driver) can block for as
    long as another thread has a pending read on the stdin pipe, and the MCP transport always has one.
    Importing them up front, while nothing reads stdin yet, removes that deadlock."""
    import ibm_db  # noqa: F401
    import ibm_db_dbi  # noqa: F401
    import numpy  # noqa: F401
    import langchain_db2.db2vs  # noqa: F401
    import haystack_integrations.document_stores.ibm_db  # noqa: F401
    import sqlalchemy  # noqa: F401


def main() -> None:
    logging.basicConfig(level=os.getenv("SHIPSAFE_LOG_LEVEL", "WARNING"), stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    log.info("ShipSafe MCP %s starting", __version__)
    preload_native_modules()
    threading.Thread(target=warm_up, name="shipsafe-warmup", daemon=True).start()
    mcp.run("stdio")


def warm_up() -> None:
    """Connect to Db2 and load the policy index in the background so the first check is fast.
    Failures are only logged: each tool reports its own errors when it is called."""
    try:
        services().knowledge_base
    except Exception as exc:  # pragma: no cover - depends on the environment
        log.warning("warm-up skipped: %s", exc)


if __name__ == "__main__":
    main()
