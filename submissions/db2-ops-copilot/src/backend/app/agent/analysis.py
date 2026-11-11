"""Root-cause analysis over collected evidence (pure, deterministic, testable).

Input: evidence items produced by the collection nodes. Output: ranked
findings, recommendations (some carrying a structured *action proposal*) and a
single probable root cause.

The rules encode ordinary DBA reasoning and are deliberately conservative:

* every claim cites the tool(s) it is based on;
* a conclusion that needs evidence we could not collect becomes an explicit
  ``evidence_gap`` finding instead of a guess;
* nothing here executes anything — actions are only *described*.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.agent.actions import ACTIONS, ActionError, index_name_for, render_statement
from app.adapters.sql_validator.sqlglot_validator import resolve_dialect

# Thresholds (named so the reasoning in findings is auditable).
HOT_MIN_ROWS_READ = 1000
HOT_MIN_SCANS = 100
HOT_SHARE = 0.40
INEFFICIENT_READ_RETURN_RATIO = 5.0
LOW_HIT_RATIO = 0.90
# A lock wait is only *critical* when it is long or widespread.
LOCK_CRITICAL_MS = 5000
LOCK_CRITICAL_COUNT = 3

SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}
_KIND_RANK = (
    "missing_index",
    "lock_waits",
    "hot_table_scans",
    "bufferpool_low",
    "stale_statistics",
    "deadlocks_timeouts",
)

_COMPARISONS = (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Is, exp.In, exp.Between)


# --------------------------------------------------------------------------
# evidence helpers
# --------------------------------------------------------------------------
def rows_of(item: dict[str, Any]) -> list[dict[str, Any]]:
    cols = [str(c).upper() for c in item.get("columns", [])]
    return [dict(zip(cols, row)) for row in item.get("rows", [])]


def find_evidence(
    evidence: list[dict[str, Any]], tool_id: str, table: str | None = None, ok_only: bool = True
) -> list[dict[str, Any]]:
    out = []
    for item in evidence:
        if item.get("tool_id") != tool_id:
            continue
        if ok_only and not item.get("ok"):
            continue
        if table is not None and (item.get("params") or {}).get("table") != table:
            continue
        out.append(item)
    return out


def tables_in_statement(sql: str) -> list[str]:
    """Unqualified table names referenced by a statement (best effort)."""
    names: list[str] = []
    try:
        dialect, _ = resolve_dialect()
        tree = sqlglot.parse_one(sql, dialect=dialect or None)
        found = [t.name.upper() for t in tree.find_all(exp.Table)] if tree else []
    except SqlglotError:
        found = [m.upper().split(".")[-1] for m in re.findall(r"\b(?:FROM|JOIN)\s+([\w.$#@]+)", sql, re.I)]
    for name in found:
        if name and name not in names:
            names.append(name)
    return names


def predicate_columns(sql: str) -> dict[str, list[str]]:
    """Columns used in sargable predicates (WHERE / JOIN ... ON), per table.

    ``{"DEMO_INCIDENTS": ["RESOLVED_AT"]}`` for
    ``... FROM APP.DEMO_INCIDENTS WHERE RESOLVED_AT IS NULL``. Columns wrapped
    in functions are skipped (not index-friendly). Unqualified columns are only
    attributed when the statement touches a single table.
    """
    try:
        dialect, _ = resolve_dialect()
        tree = sqlglot.parse_one(sql, dialect=dialect or None)
    except SqlglotError:
        return {}
    if tree is None:
        return {}
    alias_to_table = {t.alias_or_name.upper(): t.name.upper() for t in tree.find_all(exp.Table)}
    distinct_tables = sorted(set(alias_to_table.values()))
    scopes: list[exp.Expression] = [w for w in tree.find_all(exp.Where)]
    scopes += [j.args["on"] for j in tree.find_all(exp.Join) if j.args.get("on") is not None]

    result: dict[str, list[str]] = {}
    for scope in scopes:
        for col in scope.find_all(exp.Column):
            parent = col.parent
            if not isinstance(parent, _COMPARISONS):
                continue
            if isinstance(parent, exp.In) and col is not parent.this:
                continue
            qualifier = col.table.upper() if col.table else ""
            if qualifier:
                table = alias_to_table.get(qualifier)
            elif len(distinct_tables) == 1:
                table = distinct_tables[0]
            else:
                table = None
            if table is None:
                continue
            name = col.name.upper()
            bucket = result.setdefault(table, [])
            if name not in bucket:
                bucket.append(name)
    return result


def find_hot_table(activity_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The table dominating read activity through full scans, if any.

    Shared by the planner (follow-up tool selection) and the analysis so the
    two can never disagree about what "hot" means.
    """
    if not activity_rows:
        return None
    total = sum(int(r.get("ROWS_READ") or 0) for r in activity_rows)
    top = max(activity_rows, key=lambda r: int(r.get("ROWS_READ") or 0))
    read, scans = int(top.get("ROWS_READ") or 0), int(top.get("TABLE_SCANS") or 0)
    if total and read >= HOT_MIN_ROWS_READ and scans >= HOT_MIN_SCANS and read / total >= HOT_SHARE:
        return {"table": str(top["TABNAME"]).upper(), "rows_read": read, "scans": scans, "total": total}
    return None


