"""Fix loop controller.

Plain Python state machine. It owns all limits:
max attempts, stop rules, and human escalation.
Agents propose SQL. The injected re-run function
decides if a fix works. The controller never
trusts an agent verdict.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from parity.agents.prompts import system_prompt
from parity.agents.types import AgentOutput, AgentRole, FixAttempt, LoopResult
from parity.engine.result import ComparisonResult, ComparisonStatus

_MAX_ATTEMPTS = 3


class AgentRunner(Protocol):
    """Run one agent task and return its output."""

    def run(self, role: AgentRole, user: str) -> AgentOutput:
        """Run the agent. Return its output."""
        ...


class GatewayRunner:
    """Agent runner backed by the model gateway."""

    def __init__(self, gateway) -> None:
        self._gateway = gateway

    def run(self, role: AgentRole, user: str) -> AgentOutput:
        """Call the gateway with the role prompt."""
        response = self._gateway.complete(role.value, system_prompt(role), user)
        return AgentOutput(
            role=role,
            text=response.text.strip(),
            provider=response.provider,
            from_cache=response.from_cache,
        )


class FixLoopController:
    """Run diagnose, fix, and re-prove for one query."""

    def __init__(
        self,
        runner: AgentRunner,
        rerun: Callable[[str], ComparisonResult],
        max_attempts: int = _MAX_ATTEMPTS,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self._runner = runner
        self._rerun = rerun
        self._max_attempts = max_attempts

    def _diagnose(self, source_sql: str, diff_text: str) -> str:
        output = self._runner.run(
            AgentRole.DIAGNOSTICIAN,
            f"source SQL:\n{source_sql}\nfirst diff:\n{diff_text}",
        )
        return output.text

    def _propose_fix(self, hypothesis: str, current_sql: str) -> str:
        output = self._runner.run(
            AgentRole.FIXER,
            f"hypothesis: {hypothesis}\ncurrent Db2 SQL:\n{current_sql}",
        )
        return output.text.strip()

    def run(self, source_sql: str, initial_db2_sql: str, diff_text: str) -> LoopResult:
        """Run the loop. Return the outcome."""
        hypothesis = self._diagnose(source_sql, diff_text)
        attempts: list[FixAttempt] = []
        current = initial_db2_sql
        for attempt in range(1, self._max_attempts + 1):
            candidate = self._propose_fix(hypothesis, current)
            result = self._rerun(candidate)
            if result.status is ComparisonStatus.MATCH:
                attempts.append(FixAttempt(attempt, candidate, "MATCH"))
                return LoopResult(
                    status="FIXED",
                    final_sql=candidate,
                    attempts=tuple(attempts),
                    hypothesis=hypothesis,
                )
            attempts.append(
                FixAttempt(attempt, candidate, result.status.value, result.note)
            )
            current = candidate
        return LoopResult(
            status="NEEDS_HUMAN",
            final_sql=current,
            attempts=tuple(attempts),
            hypothesis=hypothesis,
            needs_human=True,
        )
