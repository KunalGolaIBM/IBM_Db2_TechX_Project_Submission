"""
Db2 Copilot Engine:
Coordinates Text-to-SQL generation (Groq llama-3.3-70b-versatile),
SQL Security Validation, Db2 Relational Query Execution,
Python Deterministic Policy Window Computation,
Db2 Vector Policy Retrieval, Verdict Synthesis via Groq, and Audit Logging.
"""
import os
import sys
import re
import json
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db import get_connection, execute_query, execute_non_query
from src.sql_validator import validate_sql, clean_sql
from src.policy_retriever import retrieve_policies
import ibm_db

load_dotenv()

DB_SCHEMA_PROMPT = """
You are a SQL expert for IBM Db2. Generate ONLY a single read-only SQL SELECT statement to answer the user request.
Do NOT include markdown, explanations, or multiple queries.

Available Tables and Schema in Db2:
1. CUSTOMERS (customer_id INT, name VARCHAR(100), email VARCHAR(100), tier VARCHAR(20) ['Standard','Gold','Platinum'], created_at DATE)
2. ORDERS (order_id INT, customer_id INT, order_date DATE, delivery_date DATE, status VARCHAR(30), item_name VARCHAR(120), item_category VARCHAR(50), item_price DECIMAL(10,2), shipping_fee DECIMAL(10,2), total_amount DECIMAL(10,2))
3. PAYMENTS (payment_id INT, order_id INT, payment_method VARCHAR(30), payment_status VARCHAR(20), amount DECIMAL(10,2), transaction_time TIMESTAMP)
4. REFUNDS (refund_id INT, order_id INT, amount DECIMAL(10,2), reason VARCHAR(200), status VARCHAR(20), requested_at DATE, processed_at DATE)

Guidelines:
- Return ONLY the raw SQL query.
- Use uppercase table and column names.
- When querying dispute or order details for an order, ALWAYS SELECT the full set of fact columns:
  O.ORDER_ID, C.NAME, C.TIER, O.ITEM_NAME, O.ITEM_CATEGORY, O.TOTAL_AMOUNT, O.ORDER_DATE, O.DELIVERY_DATE, R.REQUESTED_AT, R.REASON, R.AMOUNT AS REFUND_AMOUNT, R.STATUS AS REFUND_STATUS
  JOIN ORDERS O, CUSTOMERS C, and LEFT JOIN REFUNDS R ON O.ORDER_ID = R.ORDER_ID.
- When querying aggregations (e.g. customers with multiple refunds), group by customer and order/list as needed.
- Do NOT use comments.
"""


def get_groq_client():
    """Initialize Groq client. Raises RuntimeError if GROQ_API_KEY is missing."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing from environment. Please set your GROQ_API_KEY in .env.")
    try:
        from groq import Groq
        return Groq(api_key=api_key)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Groq client: {e}")


def resolve_groq_model(client) -> str:
    """Resolve desired model or choose top available LLM on user's Groq account."""
    configured = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    try:
        avail = [m.id for m in client.models.list().data]
        if configured in avail:
            return configured
        # Candidate preferred models
        for candidate in ("llama-3.3-70b-versatile", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"):
            if candidate in avail:
                return candidate
        chat_models = [m for m in avail if "whisper" not in m and "guard" not in m and "orpheus" not in m]
        if chat_models:
            return chat_models[0]
    except Exception:
        pass
    return configured


def generate_sql_from_question(question: str) -> str:
    """
    Translate natural language dispute question to SQL query strictly using Groq.
    Raises RuntimeError if GROQ_API_KEY is missing or the call fails.
    """
    cleaned_input = clean_sql(question)
    first_token = cleaned_input.split()[0].upper() if cleaned_input.split() else ""

    # If the user passed a direct SQL statement (e.g. during a security test), pass it directly to the validator
    if first_token in ("SELECT", "WITH", "DELETE", "DROP", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "CREATE"):
        return cleaned_input

    # Must invoke Groq API (no canned fallback)
    client = get_groq_client()
    model = resolve_groq_model(client)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": DB_SCHEMA_PROMPT},
                {"role": "user", "content": f"Generate SQL query for question: {question}"},
            ],
            temperature=0.1,
            max_tokens=2048,
        )
        raw_sql = response.choices[0].message.content.strip()
        return raw_sql
    except Exception as e:
        raise RuntimeError(f"Groq Text-to-SQL API call failed: {e}")


