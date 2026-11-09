"""
GitMind 2.0 — CLI Interface

The unified command-line interface for GitMind 2.0:
    gitmind story     — Narrative of repo history
    gitmind ask       — Ask evidence-grounded questions about your repo
    gitmind recover   — Reflog analysis + recovery suggestions
    gitmind suggest   — Proactive suggestions & repo health
    gitmind explain   — Explain a commit, file, or feature
    gitmind project   — Understand project architecture and onboarding
    gitmind review    — Signature differentiator: Historical change-risk & regression review
    gitmind index     — Index repository into IBM Db2 Knowledge Graph & Vector Store
    gitmind db2       — IBM Db2 connectivity, diagnostics, doctor, and migrations
    gitmind memory    — Query persistent multi-agent engineering findings
"""

from __future__ import annotations

import os
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

import config
from utils.banner import print_banner
from utils.output import (
    console as rich_console,
    get_chat_input,
    print_chat_response,
    print_error,
    print_info,
    print_response,
    print_success,
    print_warning,
    spinner,
)

app = typer.Typer(
    name="gitmind",
    help="GitMind 2.0 — Persistent Engineering Intelligence powered by IBM Db2.",
    add_completion=False,
    no_args_is_help=True,
)

db2_app = typer.Typer(
    name="db2",
    help="IBM Db2 database diagnostics, connectivity testing, and schema migrations.",
    no_args_is_help=True,
)
app.add_typer(db2_app, name="db2")

memory_app = typer.Typer(
    name="memory",
    help="Persistent multi-agent engineering memory and historical findings.",
    no_args_is_help=True,
)
app.add_typer(memory_app, name="memory")


# ---------------------------------------------------------------------------
# gitmind review (Signature Differentiator)
# ---------------------------------------------------------------------------

@app.command()
def review(
    base: str = typer.Option("main", "--base", "-b", help="Base branch or commit reference to compare against."),
):
    """
    🛡️ Historical Change-Risk and Regression Review (Signature Differentiator).

    Analyzes current changes against repository history in IBM Db2 to detect:
    - Previously reverted implementations
    - Historical bug fixes in touched files
    - Regressions affecting the same functions
    - Authentication, schema, and API risks
    """
    print_banner("GitMind Change Review")

    from workflows.orchestrator import run_review

    with spinner(f"Investigating change risk against '{base}' with IBM Db2 intelligence..."):
        result_md = run_review(base_ref=base)

    print_response(result_md, title=f"Change Risk Review (Base: {base})")


# ---------------------------------------------------------------------------
# gitmind story
# ---------------------------------------------------------------------------

@app.command()
def story(
    days: int = typer.Option(7, "--days", "-d", help="Number of days of history to analyze."),
    detailed: bool = typer.Option(False, "--detailed", help="Include file-level changes."),
    quickoverview: bool = typer.Option(False, "--quickoverview", "-q", help="Quick topic-based overview (no AI)."),
    by: str = typer.Option("date", "--by", "-b", help="Group commits by: date, author."),
    ai: bool = typer.Option(True, "--ai/--no-ai", help="Use AI for narrative generation."),
):
    """
    📖 Generate a narrative story of your repository's history.
    """
    print_banner("GitMind Story")

    if quickoverview or not ai:
        from tools.story.get_commits import get_recent_commits
        from tools.story.quick_overview import OverviewGenerator
        from tools.story.story_generator import StoryGenerator

        commits = get_recent_commits(days=days)
        if not commits:
            print_warning("No commits found in the specified time range.")
            return

        if quickoverview:
            generator = OverviewGenerator(commits)
            rich_console.print(generator.overview())
        else:
            generator = StoryGenerator(commits)
            rich_console.print(generator.generate(detailed=detailed, by=by))
    else:
        from workflows.orchestrator import run_story

        with spinner(f"Analyzing {days} days of commit history..."):
            result = run_story(days=days, detailed=detailed)

        print_response(result, title="Repository Story")


# ---------------------------------------------------------------------------
# gitmind ask
# ---------------------------------------------------------------------------

@app.command()
def ask(
    question: Optional[str] = typer.Argument(None, help="Your question about the repository."),
    chat: bool = typer.Option(False, "--chat", "-c", help="Start a multi-turn chat session."),
):
    """
    💬 Ask evidence-grounded questions about your repository.
    """
    print_banner("GitMind Ask")

    from workflows.orchestrator import run_query

    if chat:
        print_info("Chat mode active. Type 'exit' to quit.\n")
        while True:
            user_input = get_chat_input()
            if user_input is None:
                print_info("Goodbye!")
                break
            if not user_input.strip():
                continue

            with spinner("Thinking with IBM Db2 multi-agent intelligence..."):
                result = run_query(user_input, command="ask")

            print_chat_response(result)
    else:
        if not question:
            print_error("Please provide a question or use --chat for interactive mode.")
            print_info('Usage: gitmind ask "why was this function added?"')
            raise typer.Exit(1)

        with spinner("Analyzing repository history and Db2 knowledge graph..."):
            result = run_query(question, command="ask")

        print_response(result, title="Answer")


