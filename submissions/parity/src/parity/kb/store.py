"""Knowledge base store.

Only verified entries are searchable. New fixes
start as candidates. A human approves or rejects
them. Only approved entries are shared.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from parity.kb.embeddings import HashingEmbedder, cosine_distance

KNOWN_DIFFERENCE_DDL = """CREATE TABLE known_difference (
    difference_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    source_pattern VARCHAR(2000) NOT NULL,
    db2_pattern VARCHAR(2000) NOT NULL,
    cause VARCHAR(2000),
    fix_template VARCHAR(2000),
    verified SMALLINT NOT NULL DEFAULT 0,
    evidence_run_id INTEGER,
    embedding VECTOR(384, FLOAT32)
)"""


@dataclass
class KnownDifference:
    """One known difference and its fix."""

    title: str
    source_pattern: str
    db2_pattern: str
    cause: str = ""
    fix_template: str = ""
    verified: bool = False
    evidence_run_id: int | None = None
    category: str = ""
    embedding: tuple[float, ...] = ()

    def search_text(self) -> str:
        """Text used for embedding and search."""
        return f"{self.title} {self.source_pattern} {self.cause}"

    def matches_category(self, category: str) -> bool:
        """True when the entry belongs to the requested category."""
        if not category:
            return True
        wanted = category.lower()
        haystack = f"{self.category} {self.source_pattern} {self.title}".lower()
        if wanted in haystack:
            return True
        func = function_of(self)
        families = {
            "aggregate": {"COUNT", "SUM", "MIN", "MAX", "AVG"},
            "string": {"ILIKE", "LIKE", "UPPER", "TRIM", "SUBSTRING"},
            "limit": {"LIMIT", "OFFSET"},
        }
        return func in families.get(wanted, set())


def function_of(entry: KnownDifference) -> str:
    """Return the leading function name of the source pattern."""
    import re

    match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", entry.source_pattern.strip())
    return match.group(1).upper() if match else ""


@dataclass(frozen=True)
class ScoredDifference:
    """One search hit with its distance."""

    entry: KnownDifference
    distance: float


@dataclass(frozen=True)
class SearchStats:
    """Reuse counters for knowledge base search."""

    searches: int = 0
    hits: int = 0
    misses: int = 0

    @property
    def hit_rate(self) -> float:
        """Share of searches that returned at least one hit."""
        if self.searches == 0:
            return 0.0
        return self.hits / self.searches


def _vector_literal(embedding: tuple[float, ...]) -> str:
    """Build a Db2 VECTOR literal from our own floats.

    Bound parameters cannot carry VECTOR values through
    this driver, so the literal is inlined. Values are
    validated floats from our embedder, never user text.
    """
    if len(embedding) != 384:
        raise ValueError("embedding must have 384 values")
    parts = []
    for value in embedding:
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            raise ValueError("embedding values must be finite")
        parts.append(f"{number:.6f}")
    return "VECTOR('[" + ",".join(parts) + "]', 384, FLOAT32)"


class KbStore(Protocol):
    """Store interface for known differences."""

    def add(self, entry: KnownDifference) -> None:
        """Add one entry. Embeds it if needed."""
        ...

    def approve(self, title: str) -> None:
        """Mark one entry verified."""
        ...

    def reject(self, title: str) -> None:
        """Remove one unverified entry."""
        ...

    def search(
        self, query: str, limit: int = 5, category: str = ""
    ) -> tuple[ScoredDifference, ...]:
        """Search verified entries. Return closest first."""
        ...

    def list_candidates(self) -> tuple[KnownDifference, ...]:
        """List unverified entries for human review."""
        ...


class InMemoryKb:
    """Dict backed store. For tests and local runs."""

    def __init__(self, embedder: HashingEmbedder | None = None) -> None:
        self._embedder = embedder or HashingEmbedder()
        self._entries: dict[str, KnownDifference] = {}
        self._searches = 0
        self._hits = 0

    def stats(self) -> SearchStats:
        """Search and hit counters. Reuse is hits over searches."""
        return SearchStats(
            searches=self._searches,
            hits=self._hits,
            misses=self._searches - self._hits,
        )

    def add(self, entry: KnownDifference) -> None:
        """Add one entry. Embeds it if needed."""
        if not entry.embedding:
            entry.embedding = self._embedder.embed(entry.search_text())
        self._entries[entry.title] = entry

    def approve(self, title: str) -> None:
        """Mark one entry verified."""
        if title not in self._entries:
            raise KeyError(f"unknown entry: {title}")
        if self._entries[title].verified:
            raise ValueError("entry is already verified")
        self._entries[title].verified = True
    def reject(self, title: str) -> None:
        """Remove one unverified entry."""
        entry = self._entries.get(title)
        if entry is None:
            raise KeyError(f"unknown entry: {title}")
        if entry.verified:
            raise ValueError("verified entries cannot be rejected")
        del self._entries[title]

    def search(
        self, query: str, limit: int = 5, category: str = ""
    ) -> tuple[ScoredDifference, ...]:
        """Search verified entries. Return closest first."""
        query_vector = self._embedder.embed(query)
        scored = [
            ScoredDifference(entry, cosine_distance(query_vector, entry.embedding))
            for entry in self._entries.values()
            if entry.verified and entry.matches_category(category)
        ]
        scored.sort(key=lambda item: item.distance)
        results = tuple(scored[:limit])
        self._searches += 1
        if results:
            self._hits += 1
        return results

    def list_candidates(self) -> tuple[KnownDifference, ...]:
        """List unverified entries for human review."""
        return tuple(
            entry for entry in self._entries.values() if not entry.verified
        )


class Db2Kb:
    """Db2 backed store using VECTOR_DISTANCE."""

    def __init__(self, admin, embedder: HashingEmbedder | None = None) -> None:
        self._admin = admin
        self._embedder = embedder or HashingEmbedder()
        self._searches = 0
        self._hits = 0

    def stats(self) -> SearchStats:
        """Search and hit counters for this process."""
        return SearchStats(
            searches=self._searches,
            hits=self._hits,
            misses=self._searches - self._hits,
        )

    def create_table(self) -> None:
        """Create the known_difference table."""
        self._admin.execute_ddl(KNOWN_DIFFERENCE_DDL)

    def add(self, entry: KnownDifference) -> None:
        """Add one entry with its embedding."""
        if not entry.embedding:
            entry.embedding = self._embedder.embed(entry.search_text())
        literal = _vector_literal(entry.embedding)
        sql = (
            "INSERT INTO known_difference "
            "(title, source_pattern, db2_pattern, cause, fix_template, verified, "
            f"evidence_run_id, embedding) VALUES (?, ?, ?, ?, ?, ?, ?, {literal})"
        )
        values = [
            entry.title,
            entry.source_pattern,
            entry.db2_pattern,
            entry.cause,
            entry.fix_template,
            1 if entry.verified else 0,
            entry.evidence_run_id,
        ]
        self._admin.execute(sql, values)

    def approve(self, title: str) -> None:
        """Mark one entry verified."""
        _, rows = self._admin.execute(
            "SELECT verified FROM known_difference WHERE title = ?", [title]
        )
        if not rows:
            raise KeyError(f"unknown entry: {title}")
        if int(rows[0][0]) == 1:
            raise ValueError("entry is already verified")
        self._admin.execute(
            "UPDATE known_difference SET verified = 1 WHERE title = ?", [title]
        )

    def reject(self, title: str) -> None:
        """Remove one unverified entry."""
        _, rows = self._admin.execute(
            "SELECT verified FROM known_difference WHERE title = ?", [title]
        )
        if not rows:
            raise KeyError(f"unknown entry: {title}")
        if int(rows[0][0]) == 1:
            raise ValueError("verified entries cannot be rejected")
        self._admin.execute(
            "DELETE FROM known_difference WHERE title = ? AND verified = 0", [title]
        )

    def list_candidates(self) -> tuple[KnownDifference, ...]:
        """List unverified entries for human review."""
        _, rows = self._admin.execute(
            "SELECT title, source_pattern, db2_pattern, cause, fix_template, "
            "evidence_run_id FROM known_difference WHERE verified = 0 ORDER BY title"
        )
        return tuple(
            KnownDifference(
                title=row[0],
                source_pattern=row[1],
                db2_pattern=row[2],
                cause=row[3] or "",
                fix_template=row[4] or "",
                verified=False,
                evidence_run_id=int(row[5]) if row[5] is not None else None,
            )
            for row in rows
        )

    def search(
        self, query: str, limit: int = 5, category: str = ""
    ) -> tuple[ScoredDifference, ...]:
        """Search verified entries with VECTOR_DISTANCE."""
        query_vector = self._embedder.embed(query)
        literal = _vector_literal(query_vector)
        fetch_limit = limit * 3 if category else limit
        _, rows = self._admin.execute(
            "SELECT title, source_pattern, db2_pattern, cause, fix_template, "
            "evidence_run_id, "
            f"VECTOR_DISTANCE(embedding, {literal}, COSINE) AS dist "
            "FROM known_difference WHERE verified = 1 "
            "ORDER BY dist FETCH FIRST ? ROWS ONLY",
            [fetch_limit],
        )
        results: list[ScoredDifference] = []
        for row in rows:
            entry = KnownDifference(
                title=row[0],
                source_pattern=row[1],
                db2_pattern=row[2],
                cause=row[3] or "",
                fix_template=row[4] or "",
                verified=True,
                evidence_run_id=int(row[5]) if row[5] is not None else None,
            )
            if entry.matches_category(category):
                results.append(ScoredDifference(entry, float(row[6])))
        self._searches += 1
        if results:
            self._hits += 1
        return tuple(results[:limit])
