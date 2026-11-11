"""Plain data models shared by monitoring, analysis, diagnostics and persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class Severity(IntEnum):
    INFO = 1
    WARNING = 2
    CRITICAL = 3

    @classmethod
    def parse(cls, value: str | "Severity") -> "Severity":
        if isinstance(value, Severity):
            return value
        try:
            return cls[str(value).strip().upper()]
        except KeyError as exc:
            raise ValueError(f"Unknown severity: {value!r}") from exc


@dataclass(frozen=True)
class LockRecord:
    """One row from MON_GET_LOCKS. Fields Db2 did not return are None."""

    application_handle: int | None
    lock_name_hex: str | None
    lock_status: str | None          # G granted, W waiting, C converting
    lock_object_type: str | None = None
    lock_mode: str | None = None
    lock_current_mode: str | None = None
    lock_count: int | None = None
    member: int | None = None


@dataclass(frozen=True)
class LockWaitRecord:
    """One row from MON_GET_APPL_LOCKWAIT: ``req`` waits for a lock held by ``hld``."""

    req_application_handle: int | None
    hld_application_handle: int | None   # None = Db2 does not know, 0 = holder no longer exists
    lock_name_hex: str | None = None
    lock_object_type: str | None = None
    lock_mode: str | None = None             # mode currently held by the holder
    lock_mode_requested: str | None = None
    lock_current_mode: str | None = None
    lock_status: str | None = None
    lock_wait_start_time: str | None = None
    wait_seconds: int | None = None          # computed on the Db2 server
    req_member: int | None = None
    hld_member: int | None = None


@dataclass(frozen=True)
class SessionInfo:
    """Connection details from MON_GET_CONNECTION, when the user may read it."""

    application_handle: int
    application_name: str | None = None
    application_id: str | None = None
    system_auth_id: str | None = None
    client_hostname: str | None = None
    workload_state: str | None = None        # e.g. UOWWAIT (idle in UOW), UOWEXEC, LOCKWAIT


@dataclass(frozen=True)
class ResourceInfo:
    """Decoded lock name (MON_FORMAT_LOCK_NAME). Only keys Db2 returned are set."""

    lock_name_hex: str
    table_schema: str | None = None
    table_name: str | None = None
    object_type: str | None = None
    row_id: str | None = None
    tablespace: str | None = None

    @property
    def label(self) -> str:
        if self.table_name:
            base = f"{self.table_schema + '.' if self.table_schema else ''}{self.table_name}"
            return f"{self.object_type or 'Lock'} on {base}"
        if self.object_type:
            return f"{self.object_type} lock"
        return "Lock (object not resolved)"


@dataclass(frozen=True)
class Note:
    """A user-visible remark about data availability (never hides errors silently)."""

    level: str      # "info" | "warning" | "error"
    message: str


@dataclass
class Snapshot:
    """Point-in-time monitoring view. A snapshot is NOT history."""

    captured_at: str                                   # client UTC ISO timestamp
    locks: list[LockRecord] = field(default_factory=list)
    waits: list[LockWaitRecord] = field(default_factory=list)
    sessions: dict[int, SessionInfo] = field(default_factory=dict)
    resources: dict[str, ResourceInfo] = field(default_factory=dict)
    available_columns: dict[str, list[str]] = field(default_factory=dict)
    notes: list[Note] = field(default_factory=list)
    locks_available: bool = True
    waits_available: bool = True


@dataclass(frozen=True)
class WaitEdge:
    """A lock wait enriched with who (if anyone) blocks the waiter, and how we know."""

    waiter: int | None
    holder: int | None
    provenance: str            # db2_lockwait | lock_table_match | ambiguous | unknown | holder_gone
    holder_candidates: tuple[int, ...] = ()
    lock_name_hex: str | None = None
    lock_object_type: str | None = None
    lock_mode_held: str | None = None
    lock_mode_requested: str | None = None
    wait_seconds: int | None = None
    wait_start_time: str | None = None
    resource_label: str = "Lock (object not resolved)"
    on_cycle: bool = False


@dataclass
class LockAnalysis:
    edges: list[WaitEdge] = field(default_factory=list)
    waiters: set[int] = field(default_factory=set)
    blockers: set[int] = field(default_factory=set)
    root_blockers: set[int] = field(default_factory=set)
    cycles: list[tuple[int, ...]] = field(default_factory=list)
    depth: dict[int, int] = field(default_factory=dict)
    total_locks: int = 0
    granted_locks: int = 0
    max_wait_seconds: int | None = None


@dataclass
class Finding:
    finding_type: str
    severity: Severity
    title: str
    explanation: str
    evidence: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    affected_applications: list[int] = field(default_factory=list)
    subject_key: str = ""                 # stable identity used for incident de-duplication
    category: str = "lock_contention"
    blocker_handle: int | None = None
    waiter_handles: list[int] = field(default_factory=list)
    lock_details: str = ""
    max_wait_seconds: int | None = None
    persist: bool = True                  # False for purely informational findings

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_type": self.finding_type, "severity": self.severity.name,
            "title": self.title, "explanation": self.explanation,
            "evidence": list(self.evidence), "recommendations": list(self.recommendations),
            "affected_applications": list(self.affected_applications),
            "subject_key": self.subject_key, "category": self.category,
            "blocker_handle": self.blocker_handle, "waiter_handles": list(self.waiter_handles),
            "lock_details": self.lock_details, "max_wait_seconds": self.max_wait_seconds,
        }


@dataclass
class DiagnosisResult:
    findings: list[Finding]
    analysis: LockAnalysis
    narrative: str
    narrative_source: str      # deterministic-template | llm:<model> | deterministic-fallback: <why>
    pipeline: str              # "langchain" | "direct (langchain not installed)"
    stages: list[str] = field(default_factory=list)