def parse_date(val: Any) -> Optional[date]:
    """Parse various date formats into a datetime.date object."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except Exception:
            pass
    return None


def compute_policy_verdict_facts(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Compute dispute facts strictly in Python (not the LLM):
    1. Days between delivery date and dispute requested_at date.
    2. Applicable policy window (7 days for damaged/defective, 14 days electronics, 30 days standard).
    3. VIP exception rules (Gold/Platinum 60-day window, instant refund for claims <= $100).
    4. Deterministic decision (APPROVED / DENIED) and exact rule citation.
    """
    computed_facts = []

    for row in data:
        deliv_dt = parse_date(row.get("delivery_date"))
        req_dt = (
            parse_date(row.get("requested_at"))
            or parse_date(row.get("dispute_date"))
            or parse_date(row.get("request_date"))
            or parse_date(row.get("order_date"))
        )

        # Skip rows without individual dispute context (e.g. aggregate queries)
        if not deliv_dt and not row.get("order_id"):
            continue

        tier = str(row.get("tier", "Standard")).capitalize()
        is_vip = tier in ("Gold", "Platinum")
        cat = str(row.get("item_category", "General"))
        reason = str(row.get("reason", "")).lower()
        amount = float(row.get("total_amount") or row.get("refund_amount") or row.get("amount") or 0.0)
        item_name = str(row.get("item_name", "Item"))
        order_id = row.get("order_id")

        days_elapsed = (req_dt - deliv_dt).days if (deliv_dt and req_dt) else None

        is_damaged_defective = any(
            w in reason for w in ("damaged", "defective", "broken", "flicker", "wrong", "spoiled", "crushed", "squashed")
        )

        fact = {
            "order_id": order_id,
            "customer_name": row.get("name", "Customer"),
            "customer_tier": tier,
            "is_vip": is_vip,
            "item_name": item_name,
            "item_category": cat,
            "claim_amount": amount,
            "dispute_reason": row.get("reason", "Customer dispute"),
            "delivery_date": str(deliv_dt) if deliv_dt else "N/A",
            "dispute_date": str(req_dt) if req_dt else "N/A",
            "days_elapsed": days_elapsed,
        }

        # Policy Rule Evaluation in Python
        if is_vip and amount <= 100.0:
            fact["decision"] = "APPROVED"
            fact["applicable_window_days"] = 60
            fact["applied_policy"] = "Policy #4 (VIP & Loyalty Privileges)"
            fact["justification"] = (
                f"Customer holds {tier} VIP loyalty status. Qualified for automatic instant courtesy refund "
                f"for claims under $100 (${amount:.2f} for {item_name}) without return requirement."
            )
        elif is_vip:
            fact["applicable_window_days"] = 60
            fact["applied_policy"] = "Policy #4 (VIP & Loyalty Privileges)"
            if days_elapsed is not None and days_elapsed <= 60:
                fact["decision"] = "APPROVED"
                fact["justification"] = (
                    f"Customer holds {tier} VIP loyalty status granting an extended 60-day return window. "
                    f"Dispute filed in {days_elapsed} days ({days_elapsed}d <= 60d allowance). Full refund approved."
                )
            else:
                fact["decision"] = "DENIED"
                diff = f" by {days_elapsed - 60} days" if days_elapsed is not None else ""
                fact["justification"] = (
                    f"Customer holds {tier} VIP status with 60-day window, but dispute was submitted {days_elapsed} "
                    f"days after delivery, exceeding the 60-day limit{diff}."
                )
        elif is_damaged_defective:
            fact["applicable_window_days"] = 7
            fact["applied_policy"] = "Policy #3 (Damaged, Defective, or Wrong Items)"
            if days_elapsed is not None and days_elapsed <= 7:
                fact["decision"] = "APPROVED"
                fact["justification"] = (
                    f"Dispute claim filed {days_elapsed} days after delivery, within the mandatory 7-day damaged/defective "
                    f"goods window ({days_elapsed}d <= 7d). Entitled to 100% full refund including shipping."
                )
            else:
                fact["decision"] = "DENIED"
                diff = f" by {days_elapsed - 7} days" if days_elapsed is not None else ""
                fact["justification"] = (
                    f"Dispute filed {days_elapsed} days after delivery, exceeding the strict 7-day damaged goods window{diff}."
                )
        elif cat == "Electronics":
            fact["applicable_window_days"] = 14
            fact["applied_policy"] = "Policy #2 (Electronics Policy)"
            if days_elapsed is not None and days_elapsed <= 14:
                fact["decision"] = "APPROVED"
                fact["justification"] = (
                    f"Electronics return filed {days_elapsed} days after delivery, within the 14-day window "
                    f"({days_elapsed}d <= 14d; subject to 10% restocking fee if opened)."
                )
            else:
                fact["decision"] = "DENIED"
                diff = f" by {days_elapsed - 14} days" if days_elapsed is not None else ""
                fact["justification"] = (
                    f"Electronics return filed {days_elapsed} days after delivery, exceeding the 14-day limit{diff}."
                )
        elif cat == "Perishables":
            fact["applicable_window_days"] = 0
            fact["applied_policy"] = "Policy #2 (Electronics and Perishables Policy)"
            fact["decision"] = "DENIED"
            fact["justification"] = (
                "Perishable goods and opened food items are strictly non-refundable per Policy #2 unless verified "
                "spoiled upon delivery."
            )
        else:
            fact["applicable_window_days"] = 30
            fact["applied_policy"] = "Policy #1 (Standard Return and Refund Window)"
            if days_elapsed is not None and days_elapsed <= 30:
                fact["decision"] = "APPROVED"
                fact["justification"] = (
                    f"General merchandise return filed {days_elapsed} days after delivery, within the 30-day limit "
                    f"({days_elapsed}d <= 30d). Full refund credited to original payment method."
                )
            else:
                fact["decision"] = "DENIED"
                diff = f" by {days_elapsed - 30} days" if days_elapsed is not None else ""
                fact["justification"] = (
                    f"Return filed {days_elapsed} days after delivery, exceeding the standard 30-day return window{diff}."
                )

        computed_facts.append(fact)

    return computed_facts


