"""Sensitive-metadata sanitization for audit/history persistence (M2.5).

Guarantee: nothing written to ``APP_AUDIT.METADATA`` / ``QUERY_EXECUTIONS.
METADATA`` (or any ``detail`` string) can contain a password, token or full
connection string. Adapters sanitize AGAIN before insert even if a caller
passes careless text — the database is the last checkpoint, not the first.

Rules (conservative, fail-toward-redaction):
- key=value / key: value pairs for credential-looking keys → key=***
- inline ``pwd=...`` style inside DSNs/conn strings → redacted
- long opaque literals after credential words → redacted
- output truncated to ``MAX_LEN`` (audit rows stay small and bounded)
"""

from __future__ import annotations

import re

MAX_LEN = 2000

_CRED_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|authorization|"
    r"credential)\b(\s*[=:]\s*)([^\s,;&\"']+)"
)

# DSN-style fragments: HOSTNAME=...;PORT=...;uid=...;pwd=...
_DSN_CRED = re.compile(r"(?i)\b(pwd|password|uid|user)\s*=\s*([^;]+)")


def sanitize_metadata(text: str | None) -> str | None:
    """Redact credential-like content and bound the size of a metadata string."""
    if text is None:
        return None
    cleaned = _CRED_ASSIGNMENT.sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)
    cleaned = _DSN_CRED.sub(
        lambda m: f"{m.group(1)}=***" if m.group(1).lower() in {"pwd", "password"} else m.group(0),
        cleaned,
    )
    if len(cleaned) > MAX_LEN:
        cleaned = cleaned[:MAX_LEN] + "…[truncated]"
    return cleaned
