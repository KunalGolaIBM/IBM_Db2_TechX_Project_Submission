"""CrewAI adapter.

Maps our four agent roles to CrewAI Agent objects.
CrewAI is imported lazily, so the core controller
and all tests work without it installed.
"""

from __future__ import annotations

from parity.agents.prompts import system_prompt
from parity.agents.types import AgentRole

_ROLE_META: dict[AgentRole, tuple[str, str]] = {
    AgentRole.TRANSLATOR: (
        "SQL Translator",
        "Translate PostgreSQL SQL into IBM Db2 SQL.",
    ),
    AgentRole.FUZZER: (
        "Fuzz Designer",
        "Design edge case test values for database columns.",
    ),
    AgentRole.DIAGNOSTICIAN: (
        "Mismatch Diagnostician",
        "Explain why a query returned different results.",
    ),
    AgentRole.FIXER: (
        "SQL Fixer",
        "Rewrite a Db2 query to remove the difference.",
    ),
}


def build_crewai_agent(role: AgentRole, model: str = "gpt-4o-mini"):
    """Build one CrewAI agent. Raise ImportError if missing."""
    try:
        from crewai import Agent
    except ImportError as exc:
        raise ImportError(
            "crewai is not installed. Run: pip install -e .[agents]"
        ) from exc
    title, goal = _ROLE_META[role]
    return Agent(
        role=title,
        goal=goal,
        backstory=system_prompt(role),
        model=model,
        verbose=False,
        allow_delegation=False,
    )


def build_all_agents(model: str = "gpt-4o-mini") -> dict[AgentRole, object]:
    """Build all four CrewAI agents."""
    return {role: build_crewai_agent(role, model=model) for role in AgentRole}
