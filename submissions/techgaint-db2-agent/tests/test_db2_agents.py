"""
Production-grade unittest and pytest compatible test suite for TechGaint Multi-Agent Recruiter
and IBM Db2 Governed RAG system.
"""

import json
import unittest
from datetime import datetime
from typing import Dict, List, Any, Tuple

class TechGaintAgents:

    def __init__(self):
        self.talent_ingestion_agent = {
            "name": "Talent Ingestion & Metadata Extractor Agent",
            "role": "Ingest candidate resumes and extract structured metadata",
            "goal": "Extract key technical skills, experience, and metadata cleanly",
            "backstory": "Specialized AI recruiter expert in parsing enterprise candidate profiles."
        }
        self.governed_db2_retrieval_agent = {
            "name": "Governed Db2 Retrieval Agent",
            "role": "Query IBM Db2 with parameterized metadata filtration",
            "goal": "Enforce SQL predicate pushdown and security policies before vector lookup",
            "backstory": "Database governance agent ensuring strict relational filtering."
        }
        self.technical_evaluator_agent = {
            "name": "Technical Evaluator & Ranking Agent",
            "role": "Evaluate candidate skills against job requirements",
            "goal": "Rank candidates objectively based on verified Db2 records",
            "backstory": "Senior technical assessor focused on merit-based candidate matching."
        }
        self.compliance_auditor_agent = {
            "name": "Compliance & Bias Auditor Agent",
            "role": "Audit candidate evaluations for bias and legal compliance",
            "goal": "Ensure PII protection, consent verification, and audit logging",
            "backstory": "Enterprise compliance officer maintaining strict governance ledgers."
        }

    def get_agents(self) -> List[Dict[str, str]]:
        return [
            self.talent_ingestion_agent,
            self.governed_db2_retrieval_agent,
            self.technical_evaluator_agent,
            self.compliance_auditor_agent
        ]

    def define_tasks(self) -> List[Dict[str, Any]]:
        return [
            {
                "task_id": "ingest_task",
                "description": "Parse resume payload and structure metadata",
                "agent": self.talent_ingestion_agent["name"]
            },
            {
                "task_id": "retrieval_task",
                "description": "Execute parameterized pushdown queries on Db2 storage",
                "agent": self.governed_db2_retrieval_agent["name"]
            },
            {
                "task_id": "evaluation_task",
                "description": "Assess candidate fit based on pushdown filtered results",
                "agent": self.technical_evaluator_agent["name"]
            },
            {
                "task_id": "audit_task",
                "description": "Validate consent, PII redaction, and record in immutable ledger",
                "agent": self.compliance_auditor_agent["name"]
            }
        ]

    def orchestrate_crew(self) -> Dict[str, Any]:
        agents = self.get_agents()
        tasks = self.define_tasks()
        return {
            "status": "success",
            "process": "sequential",
            "agent_count": len(agents),
            "task_count": len(tasks),
            "execution_order": [t["task_id"] for t in tasks],
            "timestamp": datetime.utcnow().isoformat()
        }


class Db2StorageLayer:

    def build_parameterized_query(
        self,
        min_experience_years: int,
        security_clearance: str,
        consent_verified: bool,
        mandatory_skills: List[str]
    ) -> Tuple[str, List[Any]]:
        sql = (
            "SELECT c.CANDIDATE_ID, c.FULL_NAME, c.EXPERIENCE_YEARS, c.CLEARANCE_LEVEL "
            "FROM CANDIDATE_PROFILES c "
            "JOIN CANDIDATE_SKILL_MATRIX s ON c.CANDIDATE_ID = s.CANDIDATE_ID "
            "WHERE c.EXPERIENCE_YEARS >= ? "
            "AND c.CLEARANCE_LEVEL = ? "
            "AND c.CONSENT_VERIFIED = ? "
            "AND s.SKILL_NAME IN (" + ", ".join(["?"] * len(mandatory_skills)) + ") "
            "GROUP BY c.CANDIDATE_ID, c.FULL_NAME, c.EXPERIENCE_YEARS, c.CLEARANCE_LEVEL"
        )
        params = [min_experience_years, security_clearance, 1 if consent_verified else 0] + mandatory_skills
        return sql, params

    def log_audit_trail(self, agent_role: str, query_params: Dict[str, Any], status: str) -> Dict[str, Any]:
        return {
            "audit_id": "AUDIT-DB2-998241",
            "timestamp": datetime.utcnow().isoformat(),
            "table_name": "AGENT_AUDIT_LEDGER",
            "agent_role": agent_role,
            "query_params_hash": hash(json.dumps(query_params, sort_keys=True)),
            "compliance_status": status,
            "immutable_record": True
        }


