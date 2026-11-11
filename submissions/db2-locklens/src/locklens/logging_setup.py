"""Logging configuration with secret redaction."""

from __future__ import annotations

import logging
import re

_SECRET_PATTERN = re.compile(r"(?i)\b(PWD|PASSWORD|PASSWD)\s*=\s*(\{[^}]*\}|[^;\s]+)")


class RedactingFilter(logging.Filter):
    """Masks ``PWD=...`` style fragments and any explicitly registered secret values."""

    def __init__(self, secrets: list[str] | None = None):
        super().__init__()
        self._secrets = [s for s in (secrets or []) if s]

    def add_secret(self, value: str | None) -> None:
        if value and value not in self._secrets:
            self._secrets.append(value)

    def redact(self, text: str) -> str:
        text = _SECRET_PATTERN.sub(lambda m: f"{m.group(1)}=***", text)
        for secret in self._secrets:
            text = text.replace(secret, "***")
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - defensive, malformed log call
            return True
        record.msg = self.redact(message)
        record.args = ()
        return True


_FILTER = RedactingFilter()
_CONFIGURED = False


def configure_logging(level: str = "INFO", secrets: list[str] | None = None) -> None:
    """Idempotently configure root logging with the redaction filter attached."""
    global _CONFIGURED
    for s in secrets or []:
        _FILTER.add_secret(s)
    if _CONFIGURED:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(_FILTER)
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    _CONFIGURED = True
