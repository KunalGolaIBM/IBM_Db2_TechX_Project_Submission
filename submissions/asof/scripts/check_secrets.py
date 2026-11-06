#!/usr/bin/env python3
"""Block a commit that would publish a secret.

    python scripts/check_secrets.py            # checks staged changes (git diff --cached)
    python scripts/check_secrets.py --all      # checks every tracked file in this folder

Two kinds of checks:
1. The real values in your local .env. If any of them (8+ characters) appears in what you
   are about to commit, that is a leak, whatever it looks like.
2. Generic patterns: private keys, provider API keys, and forbidden files (.env, *.pem, ...).

It prints file and line for each finding, never the secret. Exit code 1 means do not commit.
Standard library only, so it runs before any dependency is installed.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT / ".env"

FORBIDDEN_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519"}
FORBIDDEN_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
PATTERNS = {
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "OpenRouter key": re.compile(r"sk-or-v1-[0-9a-f]{32,}"),
    "OpenAI-style key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
}
SECRET_KEYS = re.compile(r"(PASSWORD|SECRET|TOKEN|API_KEY|APIKEY)$")


def local_secret_values() -> list[str]:
    if not ENV_FILE.is_file():
        return []
    values = []
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("'\"")
        if SECRET_KEYS.search(key.strip().upper()) and len(value) >= 8:
            values.append(value)
    return values


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
        if name in FORBIDDEN_NAMES or name.endswith(FORBIDDEN_SUFFIXES):
            findings.append(f"{path}: forbidden file type")
            continue
        text = (PROJECT / path).read_text(encoding="utf-8", errors="ignore") if scan_all else staged_text(path)
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"{path}:{lineno}: looks like a {label}")
            for value in secrets:
                if value in line:
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