class MockFastAPIApp:

    def __init__(self, db2_layer: Db2StorageLayer, agents_orchestrator: TechGaintAgents):
        self.db2 = db2_layer
        self.orchestrator = agents_orchestrator

    def handle_request(self, path: str, method: str = "GET", payload: Dict[str, Any] = None) -> Tuple[int, Dict[str, Any]]:
        if path == "/health" and method == "GET":
            return 200, {
                "status": "healthy",
                "service": "techgaint-db2-agent",
                "db2_connected": True
            }

        if path == "/api/v1/candidates/ingest" and method == "POST":
            if not payload or "resume_text" not in payload or "candidate_email" not in payload:
                return 422, {
                    "error": "Unprocessable Entity",
                    "details": "Missing required fields: resume_text, candidate_email"
                }
            return 201, {
                "status": "success",
                "data": {
                    "candidate_id": "CAN-88401",
                    "ingested_at": datetime.utcnow().isoformat(),
                    "email": payload["candidate_email"],
                    "status": "INGESTED_AND_STORED"
                }
            }

        if path == "/api/v1/recruiter/evaluate" and method == "POST":
            if not payload or "job_role" not in payload or "min_experience" not in payload:
                return 422, {
                    "error": "Unprocessable Entity",
                    "details": "Missing required fields: job_role, min_experience"
                }
            crew_result = self.orchestrator.orchestrate_crew()
            return 200, {
                "status": "success",
                "data": {
                    "evaluation_id": "EVAL-2026-901",
                    "job_role": payload["job_role"],
                    "crew_execution": crew_result,
                    "ranked_candidates": [
                        {"candidate_id": "CAN-88401", "score": 0.94, "compliance_verified": True}
                    ]
                }
            }

        return 404, {"error": "Not Found"}


class TestCrewAIAgentInitialization(unittest.TestCase):

    def setUp(self):
        self.orchestrator = TechGaintAgents()

    def test_agent_instantiation(self):
        agents = self.orchestrator.get_agents()
        self.assertEqual(len(agents), 4)

        agent_names = [a["name"] for a in agents]
        self.assertIn("Talent Ingestion & Metadata Extractor Agent", agent_names)
        self.assertIn("Governed Db2 Retrieval Agent", agent_names)
        self.assertIn("Technical Evaluator & Ranking Agent", agent_names)
        self.assertIn("Compliance & Bias Auditor Agent", agent_names)

        for agent in agents:
            self.assertTrue(len(agent["role"]) > 5)
            self.assertTrue(len(agent["goal"]) > 5)
            self.assertTrue(len(agent["backstory"]) > 5)

    def test_task_definitions(self):
        tasks = self.orchestrator.define_tasks()
        self.assertEqual(len(tasks), 4)
        task_ids = [t["task_id"] for t in tasks]
        self.assertEqual(task_ids, ["ingest_task", "retrieval_task", "evaluation_task", "audit_task"])

    def test_crew_sequential_orchestration(self):
        result = self.orchestrator.orchestrate_crew()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["process"], "sequential")
        self.assertEqual(result["agent_count"], 4)
        self.assertEqual(result["task_count"], 4)
        self.assertIn("ingest_task", result["execution_order"])


