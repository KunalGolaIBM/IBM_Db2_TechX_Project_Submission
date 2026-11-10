import sys
import os
import unittest

# Add backend directory to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, backend_dir)

from app.database.schema import init_database_tables
from app.database.seed_data import seed_database
from app.database.db2_connector import db_connector
from app.agents.graph import run_agentic_investigation
from app.services.attack_simulator import simulate_multi_vector_compromise

class TestSentinelAIPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_database_tables()
        seed_database()

    def test_database_tables_exist(self):
        """Verify all 7 required IBM Db2 tables exist."""
        tables = [
            "USER_ACCOUNTS", "LOGIN_EVENTS", "ACCESS_LOGS",
            "SECURITY_ALERTS", "INCIDENTS", "AI_ANALYSIS",
            "RESPONSE_RECOMMENDATIONS"
        ]
        for t in tables:
            res = db_connector.execute_query(f"SELECT COUNT(*) as cnt FROM {t}")
            self.assertIsNotNone(res)

    def test_multi_agent_attack_simulation(self):
        """Verify Section 8 attack simulation and 5-agent LangGraph orchestration."""
        result = simulate_multi_vector_compromise("USR-101")
        self.assertTrue(result["success"])
        self.assertIn("incident_id", result)
        self.assertEqual(result["severity"], "CRITICAL")
        self.assertGreaterEqual(result["risk_score"], 80)
        self.assertIn("T1110.001", result["mitre_techniques"])

    def test_human_approval_gate(self):
        """Verify defensive recommendations are queued for human approval."""
        recs = db_connector.execute_query("SELECT * FROM RESPONSE_RECOMMENDATIONS WHERE status = 'PENDING_APPROVAL'")
        self.assertGreater(len(recs), 0)

if __name__ == "__main__":
    unittest.main()
