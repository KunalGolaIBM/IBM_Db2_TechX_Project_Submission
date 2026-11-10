from __future__ import annotations

import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path

POLICY_FILE = Path(__file__).with_name("audit-exceptions.toml")
ALLOWED_IDS = frozenset(
    {
        "PYSEC-2026-311",
        "PYSEC-2026-3813",
        "PYSEC-2026-3814",
        "PYSEC-2026-3815",
    }
)


def load_exception_ids(today: date | None = None) -> list[str]:
    with POLICY_FILE.open("rb") as policy_file:
        policy = tomllib.load(policy_file)

    exceptions = policy.get("exceptions", [])
    ids = [vulnerability_id for exception in exceptions for vulnerability_id in exception["ids"]]
    if len(exceptions) != 1 or frozenset(ids) != ALLOWED_IDS or len(ids) != len(ALLOWED_IDS):
        raise ValueError("Audit exception IDs do not match the approved ChromaDB advisory set")

    exception = exceptions[0]
    if exception["package"] != "chromadb":
        raise ValueError("Audit exceptions are only approved for chromadb")

    expiry = date.fromisoformat(exception["expires"])
    if (today or date.today()) > expiry:
        raise ValueError(f"ChromaDB audit exception expired on {expiry.isoformat()}")

    return ids


def build_command(ids: list[str]) -> list[str]:
    command = [sys.executable, "-m", "pip_audit", "--skip-editable", "--strict"]
    for vulnerability_id in ids:
        command.extend(["--ignore-vuln", vulnerability_id])
    return command


def main() -> int:
    try:
        exception_ids = load_exception_ids()
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(f"Dependency audit policy error: {error}", file=sys.stderr)
        return 2

    return subprocess.run(build_command(exception_ids), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
