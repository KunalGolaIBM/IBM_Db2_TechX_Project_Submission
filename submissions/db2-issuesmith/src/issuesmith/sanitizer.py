"""Deterministic log sanitiser.

Runs BEFORE any LLM call or database write, so raw secrets never leave the
user's machine and never reach Db2 or a model. Pure regex: predictable,
testable and explainable to judges and maintainers.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

# Public endpoints are evidence (e.g. "download.docker.com timed out"), so keep them.
PUBLIC_DOMAINS = (
    "docker.com", "docker.io", "ubuntu.com", "canonical.com", "icr.io", "ibm.com",
    "github.com", "githubusercontent.com", "github.io", "podman.io", "quay.io",
    "microsoft.com", "visualstudio.com", "npmjs.org", "pypi.org", "python.org",
    "fedoraproject.org", "debian.org", "launchpad.net", "opensuse.org",
)
SAFE_IPS = {"127.0.0.1", "0.0.0.0", "255.255.255.255"}

_KEY_NAMES = r"(?:pwd|password|passwd|pass|secret|token|api[_-]?key|apikey|access[_-]?key|client[_-]?secret|db2inst1_password)"

# (label, pattern, replacement). Order matters: specific before generic.
_RULES: list[tuple[str, re.Pattern[str], str]] = [
    ("PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----"), "<REDACTED:PRIVATE_KEY>"),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"), "<REDACTED:TOKEN>"),
    ("GITHUB_TOKEN", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}\b"), "<REDACTED:TOKEN>"),
    ("BEARER", re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{12,}"), r"\1 <REDACTED:TOKEN>"),
    ("URL_CREDENTIALS", re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)(?!<REDACTED)[^\s/:@]+:[^\s/@]+@"), r"\1<REDACTED:USER>:<REDACTED:PASSWORD>@"),
    # key=value or key: value (connection strings, env dumps, JSON)
    ("SECRET_KV", re.compile(rf"(?i)(\"?\b{_KEY_NAMES}\"?\s*[=:]\s*\"?)(?!<REDACTED)([^\s;\"',}}]+)"), r"\1<REDACTED:SECRET>"),
    ("DB_USER", re.compile(r"(?i)(\b(?:uid|user(?:name)?)\s*=\s*)(?!<REDACTED)([^\s;\"']+)"), r"\1<REDACTED:USER>"),
    ("DB_HOST", re.compile(r"(?i)(\bhostname\s*=\s*)(?!<REDACTED|localhost\b|127\.0\.0\.1\b)([^\s;\"']+)"), r"\1<REDACTED:HOST>"),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "<REDACTED:EMAIL>"),
    ("WINDOWS_USER", re.compile(r"(?i)([A-Z]:\\Users\\)(?!<user>)([^\\\s]+)"), r"\1<user>"),
    ("UNIX_USER", re.compile(r"(/home/|/Users/)(?!<user>)([^/\s]+)"), r"\1<user>"),
]

_IPV4 = re.compile(r"\b(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b")
_FQDN = re.compile(r"\b(?:[a-zA-Z0-9-]{1,63}\.)+(?:com|net|org|io|local|corp|internal|lan|intra|cloud|dev|in|co|biz|xyz)\b")


@dataclass
class SanitizeResult:
    text: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def _is_public(host: str) -> bool:
    host = host.lower()
    return any(host == d or host.endswith("." + d) for d in PUBLIC_DOMAINS)


def sanitize(text: str) -> SanitizeResult:
    """Return the redacted text plus a count of what was removed, per type."""
    counts: Counter[str] = Counter()
    out = text
    for label, pattern, repl in _RULES:
        out, n = pattern.subn(repl, out)
        if n:
            counts[label] += n

    def _ip(m: re.Match[str]) -> str:
        before = out[max(0, m.start() - 32):m.start()].lower()
        after = out[m.end():m.end() + 2]
        # Version numbers look like IPs (Db2 12.1.5.0, kernel 5.15.167.4-microsoft).
        looks_like_version = (
            any(k in before for k in ("version", "db2", "linux", "kernel", "release"))
            or before.endswith("v")
            or (after[:1] == "-" and after[1:2].isalpha())
        )
        if m.group(0) in SAFE_IPS or looks_like_version:
            return m.group(0)
        counts["IP_ADDRESS"] += 1
        return "<REDACTED:IP>"

    out = _IPV4.sub(_ip, out)

    def _host(m: re.Match[str]) -> str:
        host = m.group(0)
        if _is_public(host) or host.lower() in {"localhost"}:
            return host
        counts["HOSTNAME"] += 1
        return "<REDACTED:HOST>"

    out = _FQDN.sub(_host, out)
    return SanitizeResult(text=out, counts=dict(counts))


def find_secrets(text: str) -> list[str]:
    """Labels of anything that still looks sensitive (used by the critic agent)."""
    probe = sanitize(text)
    return sorted(probe.counts)
