"""The fix loop for one query.

A mismatch goes to the Diagnostician, then to the Fixer.
Every proposed fix runs on both databases and only a
matching result is accepted. The agent never decides.

Without a gateway the loop does not run and the query
keeps its mismatch, because a wrong guess must never
replace a real difference.
"""

from __future__ import annotations

from dataclasses import dataclass

from parity.agents.controller import AgentRunner, FixLoopController, GatewayRunner
from parity.engine.executor import DatabaseExecutor
from parity.engine.result import ComparisonResult, ComparisonStatus
from parity.pipeline import quote_table
from parity.runner import run_comparison

SKIPPED = "SKIPPED"
FIXED = "FIXED"
NEEDS_HUMAN = "NEEDS_HUMAN"


@dataclass(frozen=True)
class FixLoopOutcome:
    """What the loop did with one query."""

    status: str
    final_sql: str = ""
    hypothesis: str = ""
    attempts: int = 0
    note: str = ""
    result: ComparisonResult | None = None

    @property
    def is_fixed(self) -> bool:
        """True when a fix was proved."""
        return self.status == FIXED

    @property
    def needs_human(self) -> bool:
        """True when the loop gave up."""
        return self.status == NEEDS_HUMAN


def build_diff_text(result: ComparisonResult) -> str:
    """Describe the first differences for the Diagnostician."""
    if not result.diffs:
        return result.note or "no difference detail"
    lines = []
    for diff in result.diffs[:3]:
        lines.append(
            f"{diff.kind.value}: {diff.detail} "
            f"(source={diff.source_value!r}, target={diff.target_value!r})"
        )
    return "\n".join(lines)


def run_fix_loop(
    source_sql: str,
    db2_sql: str,
    result: ComparisonResult,
    source: DatabaseExecutor,
    target: DatabaseExecutor,
    gateway,
    table: str | None = None,
    max_attempts: int = 3,
) -> FixLoopOutcome:
    """Try to fix one mismatch and prove the fix.

    The gateway is optional. Without it the loop is
    skipped and the mismatch stands.
    """
    if result.status is not ComparisonStatus.MISMATCH:
        return FixLoopOutcome(
            status=SKIPPED,
            note=f"nothing to fix, status is {result.status.value}",
            result=result,
        )
    if gateway is None:
        return FixLoopOutcome(
            status=SKIPPED,
            note="no agent gateway configured, the mismatch stands",
            result=result,
        )

    def rerun(candidate: str) -> ComparisonResult:
        return run_comparison(source, target, source_sql, quote_table(candidate, table))

    runner: AgentRunner = GatewayRunner(gateway)
    controller = FixLoopController(runner, rerun, max_attempts=max_attempts)
    try:
        loop = controller.run(source_sql, db2_sql, build_diff_text(result))
    except Exception as exc:  # noqa: BLE001 - an agent failure must not hide the mismatch
        return FixLoopOutcome(
            status=NEEDS_HUMAN,
            note=f"the agent loop failed: {exc}"[:200],
            result=result,
        )
    if loop.status == FIXED:
        return FixLoopOutcome(
            status=FIXED,
            final_sql=loop.final_sql,
            hypothesis=loop.hypothesis,
            attempts=len(loop.attempts),
            note=f"fixed by the agent: {loop.hypothesis}"[:200],
            result=result,
        )
    return FixLoopOutcome(
        status=NEEDS_HUMAN,
        final_sql=loop.final_sql,
        hypothesis=loop.hypothesis,
        attempts=len(loop.attempts),
        note=(
            f"needs a human after {len(loop.attempts)} tries: {loop.hypothesis}"
        )[:200],
        result=result,
    )
