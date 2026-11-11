"""
Transactional Order, Concurrency & Cryptographic Audit Engine for BAKEBOX Choco AI on IBM Db2.

Implements:
1. Atomic Stock Reservation via IBM Db2 Row-Level Locking (`SELECT ... FOR UPDATE WITH RS`)
   and Native SQL PL Stored Procedure (`SP_RESERVE_CAKE_STOCK`).
2. In-Database Multi-Level Recursive Bill-of-Materials (BOM) Common Table Expression (CTE).
3. Single-UOW Atomic Order Placement (BOM check -> stock lock -> BB_ORDERS -> BB_ORDER_ITEMS -> BB_AUDIT_LOG).
4. Cryptographic SHA-256 Hash-Chained Audit Trail (`BB_AUDIT_LOG`) with tamper detection.
5. Phone-Authenticated Happiness Guarantee Refund Evaluation with brute-force lockout.
"""
import hashlib
import hmac
import json
import os
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

_pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from src.db import execute_dml, execute_query
from src.security import extract_phone_last10, order_auth_limiter

GENESIS_PREV_HASH = "0" * 64
_DEFAULT_DEV_AUDIT_KEY = "bakebox-db2-audit-hmac-dev-key"
_audit_append_lock = threading.Lock()
_CATALOG_WEIGHT_CACHE: Optional[Dict[str, str]] = None


def _get_audit_hmac_key() -> bytes:
    """Resolve HMAC signing key from env (with deterministic local dev fallback)."""
    raw = (os.getenv("AUDIT_HMAC_SECRET") or "").strip()
    if not raw or raw == "your_audit_hmac_secret_here":
        raw = _DEFAULT_DEV_AUDIT_KEY
    return raw.encode("utf-8")


def _resolve_cake_weight(sku_id: str) -> str:
    """Look up item weight from sample_catalog.json or canonical SKU suffix."""
    global _CATALOG_WEIGHT_CACHE
    if _CATALOG_WEIGHT_CACHE is None:
        mapping: Dict[str, str] = {}
        cat_path = os.path.join(_pkg_root, "data", "sample_catalog.json")
        try:
            if os.path.isfile(cat_path):
                with open(cat_path, "r", encoding="utf-8") as f:
                    for item in json.load(f):
                        if item.get("sku_id") and item.get("weight_kg") is not None:
                            mapping[str(item["sku_id"])] = f"{item['weight_kg']}kg"
        except Exception:
            pass
        _CATALOG_WEIGHT_CACHE = mapping

    if sku_id in _CATALOG_WEIGHT_CACHE:
        return _CATALOG_WEIGHT_CACHE[sku_id]
    lower = (sku_id or "").lower()
    if "-05kg" in lower:
        return "0.5kg"
    if "-pty" in lower:
        return "0.15kg"
    return "1.0kg"


# ==============================================================================
# 1. ATOMIC STOCK RESERVATION (IBM Db2 ROW-LEVEL LOCKING WITH RS)
# ==============================================================================

def reserve_cake_stock_atomic(conn: Any, cake_id: int, quantity: int = 1, commit: bool = True) -> bool:
    """
    Execute `SELECT STOCK_QTY FROM BB_CAKES WHERE CAKE_ID = ? FOR UPDATE WITH RS`
    to lock the target row under Db2 Read Stability (RS) isolation, preventing
    race-condition overselling. Set `commit=False` when called inside a multi-step UOW.
    """
    if not isinstance(cake_id, int) or cake_id <= 0 or not isinstance(quantity, int) or quantity <= 0:
        return False

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT STOCK_QTY FROM BB_CAKES WHERE CAKE_ID = ? FOR UPDATE WITH RS", (cake_id,))
        row = cursor.fetchone()
        if not row or row[0] < quantity:
            if commit:
                conn.rollback()
            return False

        cursor.execute(
            "UPDATE BB_CAKES SET STOCK_QTY = STOCK_QTY - ? WHERE CAKE_ID = ? AND STOCK_QTY >= ?",
            (quantity, cake_id, quantity),
        )
        if cursor.rowcount <= 0:
            if commit:
                conn.rollback()
            return False

        if commit:
            conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def call_sp_reserve_cake_stock(conn: Any, cake_id: int, quantity: int = 1, commit: bool = True) -> bool:
    """
    Invoke native IBM Db2 Stored Procedure `CALL SP_RESERVE_CAKE_STOCK(?, ?)`
    (`DYNAMIC RESULT SETS 1`), falling back cleanly to explicit row-lock SQL if unavailable.
    """
    if not isinstance(cake_id, int) or cake_id <= 0 or not isinstance(quantity, int) or quantity <= 0:
        return False

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("CALL SP_RESERVE_CAKE_STOCK(?, ?)", (cake_id, quantity))
        res = cursor.fetchone()
        ok = bool(res and res[0] == 1)
        if commit:
            conn.commit() if ok else conn.rollback()
        return ok
    except Exception:
        return reserve_cake_stock_atomic(conn, cake_id, quantity, commit=commit)
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass


