"""Pure-Python guards: no database or model needed."""
import pytest
from ask import check_sql, Refused, ask
from explain import category, numbers, BANNED

def test_select_on_audited_view_is_allowed_and_capped():
    sql = check_sql("SELECT STATION, COUNT(*) FROM AQ.V_DAY GROUP BY STATION")
    assert sql.endswith("FETCH FIRST 50 ROWS ONLY")

def test_limit_is_rewritten_for_db2():
    assert check_sql("SELECT * FROM AQ.V_DAY LIMIT 5").endswith("FETCH FIRST 5 ROWS ONLY")

@pytest.mark.parametrize("sql", [
    "DELETE FROM AQ.V_DAY",
    "UPDATE AQ.VERDICT SET AQI = 1",
    "SELECT * FROM AQ.READING",
    "SELECT * FROM AQ.V_DAY; DROP TABLE AQ.READING",
    "SELECT * FROM SYSCAT.TABLES",
    "SELECT D.* FROM AQ.V_DAY D JOIN AQ.EVIDENCE E ON 1=1",
])
def test_anything_else_is_refused(sql):
    with pytest.raises(Refused):
        check_sql(sql)

@pytest.mark.parametrize("q", ["Will Anand Vihar be severe tomorrow?", "Is it safe to run outside in ITO?",
                               "Who is responsible for the fraud?"])
def test_out_of_scope_questions_refused_before_any_model_call(q):
    assert ask(q)["refused"] is True

def test_cpcb_categories():
    assert [category(x) for x in (None, 50, 51, 200, 301, 401)] == ["none", "Good", "Satisfactory", "Moderate", "Very Poor", "Severe"]

def test_number_and_advice_detectors():
    assert numbers("AQI was 175 on 23 October.") == {"175", "23"}
    assert BANNED.search("People should wear a mask")
    assert not BANNED.search("No AQI can be calculated for this day")

def test_short_station_names_become_like():
    assert "STATION LIKE '%ITO%'" in check_sql("SELECT MAX(AQI) FROM AQ.V_DAY WHERE STATION = 'ITO'")

def test_aqi_ranking_puts_refused_days_last():
    assert "AQI DESC NULLS LAST" in check_sql("SELECT STATION FROM AQ.V_DAY ORDER BY AQI DESC")

def test_streaming_stops_at_end_of_statement():
    from ask import sql_done
    assert sql_done("SELECT COUNT(*) FROM AQ.V_DAY;")
    assert sql_done("SELECT STATION FROM AQ.V_DAY ORDER BY AQI DESC FETCH FIRST 1 ROWS ONLY")
    assert sql_done("SELECT 1 FROM AQ.V_DAY\n\nThis query counts")
    assert not sql_done("SELECT STATION, COUNT(*) FROM AQ.V_DAY WHERE STATUS =")

def test_question_normalisation_for_reuse():
    import app
    assert app.norm("  Which station   was worst? ") == app.norm("which station was worst")
    assert app.norm("Which station was worst?") != app.norm("Which station was best?")

def test_checker_refuses_cross_joins_and_clamps_row_cap():
    from ask import check_sql, Refused
    with pytest.raises(Refused):
        check_sql("SELECT * FROM AQ.V_DAY, AQ.V_CHECK")
    with pytest.raises(Refused):
        check_sql("SELECT * FROM AQ.V_DAY CROSS JOIN AQ.V_CHECK")
    assert check_sql("SELECT STATION FROM AQ.V_DAY FETCH FIRST 5000 ROWS ONLY").endswith("FETCH FIRST 50 ROWS ONLY")
    assert check_sql("SELECT STATION FROM AQ.V_DAY").endswith("FETCH FIRST 50 ROWS ONLY")
