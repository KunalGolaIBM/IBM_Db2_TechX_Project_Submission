"""Lazy package init.

Importing ``src.agent`` must not require a live Db2 driver, otherwise unit
tests for the pure policy/extraction modules would need a database.
"""

from typing import Any, Dict, Optional

__all__ = ["run", "build_graph", "has_langgraph"]


def run(raw_text: str, category: Optional[str] = None) -> Dict[str, Any]:
    from .graph import run as _run

    return _run(raw_text, category=category)


def build_graph():
    from .graph import build_graph as _build

    return _build()


def has_langgraph() -> bool:
    from .graph import HAS_LANGGRAPH

    return HAS_LANGGRAPH