# ---------------------------------------------------------------------------
# gitmind recover
# ---------------------------------------------------------------------------

@app.command()
def recover():
    """
    🔧 Analyze reflog and suggest recovery steps.
    """
    print_banner("GitMind Recover")

    from workflows.orchestrator import run_recover

    with spinner("Scanning reflog and checking for dangling objects..."):
        result = run_recover()

    print_response(result, title="Recovery Plan")


# ---------------------------------------------------------------------------
# gitmind suggest
# ---------------------------------------------------------------------------

@app.command()
def suggest():
    """
    💡 Get proactive suggestions and safety checks for your repository.
    """
    print_banner("GitMind Suggest")

    from workflows.orchestrator import run_suggest

    with spinner("Analyzing repository state..."):
        result = run_suggest()

    print_response(result, title="Suggestions")


# ---------------------------------------------------------------------------
# gitmind explain
# ---------------------------------------------------------------------------

@app.command()
def explain(
    target: str = typer.Argument(..., help="Commit hash, file path, or feature name to explain."),
):
    """
    🔍 Explain a commit, file, or feature.
    """
    print_banner("GitMind Explain")

    from workflows.orchestrator import run_explain

    with spinner(f"Investigating '{target}' with IBM Db2 context..."):
        result = run_explain(target)

    print_response(result, title=f"Explanation: {target}")


# ---------------------------------------------------------------------------
# gitmind project
# ---------------------------------------------------------------------------

@app.command()
def project(
    question: Optional[str] = typer.Argument(None, help="Optional question about the project (default: full overview)."),
):
    """
    🏗️ Understand the current project / repository architecture.
    """
    print_banner("GitMind Project")

    from workflows.orchestrator import run_project

    with spinner("Analyzing project documentation and structure..."):
        result = run_project(query=question or "")

    print_response(result, title="Project Overview")


# ---------------------------------------------------------------------------
# gitmind index
# ---------------------------------------------------------------------------

@app.command()
def index(
    days: int = typer.Option(90, "--days", "-d", help="Number of days of history to index."),
    full: bool = typer.Option(False, "--full", help="Force a full repository re-index."),
    backend: str = typer.Option("db2", "--backend", help="Persistence backend: 'db2' or 'chroma'."),
):
    """
    📇 Index repository data into IBM Db2 Knowledge Graph and Vector Store.
    """
    print_banner("GitMind Index")

    if backend == "db2":
        from data.indexer import get_repository_indexer
        from data.repository_memory import get_repository_memory

        print_info(f"Target backend: IBM Db2 Cloud / Community Edition")
        print_info(f"Indexing mode: {'FULL' if full else 'INCREMENTAL'} (history depth: {days} days)")

        with spinner("Ensuring repository registration and running Db2 indexer..."):
            memory = get_repository_memory()
            repo_id = memory.ensure_repository_registered(".")
            indexer = get_repository_indexer()
            stats = indexer.index_repository(repo_path=".", full=full, days=days)

        print_success(
            f"Db2 Indexing Complete!\n"
            f"- Repository ID: {stats.get('repo_id')}\n"
            f"- Mode: {stats.get('mode')}\n"
            f"- Indexed Artifacts: {stats.get('indexed_artifacts')}\n"
            f"- Generated Vector Chunks: {stats.get('generated_chunks')}\n"
            f"- Head SHA: {stats.get('head_sha')[:8]}"
        )

    else:
        # Legacy ChromaDB path
        from tools.story.get_commits import get_recent_commits
        from embeddings.vector_store import GitMindVectorStore

        print_info(f"Target backend: ChromaDB (legacy)")
        commits = get_recent_commits(days=days)
        if not commits:
            print_warning("No commits found to index.")
            return

        with spinner(f"Embedding {len(commits)} commits into ChromaDB..."):
            store = GitMindVectorStore()
            store.index_commits(commits)

        print_success(f"Indexed {len(commits)} commits into ChromaDB.")


# ---------------------------------------------------------------------------
# gitmind db2 subcommands
# ---------------------------------------------------------------------------

