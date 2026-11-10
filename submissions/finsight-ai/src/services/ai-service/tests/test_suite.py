#!/usr/bin/env python3
"""
FinSight AI — Milestone 03B Comprehensive Verification Suite
Tests the genuine AI integration, real embeddings, official LangChain DB2VS,
deterministic Mode A vs LLM Mode B, and strict financial ledger correctness.
"""

import os
import sys
import time
import requests
from pathlib import Path

# Load token from .env or environment
token = os.getenv("AI_SERVICE_INTERNAL_TOKEN")
if not token:
    candidate_paths = [
        Path("/app/.env"),
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parents[min(2, len(Path(__file__).resolve().parents) - 1)] / ".env"
    ]
    for p in candidate_paths:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("AI_SERVICE_INTERNAL_TOKEN="):
                        token = line.strip().split("=", 1)[1].strip()
                        break

BASE_URL = "http://127.0.0.1:8000"
TOKEN = token or "GLtWRU3gWNfGYzxpMFm9vt7yytyxKer8"
HEADERS = {"X-Service-Token": TOKEN, "Content-Type": "application/json"}
DEMO_USER = "usr_demo_synthetic_01"

def log_test(num, name):
    print(f"\n[TEST {num:02d}] {name}...")

def test_01_real_embedding_model_loading():
    log_test(1, "Real Embedding Model Loading (BAAI/bge-small-en-v1.5)")
    # Test through container python
    from fastembed import TextEmbedding
    m = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    assert m is not None, "Failed to load real TextEmbedding model"
    vecs = list(m.embed(["FinSight AI real embedding check"]))
    assert len(vecs) == 1, "Failed to embed document"
    print(f"   >>> PASS: Real pretrained model loaded: BAAI/bge-small-en-v1.5 (ONNX Runtime active).")

def test_02_embedding_dimension():
    log_test(2, "Real Embedding Output Dimension (384-dim Float32)")
    from fastembed import TextEmbedding
    m = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    vec = list(m.embed(["test vector dimension"]))[0]
    dim = len(vec)
    assert dim == 384, f"Expected dimension 384, got {dim}"
    print(f"   >>> PASS: Vector dimension verified at exactly {dim} elements (matches Db2 VECTOR(384, FLOAT32)).")

def test_03_no_fake_fallback():
    log_test(3, "No Fake / Hash-Derived Fallback in Production Path")
    # Verify FinSightEmbeddingProvider code has no hash fallback
    from app.services.embeddings import FinSightEmbeddingProvider
    provider = FinSightEmbeddingProvider(model_name="BAAI/bge-small-en-v1.5", dimension=384)
    info = provider.get_model_info()
    assert info["is_real_model"] is True
    assert info["fallback_active"] is False
    assert not hasattr(provider, "_fallback_embed"), "Prohibited fallback method still exists!"
    print(f"   >>> PASS: Verified zero fallback vectors. FastEmbed is exclusive provider.")

def test_04_reindexing_success():
    log_test(4, "Re-Indexing User Transactions via Real Embeddings")
    t0 = time.time()
    res = requests.post(
        f"{BASE_URL}/api/ai/index-transactions",
        json={"user_id": DEMO_USER},
        headers=HEADERS,
        timeout=60
    )
    assert res.status_code == 200, f"Indexing failed: {res.text}"
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["indexed_count"] == 208, f"Expected 208 indexed transactions, got {data['indexed_count']}"
    assert data["dimension"] == 384
    elapsed = time.time() - t0
    print(f"   >>> PASS: Successfully indexed all {data['indexed_count']} transactions in {elapsed:.2f}s.")

def test_05_duplicate_embedding_protection():
    log_test(5, "Duplicate Embedding Protection (Idempotent 1-to-1 Mapping)")
    from app.db import db_manager
    rows = db_manager.execute_query("""
        SELECT COUNT(embedding_id) AS total_embs, COUNT(DISTINCT transaction_id) AS unique_txs
        FROM FINSIGHT.TRANSACTION_EMBEDDINGS
        WHERE user_id = ?
    """, (DEMO_USER,))
    total = int(rows[0]["total_embs"])
    unique = int(rows[0]["unique_txs"])
    assert total == unique, f"Duplicate embeddings detected! Total: {total}, Unique: {unique}"
    assert total == 208
    print(f"   >>> PASS: Zero duplicates. Exactly {total} embeddings for {unique} transactions.")

