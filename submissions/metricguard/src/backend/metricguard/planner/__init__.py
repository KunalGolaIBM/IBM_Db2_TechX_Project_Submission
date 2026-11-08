"""Question -> typed plan. See base.py for the contract shared by all planners."""

from __future__ import annotations

from metricguard.config import Settings

from .base import (
    DEMO_DISCLOSURE,
    Planner,
    PlannerError,
    PlannerOutput,
    PlannerOutputError,
    PlannerResult,
    PlannerUnavailableError,
)
from .rules import RuleBasedPlanner


def build_planner(settings: Settings) -> Planner | None:
    """Select the planner (AI_PROVIDER, see Settings.selected_provider).

    Returns None when the chosen provider has no credentials. It never substitutes the demo planner for a
    missing or failing real provider: only AI_PROVIDER=demo (or `auto` without any key) selects it.
    """
    provider = settings.selected_provider
    if provider == "demo":
        return RuleBasedPlanner()
    if provider in ("meta", "anthropic"):
        from .llm import LangChainPlanner

        return LangChainPlanner(settings, provider=provider)
    return None


__all__ = [
    "DEMO_DISCLOSURE", "Planner", "PlannerError", "PlannerOutput", "PlannerOutputError", "PlannerResult",
    "PlannerUnavailableError", "RuleBasedPlanner", "build_planner",
]
