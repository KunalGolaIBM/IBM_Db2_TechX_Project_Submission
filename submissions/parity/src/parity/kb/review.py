"""Human review for knowledge base candidates.

Agents add new knowledge as unverified candidates.
They are never served by search until a human
approves them. This module is the review surface.
"""

from __future__ import annotations

from collections.abc import Callable

ACTIONS = ("list", "approve", "reject")


def run_review(store, action: str, title: str = "") -> str:
    """Run one review action. Return text for the caller to show."""
    if action not in ACTIONS:
        raise ValueError(f"unknown action: {action}")
    if action == "list":
        return _list(store)
    if not title:
        raise ValueError("title is required for approve and reject")
    handlers: dict[str, Callable[[], str]] = {
        "approve": lambda: _approve(store, title),
        "reject": lambda: _reject(store, title),
    }
    return handlers[action]()


def _list(store) -> str:
    """List unverified candidates.

    The title sits on its own line so it can be copied
    straight into an approve or reject command.
    """
    candidates = store.list_candidates()
    if not candidates:
        return "no candidates waiting for review"
    lines = []
    for entry in candidates:
        lines.append(entry.title)
        if entry.source_pattern:
            lines.append(f"    source: {entry.source_pattern}")
    return "\n".join(lines)


def _approve(store, title: str) -> str:
    """Approve one candidate."""
    store.approve(title)
    return f"approved: {title}"


def _reject(store, title: str) -> str:
    """Reject one candidate."""
    store.reject(title)
    return f"rejected: {title}"
