"""Fast unit tests for pure logic: no Db2 and no LLM needed (they run in about a second)."""
import pytest

from hotelops import costguard, llm
from hotelops.changefeed import change_feed
from hotelops.config import LlmSettings
from hotelops.knowledge import HANDBOOK, parse_handbook
from hotelops.preview import _impact
from hotelops.radar import MAX_DISTANCE, THEME_ANCHORS, _sql
from hotelops.redteam import _code
from hotelops.sqlguard import UnsafeSqlError, validate_select


# --------------------------------------------------------------------------- SQL guard: more attack variants
@pytest.mark.parametrize("sql", [
    "delete from guests",
    "DeLeTe FROM GUESTS WHERE 1=1",
    "MERGE INTO RATE_PLAN T USING (VALUES 1) S(X) ON 1=1 WHEN MATCHED THEN UPDATE SET RATE = 1",
    "TRUNCATE TABLE AGENT_STEPS IMMEDIATE",
    "ALTER TABLE GUESTS DEACTIVATE COLUMN ACCESS CONTROL",
    "WITH X AS (SELECT 1 FROM SYSIBM.SYSDUMMY1) SELECT * FROM X; CREATE TABLE T (A INT)",
    "SET CURRENT SCHEMA = SYSIBM",
    "LOCK TABLE GUESTS IN EXCLUSIVE MODE",
    "REVOKE SELECT ON GUESTS FROM ROLE HOTELOPS_AGENT",
    "EXPORT TO /tmp/x.csv OF DEL SELECT * FROM GUESTS",
    "SELECT * FROM TABLE(SYSPROC.ADMIN_CMD('EXPORT TO /tmp/x OF DEL SELECT * FROM GUESTS'))",
    "CALL SYSPROC.ADMIN_CMD('REORG TABLE GUESTS')",
    "SELECT 1 FROM SYSIBM.SYSDUMMY1 -- harmless\n; DROP TABLE ROOMS",
    "   ",
    "EXPLAIN PLAN FOR SELECT * FROM GUESTS",
])
def test_more_unsafe_statements_rejected(sql):
    with pytest.raises(UnsafeSqlError):
        validate_select(sql)


@pytest.mark.parametrize("sql", [
    "select * from v_daily_kpis",
    "VALUES CURRENT DATE",
    "SELECT ROOM_NO, ROW_NUMBER() OVER (ORDER BY ROOM_NO) AS RN FROM ROOMS",
    "SELECT * FROM GUEST_REVIEWS WHERE REVIEW_TEXT LIKE '%drop table%' AND REVIEW_TEXT NOT LIKE '%; delete%'",
    "SELECT 'it''s fine' AS X FROM SYSIBM.SYSDUMMY1",
    "/* the analyst */ SELECT COUNT(*) FROM RESERVATIONS",
    "SELECT UPDATED_BY, CHANGE_REASON FROM RATE_PLAN",
])
def test_legitimate_queries_pass(sql):
    out = validate_select(sql, row_limit=10)
    assert "FETCH FIRST" in out.upper()


# --------------------------------------------------------------------------- dry-run impact maths
def test_rate_change_impact_reports_revenue_and_break_even():
    before = {"nights": [{"STAY_DATE": "2026-11-20", "RATE": 1000.0, "UNSOLD_ROOMS": 4},
                         {"STAY_DATE": "2026-11-21", "RATE": 1000.0, "UNSOLD_ROOMS": 0}]}
    after = {"nights": [{"STAY_DATE": "2026-11-20", "RATE": 800.0, "UNSOLD_ROOMS": 4},
                        {"STAY_DATE": "2026-11-21", "RATE": 800.0, "UNSOLD_ROOMS": 0}]}
    out = _impact("RATE_CHANGE", before, after)
    assert [r["CHANGE_PCT"] for r in out["rows"]] == [-20.0, -20.0]
    assert out["rows"][0]["REVENUE_DELTA_IF_SOLD"] == -800
    assert "25% more rooms" in out["summary"]                     # 1000/800 - 1
    assert any("sold out" in w for w in out["warnings"])          # second night has no unsold rooms


