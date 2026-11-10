"""Scan git-tracked files of this submission for committed secrets.

Checks: tracked .env / key files, high-entropy-looking assignments to secret-named variables,
well-known API-key shapes, and (optionally) the literal values of the current environment's
secrets. Exit code 1 on any finding.

Usage:  python scripts/check_secrets.py [--literal-from-env]
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import _bootstrap

ROOT = _bootstrap.SUBMISSION_DIR
FORBIDDEN_NAMES = {".env", ".env.local", "id_rsa", "id_ed25519"}
FORBIDDEN_SUFFIXES = (".pem", ".pfx", ".p12", ".key")
KEY_SHAPES = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
_NAME = r"[A-Za-z0-9_]*(?:PASSWORD|SECRET|TOKEN|API_?KEY|APIKEY)[A-Za-z0-9_]*"
# dotenv / yaml / markdown style (NAME=value at line start) for non-code files ...
CONFIG_ASSIGN = re.compile(rf"(?im)^\s*{_NAME}\s*[=:]\s*['\"]?([^\s'\"#,$<]{{12,}})")
# ... and quoted string literals assigned to secret-named variables in code.
CODE_ASSIGN = re.compile(rf"\b{_NAME}\s*[=:]\s*['\"]([^'\"\s]{{12,}})['\"]")
PLACEHOLDER = re.compile(
    r"(?i)(id:role:token|change_me|your_|_here|example|placeholder|<|\$\{|xxxx|\*\*\*|get_secret|environ)"
)
ENV_NAMES = ("DB2_PASSWORD", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "WATSONX_APIKEY", "CIVICLENS_AUTH_TOKENS")


def tracked_files() -> list[Path]:
    out = subprocess.run(  # noqa: S603
        ["git", "ls-files", "-z", "--", "."],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    return [ROOT / p for p in out.split("\0") if p]


def scan(files: list[Path], literals: list[str]) -> list[str]:
    findings: list[str] = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if path.name.lower() in FORBIDDEN_NAMES or path.name.lower().endswith(FORBIDDEN_SUFFIXES):
            findings.append(f"{rel}: forbidden file type is tracked")
            continue
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for shape in KEY_SHAPES:
            if shape.search(text):
                findings.append(f"{rel}: matches credential shape {shape.pattern[:20]}...")
        is_test = rel.startswith("tests/")  # fixtures hold fake values; shapes/literals still apply
        pattern = CODE_ASSIGN if path.suffix == ".py" else CONFIG_ASSIGN
        for m in pattern.finditer(text):
            if not is_test and not PLACEHOLDER.search(m.group(1)):
                findings.append(f"{rel}: suspicious secret assignment near {m.group(0)[:25]!r}")
        for lit in literals:
            if lit in text:
                findings.append(f"{rel}: contains a literal secret value from the environment")
    return findings


def env_literals() -> list[str]:
    values: list[str] = []
    for name in ENV_NAMES:
        for part in os.environ.get(name, "").split(","):
            token = part.split(":")[-1].strip()
            if len(token) >= 12:
                values.append(token)
    return values


def main() -> int:
    literals = env_literals() if "--literal-from-env" in sys.argv else []
    files = tracked_files() + [p for p in _untracked()]
    findings = scan(files, literals)
    for f in findings:
        print(f"FINDING {f}")
    print(f"Scanned {len(files)} files, {len(literals)} literal secret values: {len(findings)} finding(s)")
    return 1 if findings else 0


def _untracked() -> list[Path]:
    out = subprocess.run(  # noqa: S603
        ["git", "ls-files", "-z", "--others", "--exclude-standard", "--", "."],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    return [ROOT / p for p in out.split("\0") if p]


if __name__ == "__main__":
    sys.exit(main())
