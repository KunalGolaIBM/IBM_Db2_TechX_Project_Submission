#!/usr/bin/env python3
"""Fail if any pinned dependency has a known vulnerability.

    pip install -r requirements-dev.txt
    python scripts/audit_deps.py

Runs pip-audit over requirements.lock, which pins every package AsOf installs, direct and
transitive. It checks the exact pinned versions against the PyPI advisory database (OSV),
without installing anything. Exit code 1 means a known vulnerability, or that the audit
itself could not run; both should stop a release.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
LOCK = PROJECT / "requirements.lock"


def main() -> int:
    exe = shutil.which("pip-audit")
    if exe is None:
        print("pip-audit is not installed: pip install -r requirements-dev.txt", file=sys.stderr)
        return 1
    cmd = [exe, "-r", str(LOCK), "--no-deps", "--disable-pip", "--progress-spinner", "off", "--strict"]
    try:
        result = subprocess.run(cmd, timeout=600, check=False)
    except subprocess.TimeoutExpired:
        print("pip-audit timed out after 600 s", file=sys.stderr)
        return 1
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