def test_maintenance_impact_flags_oversell_and_guests():
    inv = lambda sellable, sold: [{"STAY_DATE": "2026-11-17", "ROOM_TYPE_CODE": "DLX",  # noqa: E731
                                   "ROOMS_IN_SERVICE": sellable, "ROOMS_SOLD": sold}]
    before = {"room": [{"ROOM_NO": "307", "STATUS": "IN_SERVICE"}], "inventory": inv(20, 20), "tickets": 0,
              "guests": [{"RESERVATION_ID": 1}]}
    after = {"room": [{"ROOM_NO": "307", "STATUS": "OUT_OF_ORDER"}], "inventory": inv(19, 20), "tickets": 1,
             "guests": []}
    out = _impact("MAINTENANCE", before, after)
    assert out["rows"][0]["OVERSOLD_BY"] == 1
    assert any("OVERSOLD" in w for w in out["warnings"]) and any("1 active" in w for w in out["warnings"])


def test_upgrade_impact_lists_changed_fields_only():
    b = {"RESERVATION_ID": 7, "FULL_NAME": "A", "ROOM_TYPE": "STD", "ROOM_NO": "101", "CHECK_IN": "x",
         "CHECK_OUT": "y", "SPECIAL_NOTE": "n"}
    a = dict(b, ROOM_TYPE="PRM", ROOM_NO="405")
    out = _impact("ROOM_UPGRADE", {"reservation": [b]}, {"reservation": [a]})
    assert {r["FIELD"] for r in out["rows"]} == {"ROOM_TYPE", "ROOM_NO"}


# --------------------------------------------------------------------------- LLM quota handling
DAILY = ("429 RESOURCE_EXHAUSTED. Quota exceeded: GenerateRequestsPerDayPerProjectPerModel-FreeTier, "
         "'retryDelay': '19969s'")
MINUTE = "429 RESOURCE_EXHAUSTED. Quota exceeded per minute. 'retryDelay': '17s'"


@pytest.mark.parametrize("text,daily,transient", [
    (DAILY, True, True), (MINUTE, False, True), ("503 UNAVAILABLE overloaded", False, True),
    ("400 INVALID_ARGUMENT bad schema", False, False), ("500 INTERNAL", False, True),
])
def test_error_classification(text, daily, transient):
    exc = RuntimeError(text)
    assert llm._is_daily_quota(exc) is daily
    assert llm._is_transient(exc) is transient


def test_retry_delay_is_parsed():
    assert llm._retry_delay(RuntimeError(MINUTE)) == 17.0
    assert llm._retry_delay(RuntimeError("no hint")) is None


def test_model_chain_deduplicates_and_keeps_order(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "a")
    monkeypatch.setenv("LLM_FALLBACK_MODELS", "b, a ,c,,b")
    assert llm.model_chain() == ["a", "b", "c"]


def test_friendly_error_only_for_quota_problems():
    assert "rate-limiting" in llm.friendly_llm_error(RuntimeError(MINUTE))
    assert llm.friendly_llm_error(ValueError("boom")) is None


# --------------------------------------------------------------------------- configuration
@pytest.mark.parametrize("provider,env,missing", [
    ("gemini", {"GOOGLE_API_KEY": ""}, True),
    ("gemini", {"GOOGLE_API_KEY": "your_gemini_api_key_here"}, True),
    ("gemini", {"GOOGLE_API_KEY": "AIzaSyREALLOOKINGKEY"}, False),
    ("openai", {"OPENAI_API_KEY": "change_me"}, True),
    ("ollama", {}, False),
])
def test_missing_credentials(monkeypatch, provider, env, missing):
    for k in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert (LlmSettings(provider, "m", 0.0).missing_credentials() is not None) is missing


def test_cost_ceiling_is_configurable(monkeypatch):
    monkeypatch.setenv("SQL_MAX_COST", "1234")
    assert costguard.max_cost() == 1234.0


