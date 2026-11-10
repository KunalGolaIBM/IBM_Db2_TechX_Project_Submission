"""Tests for the parity ingest subcommand."""

import pytest

from parity import cli
from parity.cli import build_parser


def test_ingest_parser():
    args = build_parser().parse_args(["ingest", "--dir", "samples"])
    assert args.command == "ingest"
    assert args.dir == "samples"


def test_ingest_counts_queries(tmp_path, capsys):
    (tmp_path / "q.sql").write_text(
        "SELECT id FROM demo_users; DELETE FROM demo_users;", encoding="utf-8"
    )
    code = cli.main(["ingest", "--dir", str(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "queries: 2" in out
    assert "read only: 1" in out
    assert "write: 1" in out
    assert "tables: demo_users" in out


def test_ingest_counts_untranslatable(tmp_path, capsys):
    (tmp_path / "q.sql").write_text(
        "SELECT data->>'k' FROM demo_users;", encoding="utf-8"
    )
    code = cli.main(["ingest", "--dir", str(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "untranslatable by rules: 1" in out


def test_ingest_deduplicates(tmp_path, capsys):
    (tmp_path / "a.sql").write_text("SELECT 1; SELECT 1;", encoding="utf-8")
    code = cli.main(["ingest", "--dir", str(tmp_path)])
    assert code == 0
    assert "queries: 1" in capsys.readouterr().out


def test_ingest_missing_dir():
    with pytest.raises(ValueError, match="directory not found"):
        cli.main(["ingest", "--dir", "no-such-dir"])