@db2_app.command(name="doctor")
def db2_doctor():
    """
    🩺 Run comprehensive diagnostics on IBM Db2 connection & vector capabilities.
    """
    print_banner("GitMind Db2 Doctor")

    from data.db2.connection import get_connection_manager

    mgr = get_connection_manager()
    print_info(f"Probing IBM Db2 at {mgr.host}:{mgr.port}/{mgr.database} (SSL: {mgr.ssl})...")

    with spinner("Running capability detection..."):
        caps = mgr.check_capabilities()

    table = Table(title="IBM Db2 Diagnostics Report", show_lines=True)
    table.add_column("Diagnostic Check", style="cyan", no_wrap=True)
    table.add_column("Result", style="bold")
    table.add_column("Details", style="dim")

    # Connectivity
    table.add_row(
        "Connection Status",
        "[green]SUCCESS[/green]" if caps.connected else "[red]FAILED[/red]",
        f"{mgr.host}:{mgr.port}/{mgr.database}",
    )

    # Server Version
    table.add_row(
        "Db2 Server Version",
        f"[green]{caps.server_version_raw or 'Unknown'}[/green]" if caps.connected else "[dim]N/A[/dim]",
        f"Parsed: {caps.parsed_version}",
    )

    # Native Vector Support (12.1.2+)
    vec_status = (
        "[green]SUPPORTED (v12.1.2+)[/green]"
        if caps.native_vector_supported
        else "[yellow]LIMITED / EXACT SEARCH[/yellow]"
    )
    table.add_row(
        "Native VECTOR Data Type",
        vec_status,
        "Requires Db2 12.1.2+ for native vector columns",
    )

    # Vector Index (12.1.5+)
    idx_status = (
        "[green]SUPPORTED (v12.1.5+)[/green]"
        if caps.vector_index_supported
        else "[dim]Exact KNN fallback (Pre-12.1.5)[/dim]"
    )
    table.add_row(
        "Native ANN Vector Index",
        idx_status,
        "Requires Db2 12.1.5+ for native approximate vector indexing",
    )

    # VECTOR_DISTANCE function probe
    vd_status = (
        "[green]VERIFIED ON SERVER[/green]"
        if caps.vector_distance_verified
        else "[red]NOT VERIFIED[/red]"
    )
    table.add_row(
        "VECTOR_DISTANCE Probe",
        vd_status,
        f"Test result: {caps.details.get('vector_distance_test_result', 'N/A')}",
    )

    # Schema & Tables
    table.add_row(
        f"Schema '{mgr.schema}'",
        "[green]EXISTS[/green]" if caps.schema_exists else "[yellow]NOT CREATED (Run 'gitmind db2 migrate')[/yellow]",
        f"Configured schema: {mgr.schema}",
    )
    table.add_row(
        f"Vector Table '{config.DB2_VECTOR_TABLE}'",
        "[green]EXISTS[/green]" if caps.vector_table_exists else "[yellow]NOT CREATED[/yellow]",
        "Official DB2VS vector table",
    )

    rich_console.print(table)

    if caps.errors:
        print_error("Detected Issues:")
        for err in caps.errors:
            rich_console.print(f"  • {err}")


@db2_app.command(name="test")
def db2_test():
    """
    ⚡ Test live round-trip connectivity to IBM Db2.
    """
    print_banner("GitMind Db2 Test")

    from data.db2.connection import get_connection_manager

    mgr = get_connection_manager()
    print_info(f"Testing live round-trip to {mgr.host}:{mgr.port}...")

    try:
        with spinner("Pinging database..."):
            with mgr.cursor() as cur:
                cur.execute("SELECT 1 FROM SYSIBM.SYSDUMMY1")
                row = cur.fetchone()
        if row and row[0] == 1:
            print_success("IBM Db2 connection test PASSED successfully!")
        else:
            print_warning("Db2 connection succeeded but ping query returned unexpected result.")
    except Exception as e:
        print_error(f"Db2 connection test FAILED: {e}")
        raise typer.Exit(1)


@db2_app.command(name="migrate")
def db2_migrate():
    """
    📦 Run versioned schema migrations against IBM Db2.
    """
    print_banner("GitMind Db2 Migrate")

    from data.db2.migrations import SchemaMigrationManager

    mig_mgr = SchemaMigrationManager()
    print_info(f"Target schema: {mig_mgr.manager.schema}")

    with spinner("Applying versioned migrations..."):
        applied = mig_mgr.apply_migrations()

    if applied:
        print_success(f"Successfully applied {len(applied)} migrations:\n" + "\n".join(f"- {m}" for m in applied))
    else:
        print_info("Schema is already up to date. No new migrations applied.")

    with spinner("Verifying table integrity..."):
        verification = mig_mgr.verify_schema()

    table = Table(title="Verified Schema Objects", show_lines=False)
    table.add_column("Table Name", style="cyan")
    table.add_column("Status", style="bold")
    for tbl, ok in verification.items():
        table.add_row(tbl, "[green]READY[/green]" if ok else "[red]MISSING[/red]")
    rich_console.print(table)


