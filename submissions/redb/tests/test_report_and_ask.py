from redb.config import Settings
from redb.ledger import UNDO_OK
from redb.llm import Brain
from redb.monitor import write_pct
from redb.report import to_markdown
from redb.sqlguard import is_safe


def test_offline_ask_always_returns_a_safe_select():
    b = Brain(Settings(google_api_key=""))
    for q in ("slowest statements?", "which changes were applied", "ledger history", "indexes", "drop everything"):
        a = b.ask(q)
        assert is_safe(a["sql"]) and a["source"] == "heuristic" and "EMBEDDING" not in a["sql"]
    assert "FOR SYSTEM_TIME" in b.ask("show the history")["sql"]


def test_undo_guard_accepts_only_generated_index_ddl():
    assert UNDO_OK.match('DROP INDEX "RETAIL"."REDB_IX_ORDERS_AB12CD"')
    assert UNDO_OK.match('CREATE INDEX "RETAIL"."IX_OLD" ON "RETAIL"."CUSTOMERS" ("A" ASC, "B" DESC)')
    for bad in ('DROP TABLE "RETAIL"."ORDERS"', 'DROP INDEX "A"."B"; DROP TABLE T', "DROP INDEX RETAIL.X",
                'CREATE UNIQUE INDEX "A"."B" ON "A"."T" ("C" ASC)'):
        assert not UNDO_OK.match(bad)


def test_write_pct():
    assert write_pct(0, 0) == 0.0 and write_pct(75, 25) == 25.0 and write_pct(None, 10) == 100.0


def test_markdown_report():
    state = {
        "cases": [{"case_id": "W1", "sql": "SELECT 1 FROM RETAIL.ORDERS", "plan_cost": 800.0, "plan_summary": "#1 RETURN",
                   "diagnosis": {"headline": "Full scan", "plain_english": "Scans everything.", "root_causes": ["no index"]},
                   "plan_after": {"cost": 7.0}}],
        "proposals": [
            {"id": "a", "kind": "INDEX", "title": "Index on RETAIL.ORDERS (A) for W1", "verified": True,
             "evidence": "800 → 7", "rationale": "no index", "ddl": ['CREATE INDEX "R"."X" ON "R"."T" ("A" ASC)'],
             "undo": ['DROP INDEX "R"."X"'], "rewrite_sql": None},
            {"id": "b", "kind": "REWRITE", "title": "W1: adopt equivalent rewrite", "verified": False,
             "evidence": "REJECTED", "rationale": "", "ddl": [], "undo": [], "rewrite_sql": "SELECT 2 FROM T"}],
        "report": {"narrative": "Faster.", "ms_before": 20.0, "ms_after": 2.0, "reduction_pct": 90.0,
                   "per_statement": [{"case_id": "W1", "ms_before": 20.0, "ms_after": 2.0, "gain_pct": 90.0}],
                   "applied": [{"id": "a", "status": "APPLIED", "change_id": 7}]},
        "log": ["observe: 1"],
    }
    md = to_markdown(state, "offline heuristics")
    assert "| W1 | 20.0 | 2.0 | 90.0 |" in md and "APPLIED (ledger #7)" in md and "- Status: rejected" in md
    assert "7.0 with the proposed indexes (virtual)" in md and 'DROP INDEX "R"."X"' in md
