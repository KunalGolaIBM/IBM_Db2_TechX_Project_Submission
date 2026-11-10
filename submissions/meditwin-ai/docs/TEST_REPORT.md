# MediTwin AI — Automated Test Execution Report

**Date of Execution:** 2026-11-10  
**Test Framework:** Pytest 9.1.1  
**Python Runtime:** Python 3.11.9 (win32)  
**Total Tests Executed:** 40  
**Passed:** 40  
**Failed:** 0  
**Errors:** 0  
**Warnings:** 0  
**Execution Duration:** 0.67 seconds  

---

## 1. Summary by Category

| # | Category | Test File | Tests | Status | Execution Notes |
|---|---|---|---|---|---|
| 1 | **Db2 Connection** | `tests/test_01_db2_connection.py` | 3 | ✅ Passed | Validates connection string assembly, disconnected lifecycle state, and unreachable server error handling. |
| 2 | **Schema Initialization** | `tests/test_02_schema_initialization.py` | 3 | ✅ Passed | Verifies `db/schema.sql` syntax, table DDL completeness, constraints (PK, FK, CHECK), and index creation. |
| 3 | **Patient Creation** | `tests/test_03_patient_creation.py` | 2 | ✅ Passed | Verifies synthetic patient models, unique demo code generation, and demo datasets. |
| 4 | **Document Upload Validation** | `tests/test_04_document_upload_validation.py` | 5 | ✅ Passed | Validates PDF/TXT extension filtering, 10MB size ceiling enforcement, and empty file rejection. |
| 5 | **PDF Extraction** | `tests/test_05_pdf_extraction.py` | 3 | ✅ Passed | Validates PyMuPDF page-by-page text parsing, character counts, SHA-256 source hashing, and dispatcher. |
| 6 | **Pydantic Validation** | `tests/test_06_pydantic_validation.py` | 3 | ✅ Passed | Tests `ExtractedObservation` schema, test code normalization to uppercase, and confidence score bounds [0.0, 1.0]. |
| 7 | **Invalid Date Handling** | `tests/test_07_invalid_date_handling.py` | 4 | ✅ Passed | Tests unparseable date handling, missing date review triggers, future date suppression, and alternate date parsing (DD/MM/YYYY). |
| 8 | **Missing Unit Handling** | `tests/test_08_missing_unit_handling.py` | 2 | ✅ Passed | Ensures numeric observations with missing or whitespace-only units flag mandatory human review. |
| 9 | **Human Approval** | `tests/test_09_human_approval.py` | 2 | ✅ Passed | Validates `ReviewDecision` schema, reviewer audit attribution, and numeric/unit corrections. |
| 10 | **Rejected Observation** | `tests/test_10_rejected_observation.py` | 2 | ✅ Passed | Verifies that rejected observations are excluded from timelines and trend analysis. |
| 11 | **Timeline Ordering** | `tests/test_11_timeline_ordering.py` | 2 | ✅ Passed | Validates chronological date ordering (newest first for events) and deterministic difference/percentage calculation. |
| 12 | **Unit Compatibility** | `tests/test_12_unit_compatibility.py` | 1 | ✅ Passed | Confirms that incompatible units (e.g. mg/dL vs mmol/L) block direct numerical comparison. |
| 13 | **Parameterized Query** | `tests/test_13_parameterized_query.py` | 2 | ✅ Passed | Inspects repository code ensuring positional `?` parameter markers and no dynamic user string concatenation. |
| 14 | **SQL Injection Resistance**| `tests/test_14_sql_injection_resistance.py`| 1 | ✅ Passed | Submits malicious SQL payloads (`'; DROP TABLE PATIENT; --`, `' OR 1=1 --`) and verifies safe handling. |
| 15 | **Evidence Retrieval** | `tests/test_15_evidence_retrieval.py` | 2 | ✅ Passed | Validates clinical alias resolution (`haemoglobin` -> `HGB`, `blood sugar` -> `FBS`, `hba1c` -> `HBA1C`). |
| 16 | **Unsupported Question** | `tests/test_16_unsupported_question.py` | 1 | ✅ Passed | Tests non-clinical and unsupported questions, ensuring no hallucinated queries. |
| 17 | **Missing Evidence Response**| `tests/test_17_missing_evidence_response.py`| 1 | ✅ Passed | Tests exact return of *"I could not find sufficient approved records to answer this question."* |
| 18 | **Audit Logging** | `tests/test_18_audit_logging.py` | 1 | ✅ Passed | Tests audit trail creation for uploads, extractions, approvals, rejections, and Q&A interactions. |

---

## 2. Command Output

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\Vipul Mishra\OneDrive\Desktop\HACKATHON UNSTOP
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.14.1, langsmith-0.14.17, asyncio-1.4.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 40 items

tests\test_01_db2_connection.py ...                                      [  7%]
tests\test_02_schema_initialization.py ...                               [ 15%]
tests\test_03_patient_creation.py ..                                     [ 20%]
tests\test_04_document_upload_validation.py .....                        [ 32%]
tests\test_05_pdf_extraction.py ...                                      [ 40%]
tests\test_06_pydantic_validation.py ...                                 [ 47%]
tests\test_07_invalid_date_handling.py ....                              [ 57%]
tests\test_08_missing_unit_handling.py ..                                [ 62%]
tests\test_09_human_approval.py ..                                       [ 67%]
tests\test_10_rejected_observation.py ..                                 [ 72%]
tests\test_11_timeline_ordering.py ..                                    [ 77%]
tests\test_12_unit_compatibility.py .                                    [ 80%]
tests\test_13_parameterized_query.py ..                                  [ 85%]
tests\test_14_sql_injection_resistance.py .                              [ 87%]
tests\test_15_evidence_retrieval.py ..                                   [ 92%]
tests\test_16_unsupported_question.py .                                  [ 95%]
tests\test_17_missing_evidence_response.py .                             [ 97%]
tests\test_18_audit_logging.py .                                         [100%]

============================= 40 passed in 0.67s ==============================
```

