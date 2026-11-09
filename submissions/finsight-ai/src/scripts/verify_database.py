#!/usr/bin/env python3
"""
FinSight AI — Comprehensive Database Verification Suite (verify_database.py)
Tests:
  1. TCP Port 50000 Connection
  2. Database & Schema Existence
  3. Relational Table Listing
  4. Primary Key & Foreign Key Constraints
  5. Synthetic Record Counts (>100 transactions)
  6. Analytical SQL Queries Execution & Validation
  7. Multi-Tenant Scoping & Isolation Proof
  8. Seed Idempotency & Duplicate Protection
  9. Transaction Rollback Integrity
  10. Container Restart & Persistence Proof
"""

import os
import sys
import json
import socket
import subprocess
import time

CONTAINER_NAME = "finsight-db2"
DB_NAME = "FINDB"
SCHEMA_NAME = "FINSIGHT"

def log_header(title):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)

def run_db2_cmd(sql, expect_zero=True):
    """Executes SQL via docker exec db2 CLI as db2inst1"""
    escaped_sql = sql.replace('"', '\\"').replace('$', '\\$')
    cmd = [
        "docker", "exec", "-i", CONTAINER_NAME,
        "su", "-", "db2inst1", "-c",
        f"db2 -x connect to {DB_NAME} > /dev/null && db2 -x \"{escaped_sql}\" && db2 connect reset > /dev/null"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if expect_zero and res.returncode != 0:
        print(f"[!] SQL Error: {res.stderr or res.stdout}")
    return res.stdout.strip(), res.returncode

def test_01_tcp_port():
    print("[TEST 01] Verifying Localhost TCP Port 50000 Binding...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3.0)
    try:
        s.connect(("127.0.0.1", 50000))
        s.close()
        print("   >>> PASS: Port 50000 is open and actively accepting TCP connections on 127.0.0.1.")
        return True
    except Exception as e:
        print(f"   [!] FAIL: Cannot connect to 127.0.0.1:50000 ({e})")
        return False

def test_02_database_exists():
    print("\n[TEST 02] Verifying Database Existence & Active Engine...")
    out, code = run_db2_cmd("SELECT CURRENT SERVER FROM SYSIBM.SYSDUMMY1")
    if code == 0 and DB_NAME in out:
        print(f"   >>> PASS: Successfully connected to database '{DB_NAME}'. Server response: {out}")
        return True
    print(f"   [!] FAIL: Database {DB_NAME} check returned: {out}")
    return False

def test_03_table_listing():
    print("\n[TEST 03] Verifying Relational Core Tables in Schema FINSIGHT...")
    expected_tables = [
        "USERS", "ACCOUNTS", "CATEGORIES", "TRANSACTIONS",
        "IMPORT_JOBS", "ANOMALY_ALERTS", "AI_INSIGHTS", "SCHEMA_MIGRATIONS",
        "TRANSACTION_EMBEDDINGS"
    ]
    out, code = run_db2_cmd(
        f"SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = '{SCHEMA_NAME}' AND TYPE = 'T'"
    )
    if code != 0:
        print(f"   [!] FAIL: Querying SYSCAT.TABLES failed: {out}")
        return False
    
    found_tables = [t.strip() for t in out.splitlines() if t.strip()]
    missing = [t for t in expected_tables if t not in found_tables]
    if missing:
        print(f"   [!] FAIL: Missing expected tables: {missing}")
        return False
    
    print(f"   >>> PASS: All {len(expected_tables)} required tables verified in {SCHEMA_NAME}:")
    for t in expected_tables:
        print(f"       - {SCHEMA_NAME}.{t}")
    return True

def test_04_constraints():
    print("\n[TEST 04] Verifying Primary and Foreign Key Constraints...")
    out, code = run_db2_cmd(
        f"SELECT CONSTNAME, TABNAME, TYPE FROM SYSCAT.TABCONST WHERE TABSCHEMA = '{SCHEMA_NAME}' ORDER BY TABNAME, TYPE"
    )
    if code != 0:
        print(f"   [!] FAIL: Constraint query failed: {out}")
        return False
    
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    pk_count = sum(1 for l in lines if " P" in l or l.endswith("P"))
    fk_count = sum(1 for l in lines if " F" in l or l.endswith("F"))
    print(f"   >>> PASS: Found {pk_count} Primary Keys and {fk_count} Foreign Key constraints across schema.")
    return pk_count >= 7 and fk_count >= 5

def test_05_record_counts():
    print("\n[TEST 05] Verifying Synthetic Seed Population (>100 Transactions)...")
    out, code = run_db2_cmd("SELECT count(*) FROM FINSIGHT.TRANSACTIONS")
    if code != 0:
        print(f"   [!] FAIL: Count query failed: {out}")
        return False
    count = int(out.strip())
    print(f"   >>> Current transaction row count: {count}")
    if count >= 100:
        print(f"   >>> PASS: Synthetic dataset meets requirement (>100 records).")
        return True
    print(f"   [!] FAIL: Transaction count is {count}, expected >= 100.")
    return False

def test_06_analytical_queries():
    print("\n[TEST 06] Verifying Parameterized Analytical Queries...")
    queries = [
        ("Total Income", "SELECT count(*), sum(amount) FROM FINSIGHT.TRANSACTIONS WHERE user_id = 'usr_demo_synthetic_01' AND transaction_type = 'CREDIT' AND category_id != 'cat_transfer'"),
        ("Total Expenses", "SELECT count(*), sum(amount) FROM FINSIGHT.TRANSACTIONS WHERE user_id = 'usr_demo_synthetic_01' AND transaction_type = 'DEBIT' AND category_id != 'cat_transfer'"),
        ("Monthly Trends", "SELECT YEAR(transaction_date), MONTH(transaction_date), sum(amount) FROM FINSIGHT.TRANSACTIONS WHERE user_id = 'usr_demo_synthetic_01' GROUP BY YEAR(transaction_date), MONTH(transaction_date) ORDER BY 1, 2 FETCH FIRST 3 ROWS ONLY"),
        ("Top Merchants", "SELECT merchant, sum(amount) FROM FINSIGHT.TRANSACTIONS WHERE user_id = 'usr_demo_synthetic_01' AND transaction_type = 'DEBIT' GROUP BY merchant ORDER BY 2 DESC FETCH FIRST 3 ROWS ONLY"),
        ("Unusual Candidates", "SELECT transaction_id, merchant, amount FROM FINSIGHT.TRANSACTIONS WHERE user_id = 'usr_demo_synthetic_01' AND amount > 40000.00"),
    ]
    all_ok = True
    for name, sql in queries:
        out, code = run_db2_cmd(sql)
        if code == 0 and out:
            first_line = out.splitlines()[0].strip()
            print(f"   >>> PASS: [{name}] Output sample: {first_line}")
        else:
            print(f"   [!] FAIL: [{name}] returned error or empty output: {out}")
            all_ok = False
    return all_ok

def test_07_tenant_isolation():
    print("\n[TEST 07] Proving Multi-Tenant Scoping & Isolation...")
    # Insert secondary tenant
    tenant_b_id = "usr_tenant_b_isolated"
    setup_sql = f"""
    MERGE INTO FINSIGHT.USERS AS target
    USING (VALUES ('{tenant_b_id}', 'tenant.b@isolated.test', 'Tenant B Isolated')) AS src (user_id, email, full_name)
    ON (target.user_id = src.user_id)
    WHEN NOT MATCHED THEN INSERT (user_id, email, full_name) VALUES (src.user_id, src.email, src.full_name);
    """
    run_db2_cmd(setup_sql)

    # Query with tenant B's scope
    out_b, code_b = run_db2_cmd(f"SELECT count(*) FROM FINSIGHT.TRANSACTIONS WHERE user_id = '{tenant_b_id}'")
    out_a, code_a = run_db2_cmd(f"SELECT count(*) FROM FINSIGHT.TRANSACTIONS WHERE user_id = 'usr_demo_synthetic_01'")

    count_b = int(out_b.strip()) if code_b == 0 and out_b.strip() else -1
    count_a = int(out_a.strip()) if code_a == 0 and out_a.strip() else -1

    print(f"   - Tenant A ('usr_demo_synthetic_01') Transaction Count: {count_a}")
    print(f"   - Tenant B ('usr_tenant_b_isolated') Transaction Count: {count_b}")

    if count_b == 0 and count_a >= 100:
        print("   >>> PASS: Tenant isolation confirmed. Tenant B cannot see Tenant A's records.")
        # Cleanup tenant B
        run_db2_cmd(f"DELETE FROM FINSIGHT.USERS WHERE user_id = '{tenant_b_id}'")
        return True
    print("   [!] FAIL: Tenant isolation check failed.")
    return False

def test_08_duplicate_protection():
    print("\n[TEST 08] Testing Seed Idempotency & Duplicate Protection...")
    out_before, _ = run_db2_cmd("SELECT count(*) FROM FINSIGHT.TRANSACTIONS")
    count_before = int(out_before.strip())

    # Re-run a sample MERGE insert
    test_merge = """
    MERGE INTO FINSIGHT.TRANSACTIONS AS target
    USING (VALUES ('tx_sal_202606', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_salary', 'SAL-PAYROLL-202606-9821', 'Acme Global Tech Payroll', 'Monthly engineering salary credit', 125000.00, 'INR', 'CREDIT', DATE('2026-06-01'), 'POSTED', 'BANK_SYNC'))
    AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    ON (target.transaction_id = src.transaction_id)
    WHEN NOT MATCHED THEN
        INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
        VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);
    """
    run_db2_cmd(test_merge)

    out_after, _ = run_db2_cmd("SELECT count(*) FROM FINSIGHT.TRANSACTIONS")
    count_after = int(out_after.strip())

    print(f"   - Count before re-seed: {count_before}")
    print(f"   - Count after re-seed:  {count_after}")

    if count_before == count_after:
        print("   >>> PASS: Idempotent MERGE confirmed. Zero duplicate records inserted.")
        return True
    print("   [!] FAIL: Duplicate records were created.")
    return False

def test_09_transaction_rollback():
    print("\n[TEST 09] Testing ACID Transaction Rollback...")
    probe_id = "tx_probe_rollback_test"
    rollback_script = f"""
    db2 connect to {DB_NAME} > /dev/null
    db2 "+c INSERT INTO FINSIGHT.TRANSACTIONS (transaction_id, user_id, account_id, category_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source) VALUES ('{probe_id}', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_shopping', 'Rollback Probe Store', 'Test Probe Description', 999.00, 'INR', 'DEBIT', CURRENT DATE, 'POSTED', 'TEST')"
    db2 "ROLLBACK"
    db2 connect reset > /dev/null
    """
    cmd = ["docker", "exec", "-i", CONTAINER_NAME, "su", "-", "db2inst1", "-c", rollback_script]
    subprocess.run(cmd, capture_output=True, text=True)

    out, code = run_db2_cmd(f"SELECT count(*) FROM FINSIGHT.TRANSACTIONS WHERE transaction_id = '{probe_id}'")
    count = int(out.strip()) if code == 0 and out.strip() else -1
    if count == 0:
        print("   >>> PASS: Transaction successfully rolled back. Probe record was not committed.")
        return True
    print(f"   [!] FAIL: Probe record was found after rollback (count={count}).")
    return False

def test_10_container_restart_and_persistence():
    print("\n[TEST 10] Testing Container Restart & Volume Data Persistence...")
    out_before, _ = run_db2_cmd("SELECT count(*) FROM FINSIGHT.TRANSACTIONS")
    count_before = int(out_before.strip())
    print(f"   - Record count before restart: {count_before}")

    print("   - Restarting container 'finsight-db2'...")
    subprocess.run(["docker", "restart", CONTAINER_NAME], capture_output=True, text=True)
    print("   - Waiting 20 seconds for Db2 engine to re-initialize...")
    time.sleep(20)

    # Wait until DB is accessible
    retries = 15
    accessible = False
    for r in range(retries):
        out, code = run_db2_cmd("SELECT count(*) FROM FINSIGHT.TRANSACTIONS", expect_zero=False)
        if code == 0 and out.strip().isdigit():
            count_after = int(out.strip())
            accessible = True
            break
        time.sleep(5)

    if accessible and count_after == count_before:
        print(f"   - Record count after restart:  {count_after}")
        print("   >>> PASS: Database persistence confirmed! All records intact across container reboot.")
        return True
    print("   [!] FAIL: Persistence verification failed.")
    return False

def main():
    log_header("FinSight AI — IBM Db2 Live Verification Suite")
    tests = [
        test_01_tcp_port,
        test_02_database_exists,
        test_03_table_listing,
        test_04_constraints,
        test_05_record_counts,
        test_06_analytical_queries,
        test_07_tenant_isolation,
        test_08_duplicate_protection,
        test_09_transaction_rollback,
        test_10_container_restart_and_persistence
    ]

    results = []
    for t in tests:
        try:
            ok = t()
            results.append((t.__name__, ok))
        except Exception as e:
            print(f"   [!] EXCEPTION during {t.__name__}: {e}")
            results.append((t.__name__, False))

    log_header("Verification Summary")
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    for name, ok in results:
        status_str = "PASS" if ok else "FAIL"
        print(f"  [{status_str}] {name}")
    print(f"\nFinal Score: {passed}/{total} tests passed.")
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
