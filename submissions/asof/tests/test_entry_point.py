"""src/main.py is the documented way to start AsOf; it must hand over to asof.api.main."""

from __future__ import annotations

import runpy
from pathlib import Path

import asof.api

MAIN = Path(__file__).resolve().parents[1] / "src" / "main.py"


def test_main_py_starts_the_api_with_the_same_options(monkeypatch):
    seen = {}
    monkeypatch.setattr(asof.api, "main", lambda argv=None: seen.setdefault("called", True))
    runpy.run_path(str(MAIN), run_name="__main__")
    assert seen == {"called": True}


def test_main_py_does_nothing_on_import():
    ns = runpy.run_path(str(MAIN), run_name="not_main")
    assert "main" in ns
