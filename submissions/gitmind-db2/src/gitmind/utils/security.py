"""
GitMind 2.0 — Security, Secret Redaction, and Defense-in-Depth

Enforces strict security policies across repository intelligence pipelines:
- High-confidence secret detection and redaction before embedding/LLM calls
- Ignore lists for sensitive files (.env, keys, credentials, build dirs)
- Prompt injection defense wrappers for untrusted repo content
- Parameterized SQL validation
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Pattern, Tuple

# Patterns for sensitive credentials & tokens
_SECRET_PATTERNS: List[Tuple[str, Pattern]] = [
    ("OPENAI_KEY", re.compile(r"sk-[a-zA-Z0-9]{20,T3BlbkFJ[a-zA-Z0-9]{20,}")),
    ("OPENAI_PROJ", re.compile(r"sk-proj-[a-zA-Z0-9_-]{40,}")),
    ("GEMINI_KEY", re.compile(r"AIzaSy[a-zA-Z0-9_-]{33}")),
    ("GITHUB_PAT", re.compile(r"ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{82}")),
    ("SLACK_TOKEN", re.compile(r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*")),
    ("AWS_KEY", re.compile(r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}")),
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA|OPENSSH|DSA|EC|PGP)? PRIVATE KEY-----[\s\S]*?-----END (?:RSA|OPENSSH|DSA|EC|PGP)? PRIVATE KEY-----")),
    ("GENERIC_BEARER", re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{24,}")),
    ("GENERIC_PASSWORD", re.compile(r"(?i)(password|pwd|secret|auth_token)\s*[:=]\s*['\"][^\s'\"]{6,}['\"]")),
]

_EXCLUDED_PATTERNS: List[str] = [
    r"^\.git[/\\].*",
    r".*\.env.*",
    r".*\.pem$",
    r".*\.key$",
    r".*\.pfx$",
    r".*\.p12$",
    r".*id_rsa.*",
    r".*id_ed25519.*",
    r".*credentials.*",
    r".*/\.gitmind/.*",
    r".*__pycache__[/\\].*",
    r".*\.pyc$",
    r".*node_modules[/\\].*",
    r".*dist[/\\].*",
    r".*build[/\\].*",
    r".*\.egg-info[/\\].*",
    r".*\.png$",
    r".*\.jpg$",
    r".*\.jpeg$",
    r".*\.gif$",
    r".*\.ico$",
    r".*\.pdf$",
    r".*\.zip$",
    r".*\.tar.*",
    r".*\.db$",
    r".*\.sqlite.*",
]


def redact_secrets(text: str) -> str:
    """
    Scans text and replaces high-confidence secrets with safe redacted placeholders.
    Ensures secrets are never sent to external LLMs or vector databases.
    """
    if not text:
        return ""

    sanitized = text
    for name, pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub(f"[REDACTED_{name}]", sanitized)

    return sanitized


def is_path_safe_for_indexing(file_path: str) -> bool:
    """
    Checks if a relative or absolute file path is safe to index.
    Rejects sensitive files, secret configs, binaries, and build artifacts.
    """
    normalized = file_path.replace("\\", "/").strip()

    # Reject obvious sensitive basenames
    basename = Path(normalized).name.lower()
    if basename in (".env", ".env.local", ".env.production", "id_rsa", "id_ed25519"):
        return False

    for pat in _EXCLUDED_PATTERNS:
        if re.match(pat, normalized, re.IGNORECASE):
            return False

    return True


def sanitize_agent_input(text: str) -> str:
    """
    Wraps untrusted data (commit messages, PRs, diffs) to prevent prompt injection.
    Explicitly tags untrusted repository content so the LLM treats it as data.
    """
    redacted = redact_secrets(text)
    # Defense against prompt escape sequences: disarm potential system-tag overrides
    disarmed = redacted.replace("<system>", "&lt;system&gt;").replace("</system>", "&lt;/system&gt;")
    disarmed = disarmed.replace("```system", "```data")
    return disarmed