@db2_app.command(name="status")
def db2_status():
    """
    📊 Display repository intelligence and vector statistics stored in IBM Db2.
    """
    print_banner("GitMind Db2 Status")

    from data.db2.connection import get_connection_manager
    from utils.repo_utils import get_repo_id, get_repo_key

    mgr = get_connection_manager()
    repo_id = get_repo_id(".")
    repo_key = get_repo_key(".")

    print_info(f"Inspecting repository '{repo_key}' (ID: `{repo_id}`) in Db2...")

    table = Table(title="GitMind 2.0 Repository Intelligence", show_lines=True)
    table.add_column("Intelligence Category", style="cyan")
    table.add_column("Db2 Table", style="dim")
    table.add_column("Record Count", style="bold green")

    try:
        with mgr.cursor() as cur:
            queries = [
                ("Repositories", "GITMIND_REPOSITORIES", "SELECT COUNT(*) FROM GITMIND_REPOSITORIES"),
                ("Commits & Artifacts", "GITMIND_ARTIFACTS", "SELECT COUNT(*) FROM GITMIND_ARTIFACTS WHERE REPO_ID = ?"),
                ("Knowledge Graph Relations", "GITMIND_RELATIONS", "SELECT COUNT(*) FROM GITMIND_RELATIONS WHERE REPO_ID = ?"),
                ("Index Runs", "GITMIND_INDEX_RUNS", "SELECT COUNT(*) FROM GITMIND_INDEX_RUNS WHERE REPO_ID = ?"),
                ("Agent Runs", "GITMIND_AGENT_RUNS", "SELECT COUNT(*) FROM GITMIND_AGENT_RUNS WHERE REPO_ID = ?"),
                ("Persistent Findings", "GITMIND_FINDINGS", "SELECT COUNT(*) FROM GITMIND_FINDINGS WHERE REPO_ID = ?"),
                ("Finding Evidence Links", "GITMIND_FINDING_EVIDENCE", "SELECT COUNT(*) FROM GITMIND_FINDING_EVIDENCE"),
                ("Audit Trail Events", "GITMIND_AUDIT_EVENTS", "SELECT COUNT(*) FROM GITMIND_AUDIT_EVENTS WHERE REPO_ID = ?"),
                ("Vector Embeddings (Chunks)", config.DB2_VECTOR_TABLE, f"SELECT COUNT(*) FROM {config.DB2_VECTOR_TABLE}"),
            ]

            for label, tbl_name, q in queries:
                try:
                    if "?" in q:
                        cur.execute(q, (repo_id,))
                    else:
                        cur.execute(q)
                    cnt = cur.fetchone()[0]
                    table.add_row(label, tbl_name, str(cnt))
                except Exception:
                    table.add_row(label, tbl_name, "[yellow]Table not migrated[/yellow]")

        rich_console.print(table)

    except Exception as e:
        print_error(f"Could not retrieve Db2 status: {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# gitmind memory subcommands
# ---------------------------------------------------------------------------

@memory_app.command(name="search")
def memory_search(
    query: str = typer.Argument(..., help="Search query for previous engineering investigations and findings."),
    top_k: int = typer.Option(5, "--limit", "-k", help="Number of results to retrieve."),
):
    """
    🧠 Search persistent engineering memory and previous findings in IBM Db2.
    """
    print_banner("GitMind Memory Search")

    from data.repository_memory import get_repository_memory
    from utils.repo_utils import get_repo_id

    repo_id = get_repo_id(".")
    memory = get_repository_memory()

    with spinner(f"Querying persistent findings for '{query}' in Db2..."):
        findings = memory.get_similar_findings(query=query, repo_id=repo_id, top_k=top_k)

    if not findings:
        print_info("No previous engineering findings matched your query.")
        return

    for idx, f in enumerate(findings, 1):
        rich_console.print(
            f"[bold cyan]Finding {idx}: {f.get('title')}[/bold cyan] "
            f"([yellow]{f.get('finding_type')}[/yellow] - Severity: {f.get('severity')})"
        )
        rich_console.print(f"Summary: {f.get('summary')}")
        rich_console.print(f"Agent: {f.get('agent_name')} | Similarity: {f.get('similarity_score')}\n")


if __name__ == "__main__":
    app()
