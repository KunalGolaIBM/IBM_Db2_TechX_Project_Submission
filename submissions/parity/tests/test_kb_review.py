"""Tests for knowledge base review and the CLI command."""

import pytest

from parity.cli import build_parser
from parity.kb.review import run_review
from parity.kb.store import InMemoryKb, KnownDifference


def filled_kb() -> InMemoryKb:
    kb = InMemoryKb()
    kb.add(KnownDifference(title="candidate one", source_pattern="ILIKE", db2_pattern="UPPER LIKE"))
    kb.add(
        KnownDifference(
            title="keeper",
            source_pattern="LIMIT",
            db2_pattern="FETCH FIRST",
            verified=True,
        )
    )
    return kb


def test_list_shows_only_candidates():
    text = run_review(filled_kb(), "list")
    assert "candidate one" in text
    assert "keeper" not in text


def test_list_empty():
    text = run_review(InMemoryKb(), "list")
    assert text == "no candidates waiting for review"


def test_approve_makes_entry_verified():
    kb = filled_kb()
    text = run_review(kb, "approve", "candidate one")
    assert text == "approved: candidate one"
    assert "candidate one" in [hit.entry.title for hit in kb.search("ILIKE")]
    assert kb.list_candidates() == ()


def test_reject_removes_candidate():
    kb = filled_kb()
    text = run_review(kb, "reject", "candidate one")
    assert text == "rejected: candidate one"
    assert "candidate one" not in [hit.entry.title for hit in kb.search("ILIKE")]
    assert kb.list_candidates() == ()


def test_reject_verified_entry_fails():
    with pytest.raises(ValueError, match="verified entries cannot be rejected"):
        run_review(filled_kb(), "reject", "keeper")


def test_unknown_title_fails():
    with pytest.raises(KeyError):
        run_review(filled_kb(), "approve", "missing")


def test_unknown_action_fails():
    with pytest.raises(ValueError, match="unknown action"):
        run_review(filled_kb(), "merge")


def test_action_without_title_fails():
    with pytest.raises(ValueError, match="title is required"):
        run_review(filled_kb(), "approve")


def test_cli_kb_parser():
    args = build_parser().parse_args(["kb-review", "--action", "list"])
    assert args.command == "kb-review"
    assert args.action == "list"
    assert args.store == "memory"


def test_cli_kb_review_memory_forward(tmp_path, monkeypatch, capsys):
    """The full CLI path with the memory store."""
    from parity import cli

    monkeypatch.chdir(tmp_path)
    code = cli.main(["kb-review", "--action", "list"])
    assert code == 0
    assert "no candidates waiting for review" in capsys.readouterr().out


def test_cli_kb_review_unknown_candidate_exit_2(capsys):
    from parity import cli

    code = cli.main(["kb-review", "--action", "reject", "--title", "missing"])
    assert code == 2
    assert "error:" in capsys.readouterr().out


def test_list_shows_the_title_on_its_own_line():
    kb = InMemoryKb()
    kb.add(KnownDifference(title="rule abc123: SELECT 1", source_pattern="SELECT 1", db2_pattern="SELECT 1 AS 1"))
    text = run_review(kb, "list")
    lines = text.splitlines()
    assert lines[0] == "rule abc123: SELECT 1"
    assert lines[1] == "    source: SELECT 1"


def test_approve_of_an_unknown_title_fails():
    kb = InMemoryKb()
    with pytest.raises(KeyError):
        run_review(kb, "approve", "missing")


def test_approve_of_an_already_verified_entry_fails():
    kb = InMemoryKb()
    kb.add(KnownDifference(title="t", source_pattern="s", db2_pattern="d", verified=True))
    with pytest.raises(ValueError, match="already verified"):
        run_review(kb, "approve", "t")