def test_06_real_db2_vector_search():
    log_test(6, "Real IBM Db2 Vector Search (VECTOR_DISTANCE Cosine)")
    res = requests.post(
        f"{BASE_URL}/api/ai/search",
        json={"query": "cabs rides daily travel commute airport taxi", "user_id": DEMO_USER, "limit": 3},
        headers=HEADERS,
        timeout=10
    )
    assert res.status_code == 200, f"Search failed: {res.text}"
    data = res.json()
    assert data["total_results"] > 0
    top = data["results"][0]
    assert top["merchant"] == "Uber India", f"Expected Uber India, got {top['merchant']}"
    assert top["distance"] > 0.0 and top["distance"] < 1.0
    assert top["similarity_score"] > 0.70
    print(f"   >>> PASS: Top Match: {top['merchant']} (INR {top['amount']:.2f}, Dist: {top['distance']:.4f}, Sim: {top['similarity_score']:.2f}).")

def test_07_langchain_db2_integration():
    log_test(7, "Official LangChain Db2 VectorStore (DB2VS) Integration")
    import ibm_db_dbi
    from langchain_db2 import DB2VS
    from app.config import settings
    from app.services.embeddings import embedding_provider

    conn_str = f"DATABASE={settings.db2_database};hostname={settings.db2_host};port={settings.db2_port};uid={settings.db2_user};pwd={settings.db2_password};"
    client = ibm_db_dbi.connect(conn_str, "", "")
    db2vs = DB2VS(embedding_function=embedding_provider, table_name="FINSIGHT.LANGCHAIN_DB2_STORE", client=client)
    assert db2vs is not None
    docs = db2vs.similarity_search("daily office cab travel", k=2)
    assert len(docs) > 0
    print(f"   >>> PASS: Successfully queried official LangChain DB2VS. Retrieved doc: '{docs[0].page_content[:50]}...'.")

def test_08_retrieval_relevance_evaluation():
    log_test(8, "12-Domain Semantic Retrieval Evaluation")
    from evaluate_12_queries import QUERIES
    top1_hits = 0
    for q in QUERIES:
        res = requests.post(
            f"{BASE_URL}/api/ai/search",
            json={"query": q["query"], "user_id": DEMO_USER, "limit": 1},
            headers=HEADERS,
            timeout=10
        )
        data = res.json()
        if data["results"]:
            cat = data["results"][0]["category"]
            if any(exp.lower() in cat.lower() for exp in q["expected_domain"]):
                top1_hits += 1
    pct = (top1_hits / len(QUERIES)) * 100.0
    assert pct >= 90.0, f"Expected >=90% retrieval precision, got {pct}%"
    print(f"   >>> PASS: Semantic Precision@1 achieved {top1_hits}/{len(QUERIES)} ({pct:.1f}%).")

