"""The pre-commit secret check catches short secrets too, without tripping on ordinary words."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_secrets.py"
spec = importlib.util.spec_from_file_location("check_secrets", SCRIPT)
check_secrets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_secrets)


def test_long_secrets_are_found_anywhere_in_a_line():
    assert check_secrets.leaks("sk-or-v1-abcdef123456", 'key = "sk-or-v1-abcdef123456"')
    assert check_secrets.leaks("Hunter2Hunter2", "pw=xHunter2Hunter2x")


def test_short_secrets_are_found_as_words():
    assert check_secrets.leaks("db2pw", "PASSWORD=db2pw")
    assert check_secrets.leaks("db2pw", "connect using db2pw now")


def test_short_secrets_inside_other_words_do_not_trip():
    assert not check_secrets.leaks("db2pw", "the db2pwd file")
    assert not check_secrets.leaks("test", "pytest -q")
