#!/usr/bin/env python3
"""Regenerate requirements.lock from requirements.txt.

    python scripts/lock_deps.py

Builds a throwaway virtualenv, installs requirements.txt into it, and writes every resolved
package with its exact version to requirements.lock. The lock is used as a constraints file
(pip install -r requirements.txt -c requirements.lock): it pins whatever pip installs, but
does not force platform-only packages (for example the CUDA wheels torch pulls on Linux) onto
platforms that do not need them.
"""

from __future__ import annotations

import datetime as dt
import platform
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
HEADER = """# Every package AsOf installs, pinned to the exact version tested (Python {py}, {plat};
# resolved from requirements.txt on {day}). Used as a pip constraints file:
#   pip install -r requirements.txt -c requirements.lock
# Constraints pin whatever gets installed without forcing platform-only packages onto other
# platforms. Regenerate with: python scripts/lock_deps.py

"""


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        venv.create(tmp, with_pip=True)
        py = Path(tmp) / ("Scripts" if sys.platform == "win32" else "bin") / "python"
        subprocess.run([str(py), "-m", "pip", "install", "-q", "-r", str(PROJECT / "requirements.txt")],
                       check=True, timeout=1800)
        frozen = subprocess.run([str(py), "-m", "pip", "freeze", "--exclude-editable"], check=True,
                                capture_output=True, text=True, timeout=120).stdout
    lines = sorted((ln for ln in frozen.splitlines() if ln.strip()), key=str.lower)
    header = HEADER.format(py=platform.python_version().rsplit(".", 1)[0],
                           plat=f"{platform.system()} {platform.machine()}", day=dt.date.today().isoformat())
    (PROJECT / "requirements.lock").write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote requirements.lock with {len(lines)} packages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