def synthesize_verdict(
    question: str,
    data: List[Dict[str, Any]],
    policies: List[Dict[str, Any]],
    computed_facts: List[Dict[str, Any]],
) -> str:
    """
    Synthesize final verdict strictly using Groq llama-3.3-70b-versatile.
    Passes computed policy facts, Db2 relational records, and vector-matched policies.
    Raises RuntimeError if GROQ_API_KEY is missing or the call fails.
    """
    client = get_groq_client()
    model = resolve_groq_model(client)

    policy_context = "\n".join(
        [f"- Policy #{p['policy_id']} '{p['policy_title']}' ({p['category']}): {p['content']}" for p in policies]
    )
    data_context = json.dumps(data, indent=2, default=str)
    facts_context = json.dumps(computed_facts, indent=2, default=str)

    prompt = f"""
You are the IBM Db2 Copilot refund-dispute assistant for an e-commerce platform.
Evaluate the customer dispute or query using the computed facts, database records, and store refund policies.

User Query:
{question}

Python Pre-Computed Dispute & Policy Facts (Authoritative calculations):
{facts_context}

Retrieved Db2 Relational Records:
{data_context}

Db2 Vector-Retrieved Store Policies:
{policy_context}

Instructions:
1. If the query asks an analytical or aggregated question (e.g., 'Which customers have more than one refund?'), answer directly, clearly listing the customers, order IDs, and reasons from the database records.
2. If the query is an individual refund dispute decision:
   - State the **VERDICT** (APPROVED or DENIED). You MUST respect the decision computed in the Python facts.
   - Detail the **REASONING**: Explicitly quote the computed elapsed days (e.g. '4 days elapsed') versus the policy allowance ('7-day window'), customer tier, item category, and the specific policy title cited.
   - State the **ACTION / NEXT STEPS** for customer support.
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2048,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"Groq Verdict Generation API call failed: {e}")


def log_audit(question: str, sql: str, status: str, verdict: str):
    """Persist query execution details to QUERY_AUDIT table in Db2."""
    conn = None
    try:
        conn = get_connection()
        q_clean = question[:990].replace("'", "''")
        s_clean = sql[:1990].replace("'", "''")
        stat_clean = status[:48].replace("'", "''")
        v_clean = verdict[:7900].replace("'", "''")

        insert_sql = (
            f"INSERT INTO QUERY_AUDIT (question, generated_sql, sql_status, verdict) "
            f"VALUES ('{q_clean}', '{s_clean}', '{stat_clean}', '{v_clean}')"
        )
        ibm_db.exec_immediate(conn, insert_sql)
    except Exception as e:
        print(f"Failed to log audit in Db2: {e}")
    finally:
        if conn:
            ibm_db.close(conn)


def process_dispute_query(question: str) -> Dict[str, Any]:
    """
    Full End-to-End Copilot Execution Pipeline:
    1. Text-to-SQL (Groq llama-3.3-70b-versatile; fails clearly if API key missing)
    2. SQL Security Validation (AST check, single SELECT, allow-list)
    3. Db2 Relational Query Execution
    4. Python Deterministic Date & Policy Window Computation
    5. Db2 Vector Distance Policy Retrieval (fastembed)
    6. Verdict Synthesis via Groq (fails clearly if API key missing)
    7. Db2 Audit Logging
    """
    result = {
        "question": question,
        "sql": "",
        "sql_valid": False,
        "sql_error": "",
        "data": [],
        "computed_facts": [],
        "policies": [],
        "verdict": "",
        "status": "ERROR",
    }

    # Step 1: Generate SQL via Groq (or detect direct SQL injection for testing)
    try:
        raw_sql = generate_sql_from_question(question)
        result["sql"] = raw_sql
    except Exception as e:
        result["status"] = "GROQ_ERROR"
        result["verdict"] = f"Groq LLM Error: {e}"
        log_audit(question, "", "GROQ_ERROR", result["verdict"])
        return result

    # Step 2: Validate SQL Security
    is_valid, err_msg, cleaned_sql = validate_sql(raw_sql)
    result["sql_valid"] = is_valid
    result["sql_error"] = err_msg
    result["sql"] = cleaned_sql or raw_sql

    if not is_valid:
        result["verdict"] = f"SECURITY ALERT: Query rejected by validator: {err_msg}"
        result["status"] = "REJECTED"
        log_audit(question, raw_sql, "REJECTED", result["verdict"])
        return result

    # Step 3: Execute SQL on Db2
    conn = None
    try:
        conn = get_connection()
        rows = execute_query(conn, cleaned_sql)
        result["data"] = rows
        result["status"] = "EXECUTED"
    except Exception as e:
        result["sql_error"] = f"Db2 SQL Execution Error: {e}"
        result["status"] = "SQL_ERROR"
        result["verdict"] = f"Unable to fetch data from Db2: {e}"
        log_audit(question, cleaned_sql, "SQL_ERROR", result["verdict"])
        return result
    finally:
        if conn:
            ibm_db.close(conn)

    # Step 4: Deterministic Policy Window Computation in Python
    computed_facts = compute_policy_verdict_facts(result["data"])
    result["computed_facts"] = computed_facts

    # Step 5: Vector Retrieve Policies
    policies = retrieve_policies(question, top_k=2)
    result["policies"] = policies

    # Step 6: Synthesize Combined Verdict via Groq
    try:
        verdict = synthesize_verdict(question, result["data"], policies, computed_facts)
        result["verdict"] = verdict
    except Exception as e:
        result["status"] = "GROQ_ERROR"
        result["verdict"] = f"Groq Verdict Generation Error: {e}"
        log_audit(question, cleaned_sql, "GROQ_ERROR", result["verdict"])
        return result

    # Step 7: Audit Log to Db2
    log_audit(question, cleaned_sql, "EXECUTED", verdict)

    return result


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Db2 Copilot Engine")
    print("=" * 60)
    test_q = "Order 101 has a refund request. Check customer tier and dispute details, then decide."
    res = process_dispute_query(test_q)
    print(f"SQL: {res['sql']}")
    print(f"Status: {res['status']}")
    print(f"Verdict:\n{res['verdict']}")