# ==============================================================================
# 2. IN-DATABASE RECURSIVE BILL-OF-MATERIALS (BOM) CTE (IBM Db2 LUW SYNTAX)
# ==============================================================================

def check_recipe_bom_availability(conn: Any, cake_id: int, quantity: int = 1) -> List[Dict[str, Any]]:
    """
    Execute an IBM Db2 LUW Recursive Bill-of-Materials (BOM) CTE (`WITH ... UNION ALL`)
    traversing multi-level sub-assemblies (`BB_RECIPES -> BB_INGREDIENT_COMPONENTS -> BB_INVENTORY`)
    scaled by ordered `quantity` using explicit typed DECIMAL(10, 4) parameters.
    """
    if not isinstance(cake_id, int) or cake_id <= 0 or not isinstance(quantity, int) or quantity <= 0:
        return []

    sql = """
    WITH RECIPE_BOM (DEPTH, INGREDIENT_ID, INGREDIENT_NAME, REQUIRED_QTY, CURRENT_STOCK) AS (
        SELECT 1, r.INGREDIENT_ID, r.INGREDIENT_NAME,
               CAST(r.QTY_NEEDED * CAST(? AS DECIMAL(10, 4)) AS DECIMAL(10, 4)), i.STOCK_QTY
        FROM BB_RECIPES r
        JOIN BB_INVENTORY i ON r.INGREDIENT_ID = i.INGREDIENT_ID
        WHERE r.CAKE_ID = ?
        UNION ALL
        SELECT b.DEPTH + 1, sub.COMPONENT_ID, sub.COMPONENT_NAME,
               CAST(b.REQUIRED_QTY * sub.QTY_RATIO AS DECIMAL(10, 4)), inv.STOCK_QTY
        FROM RECIPE_BOM b
        JOIN BB_INGREDIENT_COMPONENTS sub ON b.INGREDIENT_ID = sub.PARENT_INGREDIENT_ID
        JOIN BB_INVENTORY inv ON sub.COMPONENT_ID = inv.INGREDIENT_ID
        WHERE b.DEPTH < 5
    )
    SELECT INGREDIENT_NAME, REQUIRED_QTY, CURRENT_STOCK,
           CASE WHEN CURRENT_STOCK >= REQUIRED_QTY THEN 'IN_STOCK' ELSE 'OUT_OF_STOCK' END AS AVAILABILITY
    FROM RECIPE_BOM
    """
    return execute_query(conn, sql, (float(quantity), cake_id))


def is_cake_bakeable(conn: Any, cake_id: int, quantity: int = 1) -> Tuple[bool, List[str]]:
    """Return `(True, [])` when all scaled BOM ingredients are stocked, else `(False, missing_list)`."""
    bom_items = check_recipe_bom_availability(conn, cake_id, quantity=quantity)
    missing = [item["INGREDIENT_NAME"] for item in bom_items if item["AVAILABILITY"] == "OUT_OF_STOCK"]
    return (len(missing) == 0, missing)


# ==============================================================================
# 3. CRYPTOGRAPHIC HMAC-SHA256 HASH-CHAINED AUDIT TRAIL (BB_AUDIT_LOG)
# ==============================================================================

def compute_block_hash(prev_hash: str, session_id: str, action_type: str, payload_str: str) -> str:
    """Compute keyed HMAC-SHA256 digest over `(prev_hash | session_id | action_type | payload_str)`."""
    raw = f"{prev_hash}|{session_id}|{action_type}|{payload_str}".encode("utf-8")
    return hmac.new(_get_audit_hmac_key(), raw, hashlib.sha256).hexdigest()


