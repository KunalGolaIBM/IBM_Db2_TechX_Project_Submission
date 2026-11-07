"""Evidence extraction, environment detection and failure classification.

Deterministic on purpose: the evidence that ends up in an issue must be lines
that really exist in the log. The LLM may describe evidence; it never invents it.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass

CATEGORIES = {
    "RUNTIME_INSTALL": "Container runtime detection / installation",
    "RESTART": "Container restart / startup",
    "CONNECTION": "Database connection",
    "AUTHENTICATION": "Authentication",
    "NETWORK": "Network / proxy / DNS",
    "EXTENSION": "VS Code extension behaviour",
    "UNCLASSIFIED": "Unclassified",
}


@dataclass(frozen=True)
class Signal:
    label: str
    pattern: re.Pattern[str]
    category: str
    weight: float
    kind: str = "ERROR"  # ERROR | WARNING | OBSERVATION


def _s(label: str, pattern: str, category: str, weight: float, kind: str = "ERROR") -> Signal:
    return Signal(label, re.compile(pattern, re.IGNORECASE), category, weight, kind)


SIGNALS: list[Signal] = [
    # Runtime detection / installation
    _s("No container runtime", r"no container runtimes? (?:found|detected|available)", "RUNTIME_INSTALL", 3.0),
    _s("All runtime installs failed", r"all runtime installations failed", "RUNTIME_INSTALL", 3.0),
    _s("Runtime install failed", r"(?:podman|docker)\b.*install(?:ation)? failed|failed to install (?:podman|docker)", "RUNTIME_INSTALL", 2.0),
    _s("Package fetch failed", r"failed to fetch|unable to fetch some archives|could not connect to .*archive|E: Unable to locate package", "RUNTIME_INSTALL", 1.5),
    # Network
    _s("Connection timed out", r"connection timed out|operation timed out|curl: \(28\)", "NETWORK", 2.0),
    _s("DNS resolution failed", r"temporary failure resolving|could not resolve host|getaddrinfo ENOTFOUND|name or service not known", "NETWORK", 2.0),
    _s("Network unreachable", r"network is unreachable|curl: \(7\)|no route to host", "NETWORK", 2.0),
    _s("Proxy / TLS problem", r"proxy|certificate verify failed|self[- ]signed certificate|SSL_ERROR", "NETWORK", 1.0, "WARNING"),
    # Restart / startup
    _s("Exec on stopped container", r"can only create exec sessions on running containers|container state improper", "RESTART", 3.0),
    _s("Quick restart failed", r"quick restart failed", "RESTART", 3.0),
    _s("Full restart required", r"full restart required", "RESTART", 1.0, "WARNING"),
    _s("Readiness timeout", r"readiness[- ]message timeout|timed out waiting for (?:db2|readiness|setup)|readiness .*time(?:d)? ?out", "RESTART", 2.0, "WARNING"),
    _s("Container exited with error", r"exited with code [1-9]|container .*exited unexpectedly", "RESTART", 1.5),
    _s("Container is stopped", r"state:? (?:exited|stopped)|container is (?:stopped|not running)", "RESTART", 0.0, "OBSERVATION"),
    _s("Port already in use", r"address already in use|port is already allocated|bind: .*in use", "RESTART", 2.0),
    # Connection / auth
    _s("SQL30081N communication error", r"SQL30081N", "CONNECTION", 3.0),
    _s("Connection refused", r"ECONNREFUSED|connection refused", "CONNECTION", 2.0),
    _s("Database not found", r"SQL1013N|SQL1031N", "CONNECTION", 2.5),
    _s("Authentication failed", r"SQL30082N|SQL1639N|authentication failed|invalid (?:user ?id|password)", "AUTHENTICATION", 3.0),
    _s("Db2 SQL error", r"\bSQL\d{4,5}N\b", "CONNECTION", 0.8),
    # Extension
    _s("Extension host error", r"extension host terminated|activating extension .* failed|cannot find module", "EXTENSION", 2.5),
    # Positive observations: needed so issues report the *final* state honestly
    _s("Waiting for readiness", r"waiting for .*readiness", "RESTART", 0.0, "OBSERVATION"),
    _s("Db2 accessible", r"db2 instance (?:is )?accessible|instance accessible|connection (?:test )?succeeded", "RESTART", 0.0, "OBSERVATION"),
    _s("Startup success", r"startup success|started successfully|setup has completed|restart (?:completed|succeeded)", "RESTART", 0.0, "OBSERVATION"),
    _s("Runtime detected", r"(?:podman|docker) (?:version )?\d+\.\d+(?:\.\d+)? detected|detected (?:podman|docker)", "RESTART", 0.0, "OBSERVATION"),
]

_GENERIC_ERROR = re.compile(r"\b(?:error|fatal|exception|failed)\b", re.IGNORECASE)

_ENV_PATTERNS: dict[str, re.Pattern[str]] = {
    "extension_version": re.compile(r"(?:IBM )?Db2 (?:Developer )?Extension(?: version)?[ :v]+(\d+\.\d+\.\d+)", re.I),
    "vscode_version": re.compile(r"(?:VS ?Code|Visual Studio Code)(?: version)?[ :v]+(\d+\.\d+\.\d+)", re.I),
    "linux_distribution": re.compile(r"(Ubuntu \d{2}\.\d{2}(?:\.\d+)?(?: LTS)?|Debian GNU/Linux \d+|Fedora(?: Linux)? \d+|Red Hat Enterprise Linux[^\n,]*?\d+(?:\.\d+)?|openSUSE[^\n,]*?\d+(?:\.\d+)?)", re.I),
    "architecture": re.compile(r"\b(x86_64|amd64|aarch64|arm64|x64)\b", re.I),
    "podman_version": re.compile(r"podman(?: version)?[ :v]+(\d+\.\d+\.\d+)", re.I),
    "docker_version": re.compile(r"docker(?: version)?[ :v]+(\d+\.\d+\.\d+)", re.I),
    "db2_version": re.compile(r"Db2(?: version| v| LUW)?[ :v]+(1[0-2]\.\d+\.\d+\.\d+)", re.I),
    "container_image": re.compile(r"\b((?:icr\.io|docker\.io|quay\.io)/[\w./-]+(?::[\w.-]+)?)"),
    "container_name": re.compile(r"container(?: named)? ['\"]?(db2[\w-]*)['\"]?", re.I),
}
_TIMESTAMP = re.compile(r"^\s*\[?\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?Z?\]?\s*(?:\[[A-Za-z]+\]\s*)?")


@dataclass
class Evidence:
    line_no: int
    kind: str
    label: str
    category: str
    log_line: str
    signature: str

    def as_dict(self) -> dict:
        return asdict(self)


def normalize_signature(line: str) -> str:
    """Turn a concrete log line into a reusable error fingerprint."""
    s = _TIMESTAMP.sub("", line).strip().lower()
    s = re.sub(r"<redacted:[a-z_]+>", "<x>", s)
    s = re.sub(r"0x[0-9a-f]+|\b[0-9a-f]{12,}\b", "<hex>", s)
    s = re.sub(r"(?:/[\w.<>-]+)+|[a-z]:\\[\w\\.<> -]+", "<path>", s)
    s = re.sub(r"\b\d+(?:\.\d+)*\b", "<n>", s)
    s = re.sub(r"\s+", " ", s)
    return s[:300]


def extract_environment(text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for key, pattern in _ENV_PATTERNS.items():
        m = pattern.search(text)
        if m:
            env[key] = m.group(1).strip()
    lowered = text.lower()
    if "wsl" in lowered or "microsoft-standard" in lowered:
        env["operating_system"] = "Windows with WSL"
    elif "darwin" in lowered or "macos" in lowered:
        env["operating_system"] = "macOS"
    elif "windows" in lowered or re.search(r"[A-Z]:\\", text):
        env["operating_system"] = "Windows"
    elif "linux" in lowered or "linux_distribution" in env:
        env["operating_system"] = "Linux"
    if "podman_version" in env:
        env["container_runtime"] = f"Podman {env['podman_version']}"
    elif "docker_version" in env:
        env["container_runtime"] = f"Docker {env['docker_version']}"
    elif re.search(r"no container runtimes? (?:found|detected|available)", text, re.I):
        env["container_runtime"] = "None detected at the time of the log"
    return env


def extract_evidence(text: str, limit: int = 20) -> list[Evidence]:
    """Return the most informative lines, in log order, without duplicates."""
    found: list[Evidence] = []
    seen: set[str] = set()
    for idx, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        match = next((s for s in SIGNALS if s.pattern.search(line)), None)
        if match is None:
            if not _GENERIC_ERROR.search(line):
                continue
            match = Signal("Generic error", _GENERIC_ERROR, "UNCLASSIFIED", 0.3)
        sig = normalize_signature(line)
        if sig in seen:
            continue
        seen.add(sig)
        found.append(Evidence(idx, match.kind, match.label, match.category, line[:1900], sig))

    if len(found) <= limit:
        return found
    # Keep strongest signals but preserve chronological order.
    weights = {s.label: s.weight for s in SIGNALS}
    ranked = sorted(found, key=lambda e: (e.kind == "OBSERVATION", weights.get(e.label, 0.3)), reverse=True)[:limit]
    return sorted(ranked, key=lambda e: e.line_no)


def classify(evidence: list[Evidence]) -> tuple[str, float]:
    """Weighted vote across evidence. Returns (category, confidence 0..1)."""
    weights = {s.label: s.weight for s in SIGNALS}
    scores: dict[str, float] = defaultdict(float)
    for ev in evidence:
        if ev.kind == "OBSERVATION":
            continue
        scores[ev.category] += weights.get(ev.label, 0.3)
    if not scores:
        return "UNCLASSIFIED", 0.0
    # Network errors during a runtime install are a symptom of the install flow.
    if scores.get("RUNTIME_INSTALL", 0) >= 3 and "NETWORK" in scores:
        scores["RUNTIME_INSTALL"] += scores["NETWORK"] * 0.5
    best = max(scores, key=scores.get)
    total = sum(scores.values())
    return best, round(scores[best] / total, 3) if total else 0.0


def build_signature(category: str, evidence: list[Evidence]) -> str:
    """Compact text used for embeddings and duplicate detection."""
    key_lines = [e.signature for e in evidence if e.kind != "OBSERVATION"][:8]
    return f"{category}: " + " | ".join(key_lines)
