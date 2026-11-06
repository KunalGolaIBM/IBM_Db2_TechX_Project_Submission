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


def test_the_cookbook_recipe_is_complete_and_holds_no_secrets():
    import json
    import re

    recipe = Path(__file__).resolve().parents[1] / "cookbook" / "09-as-of-search" / "python-local-embeddings"
    nb = json.loads((recipe / "as-of-search.ipynb").read_text(encoding="utf-8"))
    code = [c for c in nb["cells"] if c["cell_type"] == "code"]
    assert code and all(c.get("outputs") for c in code)  # committed as executed, every code cell ran
    text = (recipe / "as-of-search.ipynb").read_text(encoding="utf-8")
    assert "DB2_PASSWORD" in text and not re.search(r"PWD=|password\s*=\s*['\"]", text, re.I)
    assert all(re.match(r"^[A-Za-z0-9_.\-]+==\S+$", line) for line in
               (recipe / "requirements.txt").read_text().splitlines() if line and not line.startswith("#"))
    assert "DB2_PASSWORD=change-me" in (recipe / ".env.example").read_text()
