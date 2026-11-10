"""Capture proven lessons into the knowledge base.

A run that matched proves that a translation works. That
proof is worth keeping, so the next run can reuse it.

A captured entry starts as a candidate. It is never served
by search until a human approves it. The entry keeps the
run id that proved it.

Only a query that matched and that was rewritten becomes an
entry. A query that matched without a rewrite teaches
nothing, and a query that failed proves nothing.
"""

from __future__ import annotations

import hashlib

from parity.history.types import RunRecord
from parity.kb.store import KnownDifference

_MATCH = "MATCH"
_TITLE_LIMIT = 180
_PATTERN_LIMIT = 1900


def _short(sql: str, limit: int = 90) -> str:
    """Return one readable line of SQL."""
    text = " ".join(sql.split())
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def build_title(rules: tuple[str, ...], source_sql: str) -> str:
    """Return a stable title for one entry."""
    raw = f"{'+'.join(rules)}|{source_sql}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:6]
    title = f"{'+'.join(rules) or 'rewrite'} {digest}: {_short(source_sql, 100)}"
    return title[:_TITLE_LIMIT]


def candidates_from_run(run: RunRecord) -> list[KnownDifference]:
    """Build the knowledge base candidates of one run."""
    candidates: list[KnownDifference] = []
    for record in run.records:
        if record.status != _MATCH:
            continue
        if not record.applied_rules:
            continue
        if record.source_sql == record.db2_sql:
            continue
        candidates.append(
            KnownDifference(
                title=build_title(record.applied_rules, record.source_sql),
                source_pattern=record.source_sql[:_PATTERN_LIMIT],
                db2_pattern=record.db2_sql[:_PATTERN_LIMIT],
                cause="translation rules: " + ", ".join(record.applied_rules),
                fix_template=record.db2_sql[:_PATTERN_LIMIT],
                verified=False,
                evidence_run_id=run.run_id,
            )
        )
    return candidates


def capture_run(store, run: RunRecord) -> tuple[int, int]:
    """Store the candidates of one run.

    Return the number of entries added and the number that
    were skipped because the store already had them.
    """
    known = {entry.title for entry in store.list_candidates()}
    added = 0
    skipped = 0
    for candidate in candidates_from_run(run):
        if candidate.title in known:
            skipped += 1
            continue
        store.add(candidate)
        known.add(candidate.title)
        added += 1
    return added, skipped
