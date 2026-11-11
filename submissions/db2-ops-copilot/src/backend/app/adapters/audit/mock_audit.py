"""Mock audit adapter — in-memory, thread-safe, bounded audit trail."""

from __future__ import annotations

import threading
from collections import deque

from app.adapters.base import AuditRecord, ProbeResult
from app.core.clock import utc_now_iso
from app.core.config import Settings

_SEED_ENTRIES = [
    AuditRecord(
        id=1,
        timestamp="2026-10-30T10:00:00+00:00",
        intent="docs",
        question="What is DB2VS?",
        status="OK",
        latency_ms=42,
        detail="mock seed entry",
        request_id="seed-0001",
    ),
    AuditRecord(
        id=2,
        timestamp="2026-10-30T10:01:30+00:00",
        intent="data",
        question="List servers by uptime",
        status="OK",
        latency_ms=67,
        detail="mock seed entry",
        request_id="seed-0002",
    ),
    AuditRecord(
        id=3,
        timestamp="2026-10-30T10:02:15+00:00",
        intent="data",
        question="Drop all tables",
        status="REJECTED_BY_GATE",
        latency_ms=9,
        detail="mock seed entry: blocked by SQL validation gate",
        request_id="seed-0003",
    ),
]


class MockAuditAdapter:
    """In-memory audit trail (real mode writes to the Db2 APP_AUDIT table)."""

    probe_name = "audit"
    provider_id = "mock"
    mode = "mock"

    def __init__(self, settings: Settings | None = None, capacity: int = 1000) -> None:
        self._settings = settings or Settings()
        self._lock = threading.Lock()
        self._entries: deque[AuditRecord] = deque(
            (_replace_copy(e) for e in _SEED_ENTRIES), maxlen=capacity
        )
        self._next_id = len(_SEED_ENTRIES) + 1
        self._closed = False

    def ping(self) -> ProbeResult:
        if self._closed:
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=0.0,
                detail="mock adapter closed",
            )
        return ProbeResult(
            name=self.probe_name,
            status="ok",
            mode=self.mode,
            latency_ms=0.0,
            detail=f"mock audit store ready ({len(self._entries)} entries)",
        )

    def record(self, entry: AuditRecord) -> int:
        with self._lock:
            entry.id = self._next_id
            self._next_id += 1
            if not entry.timestamp:  # Db2 assigns REQ_TS server-side; mirror that
                entry.timestamp = utc_now_iso()
            self._entries.append(entry)
            return entry.id

    def list_recent(self, limit: int = 50) -> list[AuditRecord]:
        with self._lock:
            snapshot = list(self._entries)
        snapshot.reverse()  # newest first
        return snapshot[: max(limit, 0)]

    def close(self) -> None:
        self._closed = True


def _replace_copy(record: AuditRecord) -> AuditRecord:
    return AuditRecord(
        id=record.id,
        timestamp=record.timestamp,
        operation=record.operation,
        session_id=record.session_id,
        intent=record.intent,
        question=record.question,
        sql_text=record.sql_text,
        status=record.status,
        latency_ms=record.latency_ms,
        detail=record.detail,
        request_id=record.request_id,
        metadata=record.metadata,
    )