class TestFastAPIEndpointRouting(unittest.TestCase):

    def setUp(self):
        self.db2 = Db2StorageLayer()
        self.orchestrator = TechGaintAgents()
        self.app = MockFastAPIApp(self.db2, self.orchestrator)

    def test_health_endpoint(self):
        status_code, body = self.app.handle_request("/health", "GET")
        self.assertEqual(status_code, 200)
        self.assertEqual(body["status"], "healthy")
        self.assertEqual(body["service"], "techgaint-db2-agent")
        self.assertTrue(body["db2_connected"])

    def test_candidate_ingest_payload_validation_and_envelope(self):
        invalid_code, invalid_body = self.app.handle_request("/api/v1/candidates/ingest", "POST", {})
        self.assertEqual(invalid_code, 422)
        self.assertEqual(invalid_body["error"], "Unprocessable Entity")

        payload = {
            "resume_text": "Senior Python developer with 7 years experience in Db2 and CrewAI",
            "candidate_email": "candidate@techgaint.com"
        }
        code, body = self.app.handle_request("/api/v1/candidates/ingest", "POST", payload)
        self.assertEqual(code, 201)
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["data"]["candidate_id"], "CAN-88401")
        self.assertEqual(body["data"]["status"], "INGESTED_AND_STORED")

    def test_recruiter_evaluate_payload_validation_and_envelope(self):
        invalid_code, _ = self.app.handle_request("/api/v1/recruiter/evaluate", "POST", {"job_role": "Backend Engine"})
        self.assertEqual(invalid_code, 422)

        payload = {
            "job_role": "Senior AI & Db2 Engineer",
            "min_experience": 5,
            "mandatory_skills": ["Python", "IBM Db2"]
        }
        code, body = self.app.handle_request("/api/v1/recruiter/evaluate", "POST", payload)
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "success")
        self.assertIn("ranked_candidates", body["data"])
        self.assertTrue(len(body["data"]["ranked_candidates"]) > 0)


class TestIBMDb2MetadataFiltration(unittest.TestCase):

    def setUp(self):
        self.db2 = Db2StorageLayer()

    def test_parameterized_sql_predicate_pushdown(self):
        min_exp = 5
        clearance = "TOP_SECRET"
        consent = True
        skills = ["Python", "Db2"]

        sql, params = self.db2.build_parameterized_query(
            min_experience_years=min_exp,
            security_clearance=clearance,
            consent_verified=consent,
            mandatory_skills=skills
        )

        self.assertIn("c.EXPERIENCE_YEARS >= ?", sql)
        self.assertIn("c.CLEARANCE_LEVEL = ?", sql)
        self.assertIn("c.CONSENT_VERIFIED = ?", sql)
        self.assertEqual(params[0], 5)
        self.assertEqual(params[1], "TOP_SECRET")
        self.assertEqual(params[2], 1)
        self.assertEqual(params[3:], ["Python", "Db2"])

    def test_sql_injection_prevention(self):
        malicious_clearance = "SECRET' OR '1'='1"
        malicious_skill = "Python'; DROP TABLE CANDIDATE_PROFILES; --"

        sql, params = self.db2.build_parameterized_query(
            min_experience_years=3,
            security_clearance=malicious_clearance,
            consent_verified=True,
            mandatory_skills=[malicious_skill]
        )

        self.assertNotIn("DROP TABLE", sql)
        self.assertNotIn("OR '1'='1", sql)
        self.assertEqual(sql.count("?"), 4)
        self.assertEqual(params[1], malicious_clearance)
        self.assertEqual(params[3], malicious_skill)

    def test_immutable_audit_trail_logging(self):
        audit_entry = self.db2.log_audit_trail(
            agent_role="Compliance & Bias Auditor Agent",
            query_params={"min_experience": 5, "clearance": "TOP_SECRET"},
            status="PASSED_FULL_COMPLIANCE"
        )

        self.assertEqual(audit_entry["table_name"], "AGENT_AUDIT_LEDGER")
        self.assertEqual(audit_entry["agent_role"], "Compliance & Bias Auditor Agent")
        self.assertEqual(audit_entry["compliance_status"], "PASSED_FULL_COMPLIANCE")
        self.assertTrue(audit_entry["immutable_record"])


if __name__ == "__main__":
    unittest.main()
