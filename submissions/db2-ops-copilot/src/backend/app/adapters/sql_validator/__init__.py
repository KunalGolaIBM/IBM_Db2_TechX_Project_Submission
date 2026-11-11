"""SQL validation adapters (AST-based; local compute — no external service)."""

from __future__ import annotations

from app.adapters.sql_validator.sqlglot_validator import SqlGlotValidator, resolve_dialect
from app.core.config import Settings
from app.security.sql_policy import SqlPolicy


def build_validator(settings: Settings) -> SqlGlotValidator:
    """Build the production validator bound to the configured policy."""
    return SqlGlotValidator(SqlPolicy.from_settings(settings))


__all__ = ["SqlGlotValidator", "build_validator", "resolve_dialect"]
