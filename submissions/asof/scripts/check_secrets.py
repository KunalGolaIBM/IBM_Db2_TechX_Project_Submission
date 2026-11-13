#!/usr/bin/env python3
"""Block a commit that would publish a secret.

    python scripts/check_secrets.py            # checks staged changes (git diff --cached)
    python scripts/check_secrets.py --all      # checks every tracked file in this folder

Two kinds of checks:
1. The real values in your local .env (passwords, tokens and keys) and the chain-head anchor key
   file (default ~/.config/asof/anchor.key). If any of them appears in what you are about to commit,
   that is a leak, whatever it looks like (values of 8+ characters anywhere; shorter ones, down to
   4 characters, when they stand as a word of their own).
2. Generic patterns: private keys, provider API keys, and forbidden files (.env, *.pem, *.key, GSKit
   key databases and stash files, anything under var/, where anchor logs and TLS files are kept).

It prints file and line for each finding, never the secret. Exit code 1 means do not commit.
Standard library only, so it runs before any dependency is installed.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT / ".env"

FORBIDDEN_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519"}
FORBIDDEN_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".kdb", ".sth", ".jks", ".crt", ".arm")
FORBIDDEN_DIRS = ("var/",)  # runtime state: anchor logs, the local TLS certificate
PATTERNS = {
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "OpenRouter key": re.compile(r"sk-or-v1-[0-9a-f]{32,}"),
    "OpenAI-style key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
}
SECRET_KEYS = re.compile(r"(PASSWORD|SECRET|TOKEN|KEY|APIKEY)$")


def _env() -> dict[str, str]:
    out: dict[str, str] = {}
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                out[key.strip().upper()] = value.strip().strip("'\"")
    return out


def anchor_key_file(env: dict[str, str]) -> Path:
    """Where asof/config.py looks for the anchor key (kept in step with Settings.anchor_key_path)."""
    configured = os.environ.get("ASOF_ANCHOR_KEY_FILE") or env.get("ASOF_ANCHOR_KEY_FILE")
    if configured:
        return Path(configured).expanduser()
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "asof" / "anchor.key"


def local_secret_values() -> list[str]:
    env = _env()
    values = [v for k, v in env.items() if SECRET_KEYS.search(k) and len(v) >= MIN_SECRET_CHARS]
    key_file = anchor_key_file(env)
    if key_file.is_file():
        key = key_file.read_text(encoding="utf-8").strip()
        if len(key) >= MIN_SECRET_CHARS:
            values.append(key)
    return values


MIN_SECRET_CHARS = 4  # shorter values are too common to search for
LONG_SECRET_CHARS = 8  # from here a plain substring match; below it, a whole-word match


def leaks(value: str, line: str) -> bool:
    """A long secret anywhere in the line, or a short one standing as a word of its own."""
    if len(value) >= LONG_SECRET_CHARS:
        return value in line
    return re.search(r"(?<![A-Za-z0-9_])" + re.escape(value) + r"(?![A-Za-z0-9_])", line) is not None


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=PROJECT, capture_output=True, text=True, check=True).stdout


def staged_files() -> list[str]:
    out = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "--relative", "--", ".")
    return [line for line in out.splitlines() if line]


def tracked_files() -> list[str]:
    return [line for line in git("ls-files", "--", ".").splitlines() if line]


def staged_text(path: str) -> str:
    try:
        return git("show", f":{path}")
    except subprocess.CalledProcessError:
        return ""


def main(argv: list[str]) -> int:
    scan_all = "--all" in argv
    files = tracked_files() if scan_all else staged_files()
    secrets = local_secret_values()
    findings: list[str] = []

    for path in files:
        name = Path(path).name.lower()
        if name in FORBIDDEN_NAMES or name.endswith(FORBIDDEN_SUFFIXES) or path.startswith(FORBIDDEN_DIRS):
            findings.append(f"{path}: forbidden file type")
            continue
        text = (PROJECT / path).read_text(encoding="utf-8", errors="ignore") if scan_all else staged_text(path)
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"{path}:{lineno}: looks like a {label}")
            for value in secrets:
                if leaks(value, line):
                    findings.append(f"{path}:{lineno}: contains a value from your local .env")

    scope = "tracked files" if scan_all else "staged files"
    if findings:
        print(f"Secret check FAILED on {len(files)} {scope}:")
        for f in findings:
            print(f"  - {f}")
        return 1
    print(f"Secret check passed: {len(files)} {scope}, {len(secrets)} local secret values compared.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
