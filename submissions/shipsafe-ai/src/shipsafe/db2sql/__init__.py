"""Db2 SQL assistant: live validation and catalog inspection."""

from .checker import Db2SqlChecker, SqlCheckResult, static_rules

__all__ = ["Db2SqlChecker", "SqlCheckResult", "static_rules"]
