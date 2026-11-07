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

    recipe = Path(__file__).resolve().parents[1] / "cookbook" / "09-temporal-search" / "python-local-embeddings"
    nb = json.loads((recipe / "temporal-search.ipynb").read_text(encoding="utf-8"))
    code = [c for c in nb["cells"] if c["cell_type"] == "code"]
    assert code and all(c.get("outputs") for c in code)  # committed as executed, every code cell ran
    text = (recipe / "temporal-search.ipynb").read_text(encoding="utf-8")
    assert "DB_PASSWORD" in text and not re.search(r"PWD=|password\s*=\s*['\"]", text, re.I)
    assert not re.search(r"/(?:Users|home|private|tmp|var/folders)/", text)  # no local paths in the outputs
    assert all(re.match(r"^[A-Za-z0-9_.\-]+==\S+$", line) for line in
               (recipe / "requirements.txt").read_text().splitlines() if line and not line.startswith("#"))
    assert "DB_PASSWORD=your-db2-password" in (recipe / ".env.example").read_text()


def test_the_dbt_project_takes_credentials_only_from_the_environment():
    import re

    root = Path(__file__).resolve().parents[1] / "dbt"
    profile = (root / "profiles.yml").read_text()
    assert "env_var('DB2_PASSWORD')" in profile and not re.search(r"password:\s*[^\s\"{]", profile)
    pins = [line for line in (root / "requirements-dbt.txt").read_text().splitlines() if line and not line.startswith("#")]
    assert pins and all("==" in line for line in pins)
    models = sorted(p.stem for p in (root / "models").rglob("*.sql"))
    assert models == ["mart_clause_version_outcomes", "mart_coverage_by_area", "mart_decisions_daily",
                      "stg_claims", "stg_decisions"]
    for sql in (root / "models").rglob("*.sql"):  # the marts never read the masked ledger text
        assert not re.search(r"QUESTION_REDACTED|DRAFT_REDACTED|FINAL_ANSWER|VERDICTS_JSON", sql.read_text())