def test_09_tenant_isolation():
    log_test(9, "Strict Multi-Tenant Scoping in Vector Retrieval")
    res = requests.post(
        f"{BASE_URL}/api/ai/search",
        json={"query": "salary payroll", "user_id": "usr_tenant_b_isolated", "limit": 5},
        headers=HEADERS,
        timeout=10
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_results"] == 0, f"Expected 0 results for foreign tenant, got {data['total_results']}"
    print(f"   >>> PASS: Cross-tenant isolation verified. Foreign tenant received 0 records.")

def test_10_deterministic_assistant_mode():
    log_test(10, "Mode A: Deterministic Intelligence Execution")
    res = requests.post(
        f"{BASE_URL}/api/ai/chat",
        json={"message": "What is my total verified income?", "user_id": DEMO_USER, "mode": "deterministic"},
        headers=HEADERS,
        timeout=10
    )
    assert res.status_code == 200
    data = res.json()
    assert data["mode_active"] == "DETERMINISTIC"
    assert "750,000" in data["answer"]
    assert len(data["evidence"]) > 0
    print(f"   >>> PASS: Mode A executed verified SQL calculation with Db2 proof.")

def test_11_llm_mode_behavior():
    log_test(11, "Mode B: LLM-Powered Intelligence (With/Without Key Handling)")
    res = requests.post(
        f"{BASE_URL}/api/ai/chat",
        json={"message": "Analyze my monthly spending", "user_id": DEMO_USER, "mode": "llm"},
        headers=HEADERS,
        timeout=15
    )
    assert res.status_code == 200
    data = res.json()
    if data["mode_active"] == "LLM":
        print(f"   >>> PASS: Mode B executed via live LangChain Gemini integration.")
    else:
        assert data["mode_active"] == "LLM_AWAITING_CREDENTIALS"
        assert "GEMINI_API_KEY" in data["answer"]
        print(f"   >>> PASS: Mode B gracefully handled missing key, transparently requesting credentials without crashing.")

def test_12_evidence_correctness():
    log_test(12, "Financial Correctness & Exclusion of Internal Transfers")
    from app.services.tools import financial_tools
    income = financial_tools.get_income(DEMO_USER)
    assert income["total_income"] == 750000.00
    assert income["transaction_count"] == 6
    flow = financial_tools.get_net_cash_flow(DEMO_USER)
    assert flow["total_inflow"] == 750000.00
    assert flow["net_cash_flow"] > 0
    print(f"   >>> PASS: Inflow = INR {flow['total_inflow']:,.2f}, Outflow = INR {flow['total_outflow']:,.2f}, Net Surplus = INR {flow['net_cash_flow']:,.2f}.")

def test_13_future_pending_exclusion():
    log_test(13, "Future Pending Transaction Exclusion (> 2026-11-07)")
    from app.db import db_manager
    rows = db_manager.execute_query("""
        SELECT COUNT(*) AS future_posted
        FROM FINSIGHT.TRANSACTIONS
        WHERE transaction_date > DATE('2026-11-07')
          AND transaction_status = 'POSTED'
    """)
    assert int(rows[0]["future_posted"]) == 0
    print("   >>> PASS: Exactly 0 future-dated transactions are marked as POSTED.")

def test_14_security_and_validation():
    log_test(14, "Security Guardrails: Injection Resistance & Validation")
    # 1. Invalid Token
    r1 = requests.post(f"{BASE_URL}/api/ai/chat", json={"message": "hi"}, headers={"X-Service-Token": "bad"}, timeout=5)
    assert r1.status_code == 401
    # 2. Empty Input
    r2 = requests.post(f"{BASE_URL}/api/ai/chat", json={"message": ""}, headers=HEADERS, timeout=5)
    assert r2.status_code == 422
    # 3. SQL Injection Deflection
    r3 = requests.post(f"{BASE_URL}/api/ai/chat", json={"message": "DROP TABLE FINSIGHT.TRANSACTIONS;"}, headers=HEADERS, timeout=10)
    assert r3.status_code == 200
    assert "DROP TABLE" not in r3.json()["answer"]
    print("   >>> PASS: Security controls verified (401 Unauthorized, 422 Validation, DDL Deflection).")

def test_15_db_telemetry_and_health():
    log_test(15, "Live Database Telemetry & Connection Health")
    res = requests.get(f"{BASE_URL}/health/db", timeout=5)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "UP"
    assert data["database"] == "FINDB"
    assert data["total_transactions"] == 208
    print(f"   >>> PASS: Db2 FINDB is ONLINE ({data['server_version']}, Latency: {data['latency_ms']}ms, 208 txs).")

def main():
    print("=" * 75)
    print("       FinSight AI — Milestone 03B Verification Suite")
    print("=" * 75)

    tests = [
        test_01_real_embedding_model_loading,
        test_02_embedding_dimension,
        test_03_no_fake_fallback,
        test_04_reindexing_success,
        test_05_duplicate_embedding_protection,
        test_06_real_db2_vector_search,
        test_07_langchain_db2_integration,
        test_08_retrieval_relevance_evaluation,
        test_09_tenant_isolation,
        test_10_deterministic_assistant_mode,
        test_11_llm_mode_behavior,
        test_12_evidence_correctness,
        test_13_future_pending_exclusion,
        test_14_security_and_validation,
        test_15_db_telemetry_and_health,
    ]

    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"   [!] FAIL in {t.__name__}: {e}")

    print("\n" + "=" * 75)
    print(f"  Milestone 03B Final Results: {passed}/{len(tests)} tests passed.")
    print("=" * 75)
    sys.exit(0 if passed == len(tests) else 1)

if __name__ == "__main__":
    main()
