from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path

import pytest

from security.run_audit import POLICY_FILE, build_command, load_exception_ids

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_IDS = {
    "PYSEC-2026-311",
    "PYSEC-2026-3813",
    "PYSEC-2026-3814",
    "PYSEC-2026-3815",
}
EXPECTED_TRIVY_IDS = {
    "CVE-2026-45829",
    "CVE-2026-45830",
    "CVE-2026-45833",
    "CVE-2026-45831",
}


def test_exception_policy_is_exact_and_expires() -> None:
    policy = tomllib.loads(POLICY_FILE.read_text(encoding="utf-8"))
    exceptions = policy["exceptions"]

    assert len(exceptions) == 1
    exception = exceptions[0]
    assert exception["package"] == "chromadb"
    assert set(exception["ids"]) == EXPECTED_IDS
    assert len(exception["ids"]) == len(EXPECTED_IDS)
    assert set(exception["trivy_ids"]) == EXPECTED_TRIVY_IDS
    assert exception["owner"] == "aryan"
    assert exception["added"] == "2026-11-10"
    assert exception["expires"] == "2026-12-10"
    assert exception["reason"]
    assert date.today() <= date.fromisoformat(exception["expires"])
    assert set(load_exception_ids()) == EXPECTED_IDS


def test_expired_exceptions_stop_the_audit() -> None:
    with pytest.raises(ValueError, match="expired"):
        load_exception_ids(today=date(2026, 12, 11))


def test_audit_uses_strict_collection_and_only_approved_exceptions() -> None:
    command = build_command(sorted(EXPECTED_IDS))

    assert "--strict" in command
    assert "--skip-editable" in command
    assert {
        command[index + 1]
        for index, value in enumerate(command[:-1])
        if value == "--ignore-vuln"
    } == EXPECTED_IDS


def test_trivy_ignores_only_documented_cve_aliases() -> None:
    ignore_lines = (ROOT / ".trivyignore").read_text(encoding="utf-8").splitlines()
    ignored_ids = {
        line.strip()
        for line in ignore_lines
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert ignored_ids == EXPECTED_TRIVY_IDS
    assert any("expires 2026-12-10" in line for line in ignore_lines)


def test_application_and_compose_do_not_use_or_expose_chromadb() -> None:
    app_sources = (ROOT / "app").rglob("*.py")
    compose_files = [ROOT / "docker-compose.yml", ROOT / "deploy" / "docker-compose.prod.yml"]

    for source in app_sources:
        assert "chromadb" not in source.read_text(encoding="utf-8").lower(), source

    for compose_file in compose_files:
        assert compose_file.is_file()
        assert "chromadb" not in compose_file.read_text(encoding="utf-8").lower(), compose_file
