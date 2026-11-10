"""Tests for the release documents."""

from pathlib import Path

ROOT = Path(__file__).parent.parent


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_version_is_released():
    assert 'version = "1.0.0"' in read("pyproject.toml")


def test_readme_has_the_real_numbers():
    text = read("README.md")
    assert "130" in text
    assert "divergence-catalog.md" in text
    assert "migration-guide.md" in text
    assert "supported-versions.md" in text


def test_readme_links_every_guide_it_names():
    text = read("README.md")
    for name in (
        "architecture.md",
        "migration-guide.md",
        "divergence-catalog.md",
        "engine.md",
        "sql-translate.md",
        "fuzz-run.md",
        "agent-fix-loop.md",
        "kb-capture.md",
        "regression.md",
        "ops-runbook.md",
        "supported-versions.md",
        "release-notes.md",
    ):
        assert f"docs/{name}" in text
        assert (ROOT / "docs" / name).is_file()


def test_release_notes_state_the_limits():
    text = read("docs/release-notes.md")
    assert "Known limits" in text
    assert "not a formal proof" in text
    assert "read only" in text


def test_supported_versions_separates_tested_from_unproved():
    text = read("docs/supported-versions.md")
    assert "What is tested" in text
    assert "What is not supported yet" in text
    assert "What is not proved yet" in text


def test_migration_guide_covers_the_steps():
    text = read("docs/migration-guide.md")
    for step in (
        "parity ingest",
        "parity run",
        "parity kb-capture",
        "parity kb-review",
        "--regression",
    ):
        assert step in text
