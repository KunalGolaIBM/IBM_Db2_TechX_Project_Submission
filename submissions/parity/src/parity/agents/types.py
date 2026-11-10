"""Agent task and output types.

Agents propose. Only the Parity Engine decides.
These types carry proposals and hypotheses. They
never carry a verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AgentRole(str, Enum):
    """The four agent roles."""

    TRANSLATOR = "translator"
    FUZZER = "fuzzer"
    DIAGNOSTICIAN = "diagnostician"
    FIXER = "fixer"


@dataclass(frozen=True)
class AgentTask:
    """One task for one agent."""

    role: AgentRole
    system: str
    user: str


@dataclass(frozen=True)
class AgentOutput:
    """One agent response."""

    role: AgentRole
    text: str
    provider: str = ""
    from_cache: bool = False


@dataclass(frozen=True)
class FixAttempt:
    """One fix try with its outcome."""

    attempt: int
    candidate_sql: str
    outcome: str
    note: str = ""


@dataclass(frozen=True)
class LoopResult:
    """Outcome of the fix loop for one query."""

    status: str
    final_sql: str = ""
    attempts: tuple[FixAttempt, ...] = ()
    hypothesis: str = ""
    needs_human: bool = False
