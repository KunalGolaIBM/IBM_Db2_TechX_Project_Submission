# Db2Sentinel AI — Testing & Verification Guide

This guide describes how to run automated tests, verify IBM Db2 integration, and simulate cybersecurity scenarios against **Db2Sentinel AI**.

---

## 1. Test Suite Overview

Db2Sentinel AI features comprehensive automated tests covering the entire pipeline:

| Test Module | Coverage Scope | Key Assertions |
| :--- | :--- | :--- |
| `tests/test_db2_connection.py` | IBM Db2 connector, connection pooling, table existence, schema validation | Live Db2 / SQLite fallback connectivity, CRUD operations |
| `tests/test_detection.py` | 6 deterministic threat detection rules | Threshold triggers, event aggregation, sliding time-window logic |
| `tests/test_risk.py` | 4-factor risk scoring engine | 0–100 mathematical bounds, transparent factor calculation, severity buckets |
| `tests/test_workflow.py` | LangGraph StateGraph orchestration | Node transitions, state persistence, interrupt before sensitive action |
| `tests/test_api.py` | FastAPI REST endpoints | HTTP status codes, schema validation, incident lifecycle |

---

## 2. Running Automated Tests

Run the full test suite with `pytest`:

```bash
# From submissions/db2sentinel-ai:
pytest tests/ -v
```

### Running with Code Coverage:
```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

### Expected Output:
```text
tests/test_api.py::test_health_endpoint PASSED
tests/test_api.py::test_events_endpoint PASSED
tests/test_api.py::test_alerts_endpoint PASSED
tests/test_api.py::test_incidents_lifecycle PASSED
tests/test_db2_connection.py::test_db_manager_connection PASSED
tests/test_db2_connection.py::test_core_tables_exist PASSED
tests/test_detection.py::test_brute_force_detection PASSED
tests/test_detection.py::test_password_spray_detection PASSED
tests/test_risk.py::test_risk_calculation_bounds PASSED
tests/test_risk.py::test_critical_risk_factors PASSED
tests/test_workflow.py::test_langgraph_workflow_execution PASSED
============================== 11 passed in 4.50s ==============================
```

---

## 3. End-to-End Simulation Scenarios

You can execute end-to-end simulation scripts without needing to launch the frontend:

### Scenario A: Credential Brute Force & Privilege Abuse
Run the interactive CLI simulation:
```bash
python scripts/run_demo.py
```
This script executes the complete sequence:
1. Injects 5 failed login events (`SQL30082N` RC 24) from IP `198.51.100.42`.
2. Injects an unauthorized schema drop statement.
3. Invokes `DetectionService.evaluate_events()`, triggering `RULE_BRUTE_FORCE`.
4. Creates high-severity Incident `INC-2026-001`.
5. Initiates the **LangGraph 6-Node Workflow**:
   - `Detection Agent` -> `Evidence Agent` -> `Threat Intel Agent` -> `Risk Agent` -> `Response Agent` -> `Report Agent`.
6. Enforces **Human-in-the-Loop Approval Gate** requiring DBA review.
7. Simulates reviewer sign-off and records cryptographic audit record.

---

## 4. Submission Validation Check

Before submitting to the hackathon repository, verify that your project passes all official checks defined by the organizers:

```bash
# From repository root:
python scripts/validate_submission.py submissions/db2sentinel-ai
```

The validator confirms:
- [x] Project slug matches folder name (`db2sentinel-ai`)
- [x] All 4 mandatory files exist and are non-empty (`README.md`, `architecture.md`, `submission.json`, `.env.example`)
- [x] JSON syntax in `submission.json` is valid against official schema
- [x] No sensitive files (`.env`, private keys) are present in the directory
