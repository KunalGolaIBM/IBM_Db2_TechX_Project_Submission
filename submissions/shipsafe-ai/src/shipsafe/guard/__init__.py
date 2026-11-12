"""IDE guard: check code before the AI assistant writes it."""

from .checker import GuardIssue, GuardResult, check_code, language_for

__all__ = ["GuardIssue", "GuardResult", "check_code", "language_for"]