# --------------------------------------------------------------------------- knowledge, radar, change feed, red team
def test_policy_handbook_parses_into_unique_policies():
    sections = parse_handbook(HANDBOOK.read_text(encoding="utf-8"))
    ids = [pid for pid, _, _ in sections]
    assert len(ids) == 12 and len(set(ids)) == 12
    assert all(body and title for _, title, body in sections)
    assert {"POL-GR-01", "POL-ENG-01", "POL-AI-01", "POL-RM-01"} <= set(ids)


def test_radar_sql_binds_two_parameters_per_theme():
    sql = _sql()
    assert sql.count("VECTOR(?, 384, FLOAT32)") == len(THEME_ANCHORS)
    assert "GROUPING SETS" in sql and 0.25 < MAX_DISTANCE < 0.33


class _FakeDb:
    def __init__(self):
        self.params = []

    def query(self, sql, params=()):
        self.params.append(params)
        return []


@pytest.mark.parametrize("hours,expected", [(0, 1), (24, 24), (100000, 720)])
def test_change_feed_window_is_clamped(hours, expected):
    db = _FakeDb()
    out = change_feed(db, hours)
    assert out["window_hours"] == expected and all(p == (expected,) for p in db.params)


@pytest.mark.parametrize("msg,code", [
    ("[IBM][CLI Driver] SQL0551N The statement failed", "SQL0551N"),
    ("SQL20471N something", "SQL20471N"),
])
def test_redteam_extracts_db2_error_codes(msg, code):
    assert _code(RuntimeError(msg)) == code


def test_oversized_tool_output_is_trimmed_but_stays_valid_json():
    import json

    from hotelops.tools import MAX_TOOL_CHARS, _dump

    big = {"rows": [{"text": "x" * 200, "n": i} for i in range(500)], "note": "keep me"}
    out = _dump(big)
    parsed = json.loads(out)
    assert len(out) <= MAX_TOOL_CHARS and "_truncated" in parsed
    assert parsed["result"]["note"] == "keep me" and 0 < len(parsed["result"]["rows"]) < 500
    assert _dump({"a": 1}) == '{"a": 1}'



def test_latest_anchor_reads_the_last_line(tmp_path):
    from hotelops.audit import latest_anchor

    f = tmp_path / "a.jsonl"
    assert latest_anchor(f) is None
    lines = ['{"step_id": 1, "row_hash": "A"}', '{"step_id": 2, "row_hash": "B"}', ""]
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert latest_anchor(f) == {"step_id": 2, "row_hash": "B"}


def test_rehash_sql_matches_the_trigger_formula():
    """The rebuilt-ledger demo must hash exactly like TRG_STEPS_HASH_CHAIN, or the demo would prove nothing."""
    from pathlib import Path

    from hotelops.audit import CHAIN_SQL, REHASH_SQL

    trigger = (Path(__file__).resolve().parents[1] / "src" / "sql" / "01_schema.sql").read_text(encoding="utf-8")
    for part in ("TRIM(CHAR(STEP_ID))", "RUN_ID", "AGENT", "TOOL_NAME", "TRIM(CHAR(OK))",
                 "CAST(SUBSTR(COALESCE(TOOL_INPUT, ''), 1, 2000) AS VARCHAR(8000))",
                 "CAST(SUBSTR(COALESCE(TOOL_OUTPUT, ''), 1, 2000) AS VARCHAR(8000))", ", 2))"):
        assert part in REHASH_SQL and part in CHAIN_SQL
    assert "CAST(SUBSTR(COALESCE(N.TOOL_OUTPUT, ''), 1, 2000) AS VARCHAR(8000)), 2))" in trigger


def test_promotion_tool_is_available_to_analyst_and_operations():
    from hotelops.tools import AGENT_TOOLSETS

    assert "promotion_on" in AGENT_TOOLSETS["analyst"] and "promotion_on" in AGENT_TOOLSETS["operations"]
