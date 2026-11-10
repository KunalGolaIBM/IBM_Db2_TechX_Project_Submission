"""System prompts for each agent.

Prompts hold only SQL text, schema names, and synthetic
values. Production rows are never included. Temperature
is 0 at the gateway, so outputs stay stable.
"""

from __future__ import annotations

from parity.agents.types import AgentRole

PROMPTS: dict[AgentRole, str] = {
    AgentRole.TRANSLATOR: (
        "You translate PostgreSQL SQL into IBM Db2 SQL. "
        "Keep the meaning identical. Use CAST, FETCH FIRST, and Db2 "
        "functions where the dialects differ. Output only the Db2 SQL. "
        "No explanation. No markdown."
    ),
    AgentRole.FUZZER: (
        "You design edge case test values for database columns. "
        "Use NULL, empty strings, spaces, Unicode, extreme numbers, "
        "and timezone dates. Output a JSON list of values per column. "
        "Synthetic values only."
    ),
    AgentRole.DIAGNOSTICIAN: (
        "You explain why a query returned different results on two "
        "databases. Look at the first differing row. Name the likely "
        "cause in one sentence. Output only the hypothesis."
    ),
    AgentRole.FIXER: (
        "You rewrite a Db2 query so it returns the same result as the "
        "source query. Fix the specific difference you are shown. "
        "Output only the rewritten Db2 SQL. No explanation."
    ),
}


def system_prompt(role: AgentRole) -> str:
    """Return the system prompt for one role."""
    return PROMPTS[role]
