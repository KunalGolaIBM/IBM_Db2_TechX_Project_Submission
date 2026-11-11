"""
Module: tests/test_live_db2_smoke.py
Opt-In Live IBM Db2 LUW 12.1 Integration Smoke Test.

Automatically skipped offline (`MockDb2` default). Runs live relational DDL,
Recursive BOM CTE, `SEQ_BB_ORDER_ID`, `SP_RESERVE_CAKE_STOCK`, audit hash chain,
and `DB2LlamaVS` round-trip when `submissions/bakebox-choco-ai/.env` points to a
running IBM Db2 container (`docker compose up -d`).
"""
import os
import sys
import unittest

_pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from src.db import db_session, is_live_db2_available
from src.ingest import init_relational_tables, run_ingestion
from src.order_engine import (
    check_recipe_bom_availability,
    verify_audit_chain,
)


@unittest.skipUnless(
    is_live_db2_available(),
    "Live IBM Db2 credentials not configured (set DB2_USER/DB2_PASSWORD & DB2_FORCE_MOCK=false to run)",
)
class TestLiveDb2Smoke(unittest.TestCase):
    """Verify real IBM Db2 12.1 LUW container connectivity and SQL objects end-to-end."""

    def test_01_live_ddl_bom_audit_and_vector_ingest(self):
        with db_session() as conn:
            init_relational_tables(conn)
            bom = check_recipe_bom_availability(conn, cake_id=1, quantity=1)
            self.assertGreater(len(bom), 0)
            ok, bad_id, _ = verify_audit_chain(conn)
            self.assertTrue(ok, f"Live Db2 audit chain broke at {bad_id}")

        run_ingestion()


if __name__ == "__main__":
    unittest.main()