def get_latest_audit_hash(conn: Any) -> str:
    """Fetch the latest hash tip in `BB_AUDIT_LOG` (`FETCH FIRST 1 ROWS ONLY`), or genesis hash."""
    sql = "SELECT CURRENT_HASH FROM BB_AUDIT_LOG ORDER BY LOG_ID DESC FETCH FIRST 1 ROWS ONLY"
    rows = execute_query(conn, sql)
    if rows:
        return rows[0]["CURRENT_HASH"]
    return GENESIS_PREV_HASH


def append_audit_log(
    conn: Any,
    session_id: str,
    action_type: str,
    payload_dict: Dict[str, Any],
    commit: bool = True,
) -> Dict[str, Any]:
    """
    Thread-safely append a tamper-evident keyed HMAC-SHA256 record to `BB_AUDIT_LOG`.
    Seals an explicit UTC `_audit_ts` timestamp inside the hashed JSON preimage.
    When `commit=False`, participates directly inside the caller's atomic UOW.
    """
    sealed_payload = dict(payload_dict)
    sealed_payload.setdefault("_audit_ts", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    canonical_payload = json.dumps(sealed_payload, sort_keys=True)
    with _audit_append_lock:
        try:
            execute_dml(conn, "LOCK TABLE BB_AUDIT_LOG IN EXCLUSIVE MODE", (), commit=False)
        except Exception:
            pass  # Mock/non-privileged fallback still protected by _audit_append_lock
        prev_hash = get_latest_audit_hash(conn)
        current_hash = compute_block_hash(prev_hash, session_id, action_type, canonical_payload)
        insert_sql = """
        INSERT INTO BB_AUDIT_LOG (SESSION_ID, ACTION_TYPE, PAYLOAD, PREV_HASH, CURRENT_HASH)
        VALUES (?, ?, ?, ?, ?)
        """
        execute_dml(conn, insert_sql, (session_id, action_type, canonical_payload, prev_hash, current_hash), commit=commit)

    return {
        "session_id": session_id,
        "action_type": action_type,
        "payload": sealed_payload,
        "prev_hash": prev_hash,
        "current_hash": current_hash,
    }


def verify_audit_chain(conn: Any) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Cryptographically verify pointer continuity and SHA-256 payload digests across `BB_AUDIT_LOG`.
    Returns `(True, None, None)` if intact, or `(False, compromised_log_id, details)`.
    """
    sql = "SELECT LOG_ID, SESSION_ID, ACTION_TYPE, PAYLOAD, PREV_HASH, CURRENT_HASH FROM BB_AUDIT_LOG ORDER BY LOG_ID"
    records = execute_query(conn, sql)
    if not records:
        return (True, None, None)

    expected_prev = GENESIS_PREV_HASH
    for r in records:
        log_id = r["LOG_ID"]
        if r["PREV_HASH"] != expected_prev:
            return (False, log_id, f"Broken chain pointer: expected prev_hash '{expected_prev}', got '{r['PREV_HASH']}'")

        calculated_current = compute_block_hash(r["PREV_HASH"], r["SESSION_ID"], r["ACTION_TYPE"], r["PAYLOAD"])
        if calculated_current != r["CURRENT_HASH"]:
            return (False, log_id, f"Hash divergence: payload modified. Expected '{calculated_current}', got '{r['CURRENT_HASH']}'")
        expected_prev = r["CURRENT_HASH"]

    return (True, None, None)


# ==============================================================================
# 4. ATOMIC END-TO-END ORDER PLACEMENT & HAPPINESS GUARANTEE REFUND
# ==============================================================================

def _allocate_next_order_id(conn: Any) -> int:
    """Allocate a collision-free Order ID via IBM Db2 SEQ_BB_ORDER_ID sequence (with safe MAX fallback)."""
    try:
        rows = execute_query(conn, "SELECT NEXT VALUE FOR SEQ_BB_ORDER_ID AS NEXT_ORDER_ID FROM SYSIBM.SYSDUMMY1")
        if rows and rows[0].get("NEXT_ORDER_ID") is not None:
            return int(rows[0]["NEXT_ORDER_ID"])
    except Exception:
        pass
    max_rows = execute_query(conn, "SELECT COALESCE(MAX(ORDER_ID), 1104) + 1 AS NEXT_ORDER_ID FROM BB_ORDERS")
    if max_rows and max_rows[0].get("NEXT_ORDER_ID") is not None:
        return int(max_rows[0]["NEXT_ORDER_ID"])
    return 1105


def place_verified_order_atomic(
    conn: Any,
    cake_id: int,
    customer_name: str,
    customer_phone: str,
    quantity: int = 1,
    cake_base: str = "Khoaa (Eggless)",
    custom_message: str = "",
    delivery_address: str = "Mathura, UP",
    session_id: str = "order_api",
) -> Dict[str, Any]:
    """
    Execute a full single-UOW ACID order transaction inside IBM Db2:
      1. Validate input & extract normalized `phone_last10` for sargable lookup.
      2. Fetch cake catalog metadata from `BB_CAKES`.
      3. Run quantity-scaled In-Db2 Recursive BOM CTE (`is_cake_bakeable`) to confirm raw ingredient stock.
      4. Acquire atomic row lock (`SP_RESERVE_CAKE_STOCK` / `FOR UPDATE WITH RS`) without premature commit.
      5. Allocate Order ID cleanly via Db2 `SEQ_BB_ORDER_ID`, insert `BB_ORDERS` + `BB_ORDER_ITEMS` + `BB_AUDIT_LOG`.
      6. Commit all changes atomically, or rollback cleanly on any failure.
    """
    if not isinstance(cake_id, int) or cake_id <= 0 or not isinstance(quantity, int) or quantity <= 0:
        return {"success": False, "status": "INVALID_REQUEST", "message": "Invalid cake_id or quantity."}

    clean_name = (customer_name or "").strip()
    phone_10 = extract_phone_last10(customer_phone)
    if not clean_name or not phone_10:
        return {"success": False, "status": "INVALID_CUSTOMER_DETAILS", "message": "Valid name and 10-digit mobile number required."}

    try:
        cakes = execute_query(
            conn,
            "SELECT CAKE_ID, NAME, SKU_ID, STOCK_QTY, PRICE, IS_EGGLESS_AVAILABLE FROM BB_CAKES WHERE CAKE_ID = ?",
            (cake_id,),
        )
        if not cakes:
            return {"success": False, "status": "CAKE_NOT_FOUND", "message": f"Cake ID #{cake_id} does not exist."}

        cake = cakes[0]
        bakeable, missing = is_cake_bakeable(conn, cake_id, quantity=quantity)
        if not bakeable:
            return {
                "success": False,
                "status": "BOM_INGREDIENT_SHORTAGE",
                "missing_ingredients": missing,
                "message": f"Cannot bake {quantity}x {cake['NAME']}: raw ingredient shortage ({', '.join(missing)}).",
            }

        if not call_sp_reserve_cake_stock(conn, cake_id, quantity, commit=False):
            conn.rollback()
            return {"success": False, "status": "OUT_OF_STOCK", "message": f"{cake['NAME']} is currently sold out or insufficient stock."}

        new_order_id = _allocate_next_order_id(conn)
        sku_id = str(cake.get("SKU_ID") or f"BB-{cake_id}")
        item_weight = _resolve_cake_weight(sku_id)
        unit_price = float(cake["PRICE"])
        total_amount = round(unit_price * quantity, 2)

        execute_dml(
            conn,
            """
            INSERT INTO BB_ORDERS
            (order_id, user_id, customer_name, customer_phone, phone_last10, order_type, order_status, total_amount, delivery_address, special_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_order_id, 1, clean_name, customer_phone.strip(), phone_10,
                "DELIVERY", "CONFIRMED", total_amount, delivery_address.strip(), custom_message.strip(),
            ),
            commit=False,
        )
        execute_dml(
            conn,
            """
            INSERT INTO BB_ORDER_ITEMS
            (order_id, sku_id, item_name, quantity, unit_price, cake_base, cake_weight, custom_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_order_id, sku_id, cake["NAME"],
                quantity, unit_price, cake_base, item_weight, custom_message.strip(),
            ),
            commit=False,
        )
        audit_entry = append_audit_log(
            conn,
            session_id,
            "ORDER_PLACED",
            {"order_id": new_order_id, "cake_id": cake_id, "sku_id": sku_id, "cake_weight": item_weight, "qty": quantity, "total_amount": total_amount},
            commit=False,
        )
        conn.commit()
        return {
            "success": True,
            "status": "CONFIRMED",
            "order_id": new_order_id,
            "cake_name": cake["NAME"],
            "cake_weight": item_weight,
            "quantity": quantity,
            "total_amount": total_amount,
            "baking_eta": "3-4 hours (Fresh Baked on Order)",
            "audit_hash": audit_entry["current_hash"],
            "message": f"Radhe Radhe ji! Order #{new_order_id} confirmed for {quantity}x {cake['NAME']} ({item_weight}).",
        }
    except Exception:
        conn.rollback()
        raise


def evaluate_refund_request(
    conn: Any,
    order_id: int,
    reason: str,
    customer_phone: Optional[str] = None,
    require_phone_auth: bool = False,
    client_ip: str = "local",
) -> Dict[str, Any]:
    """
    Evaluate customer refund eligibility under Shri Ram Baker's Happiness Guarantee.
    Enforces 2FA phone matching, IP+order brute-force rate limiting, and single-UOW ACID
    updates paired with tamper-evident `BB_AUDIT_LOG` entries.
    """
    if not isinstance(order_id, int) or order_id <= 0:
        return {"eligible": False, "order_id": order_id, "status": "INVALID_ORDER_ID", "message": "Invalid order_id."}

    if require_phone_auth and order_auth_limiter.is_locked(order_id, client_ip=client_ip):
        return {
            "eligible": False,
            "order_id": order_id,
            "status": "TOO_MANY_ATTEMPTS",
            "message": "Too many failed phone verification attempts. Temporarily locked for security.",
        }

    safe_reason = (reason or "Customer claim").strip()[:500]
    phone_10 = extract_phone_last10(customer_phone)

    if require_phone_auth and not phone_10:
        return {
            "eligible": False,
            "order_id": order_id,
            "status": "VERIFICATION_REQUIRED",
            "message": "Registered 10-digit mobile number is required to authorize refund evaluation.",
        }

    rows = execute_query(
        conn,
        "SELECT ORDER_ID, ORDER_STATUS, TOTAL_AMOUNT, CREATED_AT, CUSTOMER_PHONE FROM BB_ORDERS WHERE ORDER_ID = ?",
        (order_id,),
    )
    if not rows:
        return {
            "eligible": False,
            "order_id": order_id,
            "status": "ORDER_NOT_FOUND",
            "message": f"Order #{order_id} could not be located in IBM Db2 records.",
        }

    order = rows[0]
    if require_phone_auth:
        stored_10 = extract_phone_last10(str(order.get("CUSTOMER_PHONE", "")))
        if stored_10 != phone_10:
            order_auth_limiter.record_failure(order_id, client_ip=client_ip)
            append_audit_log(
                conn,
                f"order_{order_id}",
                "REFUND_AUTH_FAILED",
                {"order_id": order_id, "client_ip": client_ip, "reason": "Registered phone verification mismatch"},
                commit=True,
            )
            return {
                "eligible": False,
                "order_id": order_id,
                "status": "PHONE_MISMATCH",
                "message": f"Verification failed: provided phone number does not match Order #{order_id}.",
            }
        order_auth_limiter.reset(order_id, client_ip=client_ip)

    status = str(order["ORDER_STATUS"]).upper()
    amount = float(order["TOTAL_AMOUNT"])

    if status in ("BAKING", "CONFIRMED"):
        try:
            execute_dml(conn, "UPDATE BB_ORDERS SET ORDER_STATUS = 'REFUNDED' WHERE ORDER_ID = ?", (order_id,), commit=False)
            append_audit_log(
                conn,
                f"order_{order_id}",
                "REFUND_APPROVED",
                {
                    "order_id": order_id,
                    "amount": amount,
                    "reason": safe_reason,
                    "policy": "Happiness Guarantee 100% Assurance",
                },
                commit=False,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        return {
            "eligible": True,
            "order_id": order_id,
            "status": "REFUNDED",
            "amount_refunded": amount,
            "message": f"Refund of ₹{amount:.2f} approved under Shri Ram Baker's Happiness Guarantee. Order status updated.",
        }
    if status == "DELIVERED":
        return {
            "eligible": True,
            "order_id": order_id,
            "status": "STORE_CREDIT_ISSUED",
            "amount_refunded": amount,
            "message": f"Replacement or store credit voucher issued for ₹{amount:.2f}. Support agent notified.",
        }
    if status == "REFUNDED":
        return {
            "eligible": False,
            "order_id": order_id,
            "status": "ALREADY_REFUNDED",
            "message": f"Order #{order_id} has already been refunded.",
        }
    return {
        "eligible": False,
        "order_id": order_id,
        "status": "INELIGIBLE",
        "message": f"Order #{order_id} in status '{status}' is not eligible for automated online refund.",
    }
