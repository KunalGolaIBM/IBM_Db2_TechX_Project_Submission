"""End to end run pipeline.

Ingest a directory of SQL files, translate each query,
compare on both databases, and collect report entries.
Schema and data sync happens before this step. The
pipeline assumes both databases already hold the
same data.

Translation is rules first. Queries the rules cannot
handle go to the optional gateway (an agent proposes,
the engine still decides). In replay mode the gateway
serves recorded responses only and never touches the
network.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from parity.agents.prompts import system_prompt
from parity.agents.types import AgentRole
from parity.engine.executor import DatabaseExecutor
from parity.engine.result import ComparisonResult, ComparisonStatus
from parity.engine.safety import validate_row_limit
from parity.gateway.client import Gateway
from parity.gateway.types import BudgetExceededError, CacheMissError
from parity.ingest.loader import deduplicate, load_sql_dir
from parity.report.risk import QueryReport
from parity.runner import run_comparison
from parity.translate.rules import translate


def quote_table(db2_sql: str, table: str | None) -> str:
    """Quote the source table name in the Db2 SQL."""
    if table:
        return db2_sql.replace(table, f'"{table.upper()}"', 1)
    return db2_sql


def _agent_translate(
    query_id: str, source_sql: str, gateway: Gateway
) -> tuple[str, str]:
    """Ask the gateway agent for Db2 SQL.

    Return (db2_sql, ""). On failure return ("", reason).
    """
    user = f"Translate this PostgreSQL query to Db2:\n{source_sql}"
    try:
        response = gateway.complete(
            "translator", system_prompt(AgentRole.TRANSLATOR), user
        )
    except CacheMissError:
        return "", f"{query_id}: replay cache miss, call was not recorded"
    except BudgetExceededError:
        return "", f"{query_id}: token budget exhausted"
    sql = response.text.strip()
    if not sql:
        return "", f"{query_id}: agent returned empty SQL"
    return sql, ""


def _process_query(
    query, source, target, gateway, schema=None, fix_loop: bool = False
) -> QueryReport:
    """Run one query through translate and compare."""
    if not query.read_only:
        result = ComparisonResult(
            status=ComparisonStatus.NOT_COMPARABLE,
            note="write query: not executed",
        )
        return QueryReport.from_result(query.query_id, query.source_sql, "", result)
    translation = translate(query.source_sql, schema=schema)
    if translation.untranslatable:
        if gateway is None:
            result = ComparisonResult(
                status=ComparisonStatus.NOT_COMPARABLE,
                note="untranslatable by rules "
                f"({', '.join(translation.untranslatable)}); "
                "no agent gateway configured",
            )
            return QueryReport.from_result(query.query_id, query.source_sql, "", result)
        agent_sql, failure = _agent_translate(
            query.query_id, query.source_sql, gateway
        )
        if failure or not agent_sql:
            note = failure or "agent returned empty SQL"
            result = ComparisonResult(
                status=ComparisonStatus.NOT_COMPARABLE,
                note=f"agent translation failed: {note}",
            )
            return QueryReport.from_result(query.query_id, query.source_sql, "", result)
        db2_sql = quote_table(agent_sql, query.tables[0] if query.tables else None)
        applied_rules = ("agent_translation",)
    else:
        db2_sql = quote_table(
            translation.db2_sql, query.tables[0] if query.tables else None
        )
        applied_rules = translation.applied_rules
    result = run_comparison(source, target, query.source_sql, db2_sql)
    if fix_loop and result.status is ComparisonStatus.MISMATCH:
        from parity.agents.loop import run_fix_loop

        table = query.tables[0] if query.tables else None
        outcome = run_fix_loop(
            query.source_sql,
            db2_sql,
            result,
            source,
            target,
            gateway,
            table=table,
        )
        if outcome.is_fixed:
            result = ComparisonResult(
                status=ComparisonStatus.MATCH,
                note=outcome.note,
                settings=result.settings,
            )
            db2_sql = outcome.final_sql
            applied_rules = ("agent_fix",)
        elif outcome.note:
            result = ComparisonResult(
                status=result.status,
                diffs=result.diffs,
                settings=result.settings,
                note=outcome.note,
            )
    return QueryReport.from_result(
        query.query_id,
        query.source_sql,
        db2_sql,
        result,
        applied_rules=applied_rules,
    )


def run_pipeline(
    workload_dir: Path,
    source: DatabaseExecutor,
    target: DatabaseExecutor,
    gateway: Gateway | None = None,
    concurrency: int = 1,
    schema=None,
    fix_loop: bool = False,
) -> list[QueryReport]:
    """Run the full pipeline. Return report entries.

    The optional schema gives the translator the column
    types, so a type aware rule can fire. With fix_loop a
    mismatch goes to the agent loop, which tries to fix it
    and proves the fix on both databases.
    """
    validate_row_limit(concurrency)
    queries = deduplicate(load_sql_dir(workload_dir))
    if concurrency == 1:
        return [
            _process_query(query, source, target, gateway, schema, fix_loop)
            for query in queries
        ]
    indexed: list[tuple[int, QueryReport]] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(
                _process_query, query, source, target, gateway, schema, fix_loop
            ): index
            for index, query in enumerate(queries)
        }
        for future in as_completed(futures):
            indexed.append((futures[future], future.result()))
    indexed.sort(key=lambda pair: pair[0])
    return [report for _, report in indexed]