def leading_columns(index_rows: list[dict[str, Any]]) -> set[str]:
    """First key column of every index (``COLNAMES`` like ``+A+B`` / ``-TS``)."""
    leading: set[str] = set()
    for row in index_rows:
        match = re.match(r"\s*[+\-*]?([A-Za-z0-9_$#@]+)", str(row.get("COLNAMES") or ""))
        if match:
            leading.add(match.group(1).upper())
    return leading


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed.replace(tzinfo=None)


def _word_in(name: str, text: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9_$#@]){re.escape(name)}(?![A-Za-z0-9_$#@])", text.upper()) is not None


# --------------------------------------------------------------------------
# finding / recommendation builders
# --------------------------------------------------------------------------
def _finding(
    fid: str,
    kind: str,
    severity: str,
    title: str,
    detail: str,
    tools: list[str],
    *,
    confidence: str = "medium",
    table: str | None = None,
) -> dict[str, Any]:
    return {
        "id": fid,
        "kind": kind,
        "severity": severity,
        "confidence": confidence,
        "title": title,
        "detail": detail,
        "evidence": tools,
        "table": table,
    }


def _action(action_type: str, schema: str, table: str, column: str | None = None) -> dict[str, Any] | None:
    params = {"schema": schema, "table": table}
    if action_type == "create_index":
        params["column"] = column or ""
    try:
        statement = render_statement(action_type, params)
    except ActionError:
        return None
    return {"type": action_type, "params": params, "statement": statement}


def _rec(
    rid: str,
    title: str,
    rationale: str,
    finding_id: str,
    priority: int,
    action: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": rid,
        "title": title,
        "rationale": rationale,
        "finding_id": finding_id,
        "priority": priority,
        "action": action,
        "requires_approval": action is not None,
    }


# --------------------------------------------------------------------------
# the analysis
# --------------------------------------------------------------------------
def analyze_evidence(
    evidence: list[dict[str, Any]],
    *,
    intent: str,
    entities: dict[str, Any],
    schema: str,
    now: datetime,
    stale_days: int,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    recs: list[dict[str, Any]] = []
    now_naive = now.replace(tzinfo=None)

    activity = next(iter(find_evidence(evidence, "monitor.table_activity")), None)
    slow = next(iter(find_evidence(evidence, "monitor.slow_statements")), None)
    stmts = rows_of(slow) if slow else []
    activity_rows = rows_of(activity) if activity else []

    hot_table: str | None = None

    # -- 1. hot tables read by full scans -----------------------------------
    hot = find_hot_table(activity_rows)
    if hot:
        if True:
            hot_table = hot["table"]
            read, scans, total = hot["rows_read"], hot["scans"], hot["total"]
            related = sorted(
                (s for s in stmts if _word_in(hot_table, str(s.get("STMT_TEXT") or ""))),
                key=lambda s: -int(s.get("TOTAL_ACT_TIME") or 0),
            )
            extra = ""
            if related:
                s = related[0]
                extra = (
                    f" The costliest statement touching it ran {s.get('NUM_EXECUTIONS')} times "
                    f"(avg {s.get('AVG_ACT_TIME_MS')} ms), reading {s.get('ROWS_READ')} rows to "
                    f"return {s.get('ROWS_RETURNED')}."
                )
            findings.append(
                _finding(
                    f"hot_table_scans:{hot_table}",
                    "hot_table_scans",
                    "warning",
                    f"{hot_table} is read mostly by full table scans",
                    f"{hot_table} accounts for {read / total:.0%} of all rows read ({read} rows, "
                    f"{scans} table scans).{extra}",
                    ["monitor.table_activity"] + (["monitor.slow_statements"] if related else []),
                    confidence="high" if related else "medium",
                    table=hot_table,
                )
            )

    # -- 2. missing index for sargable predicates ----------------------------
    sql_sources: list[tuple[str, int, str]] = []  # (sql, weight, evidence tool)
    for s in stmts:
        text = str(s.get("STMT_TEXT") or "")
        reads, returned = int(s.get("ROWS_READ") or 0), max(int(s.get("ROWS_RETURNED") or 0), 1)
        if reads / returned >= INEFFICIENT_READ_RETURN_RATIO or (hot_table and _word_in(hot_table, text)):
            sql_sources.append((text, max(int(s.get("NUM_EXECUTIONS") or 1), 1), "monitor.slow_statements"))
    # EXPLAIN may be unavailable (no EXPLAIN tables) yet the statement still
    # passed the safety gate, so predicate analysis remains valid.
    explain_ev = next(
        (
            e
            for e in evidence
            if e.get("tool_id") == "sql.explain" and (e.get("extra") or {}).get("gate_passed")
        ),
        None,
    )
    if explain_ev and entities.get("sql"):
        sql_sources.append((str(entities["sql"]), 1, "sql.explain"))

    weights: dict[tuple[str, str], int] = {}
    used_tools: dict[tuple[str, str], set[str]] = {}
    for sql, weight, tool in sql_sources:
        for table, columns in predicate_columns(sql).items():
            for column in columns:
                weights[(table, column)] = weights.get((table, column), 0) + weight
                used_tools.setdefault((table, column), set()).add(tool)

    gap_tables: set[str] = set()
    best_per_table: dict[str, tuple[str, int]] = {}
    for (table, column), weight in sorted(weights.items(), key=lambda kv: -kv[1]):
        idx = find_evidence(evidence, "catalog.indexes", table)
        if not idx or not rows_of(idx[0]):
            # No index list (failed, or the table lives in another schema):
            # concluding "no index" would be a guess.
            gap_tables.add(table)
            continue
        if column in leading_columns(rows_of(idx[0])):
            continue
        best_per_table.setdefault(table, (column, weight))

    for table, (column, weight) in best_per_table.items():
        hot = table == hot_table
        tools = sorted(used_tools[(table, column)]) + ["catalog.indexes"]
        fid = f"missing_index:{table}:{column}"
        findings.append(
            _finding(
                fid,
                "missing_index",
                "warning",
                f"No index leads with {table}.{column}",
                f"Queries filter {table} on {column}, but none of its indexes starts with that "
                f"column, so Db2 must scan the table"
                + (" — consistent with the heavy scan activity above." if hot else "."),
                tools,
                confidence="high" if hot else "medium",
                table=table,
            )
        )
        action = _action("create_index", schema, table, column)
        recs.append(
            _rec(
                f"rec:create_index:{table}:{column}",
                f"Create an index on {table}({column})",
                f"Weighted by {weight} observed execution(s). Test with EXPLAIN first; the index "
                "adds write overhead and build time.",
                fid,
                1,
                action,
            )
        )

    for table in sorted(gap_tables - set(best_per_table)):
        findings.append(
            _finding(
                f"evidence_gap:indexes:{table}",
                "evidence_gap",
                "info",
                f"Index definitions for {table} unavailable",
                f"Predicates on {table} were found, but its index list could not be collected, so "
                "no index conclusion is drawn.",
                ["catalog.indexes"],
                table=table,
            )
        )

    # -- 3. stale / missing statistics -----------------------------------------
    stats_ev = next(iter(find_evidence(evidence, "catalog.stale_statistics")), None)
    if stats_ev:
        stale: list[tuple[str, str]] = []
        for r in rows_of(stats_ev):
            name = str(r.get("TABNAME"))
            ts = _parse_ts(r.get("STATS_TIME"))
            if r.get("STATS_STATUS") == "NO_STATS":
                stale.append((name, "no statistics collected"))
            elif ts is not None and (now_naive - ts).days > stale_days:
                stale.append((name, f"last collected {(now_naive - ts).days} days ago"))
        if stale:
            stale.sort(key=lambda t: (t[0] != hot_table, t[0]))
            findings.append(
                _finding(
                    "stale_statistics",
                    "stale_statistics",
                    "warning",
                    f"{len(stale)} table(s) with missing or stale statistics",
                    "; ".join(f"{n}: {why}" for n, why in stale)
                    + ". Outdated statistics can push the optimizer into poor plans (e.g. scans)."
                    + (f" {hot_table} is also the hottest table." if hot_table in {n for n, _ in stale} else ""),
                    ["catalog.stale_statistics"],
                    confidence="high" if hot_table in {n for n, _ in stale} else "medium",
                )
            )
            for name, why in stale[:3]:
                recs.append(
                    _rec(
                        f"rec:runstats:{name}",
                        f"Collect statistics on {name}",
                        f"{name}: {why}. RUNSTATS is low risk and changes no data.",
                        "stale_statistics",
                        2,
                        _action("runstats", schema, name),
                    )
                )
        elif intent == "statistics":
            findings.append(
                _finding(
                    "statistics_ok",
                    "statistics_ok",
                    "info",
                    "Statistics are current",
                    f"Every table has statistics collected within the last {stale_days} days.",
                    ["catalog.stale_statistics"],
                )
            )

    # -- 4. lock waits / deadlocks --------------------------------------------------
    locks_ev = next(iter(find_evidence(evidence, "monitor.lock_waits")), None)
    conn_ev = next(iter(find_evidence(evidence, "monitor.connections")), None)
    conn_rows = {int(r["APPLICATION_HANDLE"]): r for r in rows_of(conn_ev)} if conn_ev else {}
    if locks_ev and rows_of(locks_ev):
        waiting = rows_of(locks_ev)
        handles = sorted({int(r["APPLICATION_HANDLE"]) for r in waiting})
        who = []
        for h in handles:
            c = conn_rows.get(h)
            who.append(
                f"application {h}"
                + (f" ({c.get('APPLICATION_NAME')}, {c.get('LOCK_WAIT_TIME')} ms lock wait)" if c else "")
            )
        longest = max(
            (int((conn_rows.get(h) or {}).get("LOCK_WAIT_TIME") or 0) for h in handles),
            default=0,
        )
        severe = len(waiting) >= LOCK_CRITICAL_COUNT or longest >= LOCK_CRITICAL_MS
        findings.append(
            _finding(
                "lock_waits",
                "lock_waits",
                "critical" if severe else "warning",
                f"{len(waiting)} lock(s) currently waiting",
                "Waiting: " + ", ".join(who) + ". Another transaction is holding conflicting locks.",
                ["monitor.lock_waits"] + (["monitor.connections"] if conn_rows else []),
                confidence="high",
            )
        )
        recs.append(
            _rec(
                "rec:investigate_locks",
                "Identify the lock holder and shorten its transaction",
                "Find the holder (MON_GET_APPL_LOCKWAIT or `db2pd -db <name> -locks wait`), review "
                "its commit frequency and isolation level. The copilot never forces applications off.",
                "lock_waits",
                1,
            )
        )
    if conn_rows:
        hurting = [r for r in conn_rows.values() if int(r.get("DEADLOCKS") or 0) or int(r.get("LOCK_TIMEOUTS") or 0)]
        if hurting:
            findings.append(
                _finding(
                    "deadlocks_timeouts",
                    "deadlocks_timeouts",
                    "warning",
                    f"{len(hurting)} connection(s) with deadlocks or lock timeouts",
                    "; ".join(
                        f"app {r['APPLICATION_HANDLE']}: {r.get('DEADLOCKS')} deadlock(s), "
                        f"{r.get('LOCK_TIMEOUTS')} timeout(s)"
                        for r in hurting
                    ),
                    ["monitor.connections"],
                )
            )

    # -- 5. buffer pool ----------------------------------------------------------------
    bp_ev = next(iter(find_evidence(evidence, "monitor.bufferpool_hit_ratio")), None)
    if bp_ev:
        low = [r for r in rows_of(bp_ev) if r.get("HIT_RATIO") is not None and float(r["HIT_RATIO"]) < LOW_HIT_RATIO]
        if low:
            findings.append(
                _finding(
                    "bufferpool_low",
                    "bufferpool_low",
                    "warning",
                    "Low buffer pool hit ratio",
                    "; ".join(f"{r['BP_NAME']}: {float(r['HIT_RATIO']):.1%}" for r in low)
                    + f" (threshold {LOW_HIT_RATIO:.0%}).",
                    ["monitor.bufferpool_hit_ratio"],
                )
            )
            recs.append(
                _rec(
                    "rec:bufferpool",
                    "Review buffer pool sizing and scan-heavy queries",
                    "A low hit ratio means many physical reads: fix scans first, then consider "
                    "enlarging the pool (ALTER BUFFERPOOL is a manual DBA decision).",
                    "bufferpool_low",
                    3,
                )
            )
        else:
            rows = rows_of(bp_ev)
            findings.append(
                _finding(
                    "bufferpool_ok",
                    "bufferpool_ok",
                    "info",
                    "Buffer pool hit ratio is healthy",
                    "; ".join(
                        f"{r['BP_NAME']}: {float(r['HIT_RATIO']):.1%}" for r in rows if r.get("HIT_RATIO") is not None
                    ),
                    ["monitor.bufferpool_hit_ratio"],
                )
            )

    # -- 6. unused indexes ------------------------------------------------------------------
    usage_ev = next(iter(find_evidence(evidence, "monitor.index_usage")), None)
    if usage_ev:
        unused = [r for r in rows_of(usage_ev) if int(r.get("INDEX_SCANS") or 0) == 0]
        if unused:
            findings.append(
                _finding(
                    "unused_indexes",
                    "unused_indexes",
                    "info",
                    f"{len(unused)} index(es) with no scans since the counters started",
                    ", ".join(f"{r['TABNAME']}.{r['INDNAME']}" for r in unused),
                    ["monitor.index_usage"],
                    confidence="low",
                )
            )
            recs.append(
                _rec(
                    "rec:review_unused_indexes",
                    "Review unused indexes over a longer window before any change",
                    "Usage counters reset on database deactivation, and an index may serve "
                    "constraints or rare jobs. The copilot never proposes DROP INDEX.",
                    "unused_indexes",
                    4,
                )
            )

    # -- 7. user-requested maintenance ---------------------------------------------------------
    action_req = entities.get("action")
    if intent == "maintenance" and action_req:
        tables_ev = next(iter(find_evidence(evidence, "catalog.tables")), None)
        names = {str(r["TABNAME"]).upper() for r in rows_of(tables_ev)} if tables_ev else set()
        target = action_req.get("table")
        if tables_ev and target not in names:
            findings.append(
                _finding(
                    "table_not_found",
                    "table_not_found",
                    "warning",
                    f"Table {target} was not found in schema {schema}",
                    "No action was proposed. Check the name with: 'list tables'.",
                    ["catalog.tables"],
                )
            )
        elif not tables_ev:
            findings.append(
                _finding(
                    "evidence_gap:tables",
                    "evidence_gap",
                    "warning",
                    "Could not verify that the table exists",
                    "The catalog could not be read, so no action was proposed.",
                    ["catalog.tables"],
                )
            )
        else:
            skip = None
            if action_req["type"] == "create_index":
                idx = find_evidence(evidence, "catalog.indexes", target)
                if idx and action_req["column"] in leading_columns(rows_of(idx[0])):
                    skip = f"{target} already has an index leading with {action_req['column']}."
            if skip:
                findings.append(
                    _finding("already_indexed", "already_indexed", "info", "Index already exists", skip, ["catalog.indexes"], table=target)
                )
            else:
                spec = ACTIONS[action_req["type"]]
                findings.append(
                    _finding(
                        "requested_action",
                        "requested_action",
                        "info",
                        f"Requested: {spec.title} on {target}",
                        "The table exists. The action is proposed below and needs your approval; "
                        "nothing has been executed.",
                        ["catalog.tables"],
                        table=target,
                    )
                )
                recs.append(
                    _rec(
                        f"rec:{action_req['type']}:{target}",
                        f"{spec.title}: {schema}.{target}",
                        spec.impact,
                        "requested_action",
                        1,
                        _action(action_req["type"], schema, target, action_req.get("column")),
                    )
                )

    # -- 8. evidence we could not collect -----------------------------------------------------------
    for item in evidence:
        if item.get("ok"):
            continue
        err = item.get("error") or {}
        code = err.get("code", "ERROR")
        sev = "warning" if code in {"DB_PERMISSION_DENIED", "ADAPTER_UNAVAILABLE"} else "info"
        findings.append(
            _finding(
                f"evidence_gap:{item['tool_id']}",
                "evidence_gap",
                sev,
                f"Could not collect {item.get('title', item['tool_id'])}",
                f"{code}: {err.get('message', 'unknown error')}",
                [item["tool_id"]],
                table=(item.get("params") or {}).get("table"),
            )
        )
        if code == "DB_PERMISSION_DENIED":
            recs.append(
                _rec(
                    f"rec:grant:{item['tool_id']}",
                    "Grant monitoring privileges to the diagnostic account",
                    "See database/migrations/005_dba_tools.sql (EXECUTE on MON_GET_* plus "
                    "SQLADM/DATAACCESS); prefer a dedicated monitoring account.",
                    f"evidence_gap:{item['tool_id']}",
                    3,
                )
            )

    # -- 9. nothing wrong -------------------------------------------------------------------------------
    diagnostic = intent in {"performance", "locks", "memory", "indexes", "statistics", "connections"}
    if diagnostic and not any(f["severity"] in {"warning", "critical"} for f in findings):
        collected = sorted({e["tool_id"] for e in evidence if e.get("ok")})
        if collected:
            findings.append(
                _finding(
                    "no_issues",
                    "no_issues",
                    "info",
                    "No bottleneck detected in the collected evidence",
                    "Checked: " + ", ".join(collected) + ". This covers only those signals.",
                    collected,
                )
            )

    findings.sort(key=lambda f: (SEVERITY_RANK.get(f["severity"], 3), _kind_rank(f["kind"])))
    recs.sort(key=lambda r: r["priority"])
    seen: set[str] = set()
    unique_recs = []
    for r in recs:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique_recs.append(r)

    return {
        "findings": findings,
        "recommendations": unique_recs,
        "root_cause": _root_cause(findings),
    }


def _kind_rank(kind: str) -> int:
    return _KIND_RANK.index(kind) if kind in _KIND_RANK else len(_KIND_RANK)


def _root_cause(findings: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [f for f in findings if f["kind"] in _KIND_RANK and f["severity"] in {"critical", "warning"}]
    if not candidates:
        return None
    top = min(candidates, key=lambda f: (SEVERITY_RANK[f["severity"]], _kind_rank(f["kind"])))
    return {
        "finding_id": top["id"],
        "kind": top["kind"],
        "confidence": top["confidence"],
        "summary": f"{top['title']}. {top['detail']}",
    }
