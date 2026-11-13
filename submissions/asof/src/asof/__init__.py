"""AsOf: checks what an AI assistant says against the policy in force on that date, on IBM Db2."""

from __future__ import annotations

from typing import Any

__version__ = "0.1.0"


def as_runnable(**kwargs: Any) -> Any:
    """LangChain Runnable that checks a draft answer; see asof.integration.as_runnable."""
    from .integration import as_runnable as _as_runnable

    return _as_runnable(**kwargs)
