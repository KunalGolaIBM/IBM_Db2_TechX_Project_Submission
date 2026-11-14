"""Read-only SQL boundary and analyst fallback behavior."""
from types import SimpleNamespace

import pytest

from analyst import Analyst, QUICK_QUESTIONS, UnsafeSQL, guard_sql
import llm


@pytest.mark.parametrize("sql", [
    "INSERT INTO PG_ENTITIES VALUES (1)", "UPDATE PG_ENTITIES SET STATUS='TRUSTED'",
    "DELETE FROM PG_REPORTS", "MERGE INTO PG_ENTITIES USING PG_REPORTS ON 1=1",
    "DROP TABLE PG_REPORTS", "CREATE TABLE X (A INT)", "ALTER TABLE PG_REPORTS ADD X INT",
    "SELECT 1 FROM PG_SCREENINGS; SELECT 2 FROM PG_SCREENINGS", "SELECT 1;;",
    "SELECT 1 FROM PG_SCREENINGS /* ; DROP TABLE PG_REPORTS */",
    "SELECT 1 FROM PG_SCREENINGS -- hidden\n;DELETE FROM PG_REPORTS",
    "SELECT EM/**/BEDDING FROM PG_REPORTS", "SELECT \"EMBEDDING\" FROM PG_REPORTS",
    "SELECT * FROM PG_REPORTS", "SELECT P.* FROM PG_SCAM_PATTERNS P",
    "SELECT * FROM SYSCAT.TABLES", "SELECT 1 FROM PG_SCREENINGS, SYSCAT.TABLES",
    "SELECT 1 FROM PG_SCREENINGS CROSS JOIN PG_META", "SELECT 1 FROM OTHER.PG_ENTITIES",
    "WITH SYSCAT AS (SELECT 1 FROM PG_ENTITIES) SELECT * FROM SYSCAT.TABLES",
    "SELECT * FROM TABLE(SYSPROC.ADMIN_GET_TAB_INFO('X','Y'))",
    "SELECT EVIL_FUNCTION(ID) FROM PG_SCREENINGS", "SELECT ID INTO X FROM PG_SCREENINGS",
])
def test_sql_attacks_are_rejected(sql):
    with pytest.raises(UnsafeSQL):
        guard_sql(sql)


@pytest.mark.parametrize("title", list(QUICK_QUESTIONS))
def test_all_presets_run_without_a_key(repo, title):
    result = Analyst(repo).answer(title)
    assert result["mode"] == "preset" and result["sql"].endswith("FETCH FIRST 100 ROWS ONLY")


def test_row_limits_and_cte_scope():
    # COUNT(*) counts rows without exposing vector columns.
    assert guard_sql("SELECT COUNT(*) FROM PG_REPORTS").endswith("FETCH FIRST 100 ROWS ONLY")
    assert guard_sql("SELECT ID FROM PG_REPORTS FETCH FIRST 99999 ROWS ONLY").endswith("FETCH FIRST 100 ROWS ONLY")
    safe = guard_sql("WITH X AS (SELECT ID FROM PG_ENTITIES) SELECT * FROM X", max_rows=5)
    assert safe.endswith("FETCH FIRST 5 ROWS ONLY")
    with pytest.raises(UnsafeSQL):
        guard_sql("gibberish")


def test_analyst_schema_cached_and_unknown_preset_rejected(repo, monkeypatch):
    calls = []
    monkeypatch.setattr(repo, "schema_description", lambda: calls.append(1) or "PG_ENTITIES(ID INT)")
    analyst = Analyst(repo)
    assert analyst.schema() == analyst.schema()
    assert len(calls) == 1
    with pytest.raises(KeyError):
        analyst.run_quick("unknown")


def model(sql="SELECT ID FROM PG_ENTITIES", summary="Three rows"):
    return SimpleNamespace(generate_json=lambda *a, **k: {"sql": sql}, generate=lambda *a, **k: summary)


def test_analyst_generated_query_and_summary(repo):
    result = Analyst(repo, model()).answer("How many accounts?")
    assert result["mode"] == "gemini" and result["summary"] == "Three rows"


def test_analyst_rejected_query(repo):
    assert Analyst(repo, model("DELETE FROM PG_ENTITIES")).answer("Delete all")["mode"] == "rejected"


def test_analyst_database_error_is_a_structured_result(repo, monkeypatch):
    def fail(sql):
        raise RuntimeError("offline")
    monkeypatch.setattr(repo, "run_readonly", fail)
    assert Analyst(repo, model()).answer("Question")["mode"] == "error"


def test_analyst_unavailable_model_and_summary_failure(repo):
    def fail(*a, **k):
        raise llm.LLMUnavailable("offline")
    assert Analyst(repo, SimpleNamespace(generate_json=fail)).answer("Question")["mode"] == "unavailable"
    provider = model()
    provider.generate = fail
    assert Analyst(repo, provider).answer("Question")["mode"] == "gemini"
