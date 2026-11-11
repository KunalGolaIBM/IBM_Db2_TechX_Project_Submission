"""
Database Connection, ACID Transaction, and Session Manager for IBM Db2.

Uses official `ibm_db` and `ibm_db_dbi` drivers as primary connector.
Provides:
1. Dynamic environment configuration (without unsafe parent-.env traversal).
2. Explicit transaction boundary control (`commit=False` for multi-statement UOW).
3. Thread-safe, transaction-snapshot MockDb2Connection PEP 249 simulator for
   100% deterministic offline reproducibility without Docker or live credentials.
"""
import copy
import os
import re
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 1. Load submission-local .env only (avoid accidentally inheriting parent workspace .env)
try:
    from dotenv import load_dotenv
    _local_env = Path(__file__).resolve().parent.parent / ".env"
    if _local_env.is_file():
        load_dotenv(dotenv_path=_local_env, override=False)
except ImportError:
    pass

# 2. Check for official IBM Db2 Python drivers
try:
    import ibm_db
    import ibm_db_dbi
except ImportError:
    ibm_db = None
    ibm_db_dbi = None

_PLACEHOLDER_VALUES = {
    "",
    "your_db2_username",
    "your_least_privilege_db2_user",
    "dummy_user",
    "your_db2_password",
    "your_db2_password_here",
}

# Retained for backward imports; prefer get_db2_settings() for runtime resolution
DB2_HOST = os.getenv("DB2_HOST", "127.0.0.1")
DB2_PORT = os.getenv("DB2_PORT", "50000")
DB2_DATABASE = os.getenv("DB2_DATABASE", "IBMDB201")
DB2_FORCE_MOCK = os.getenv("DB2_FORCE_MOCK", "false").lower() in ("true", "1", "yes")


def get_db2_settings() -> Dict[str, Any]:
    """Read IBM Db2 runtime settings dynamically from environment variables."""
    return {
        "host": os.getenv("DB2_HOST", "127.0.0.1"),
        "port": os.getenv("DB2_PORT", "50000"),
        "database": os.getenv("DB2_DATABASE", "IBMDB201"),
        "force_mock": os.getenv("DB2_FORCE_MOCK", "false").lower() in ("true", "1", "yes"),
    }


def is_live_db2_available() -> bool:
    """Return True only when official drivers and non-placeholder credentials are present."""
    settings = get_db2_settings()
    if settings["force_mock"] or ibm_db is None or ibm_db_dbi is None:
        return False
    user = (os.getenv("DB2_USER") or "").strip()
    pwd = (os.getenv("DB2_PASSWORD") or "").strip()
    return (user not in _PLACEHOLDER_VALUES) and (pwd not in _PLACEHOLDER_VALUES)


def get_connection_string() -> str:
    """
    Build standard IBM Db2 TCPIP connection string on-demand without module-level secrets.
    Raises ValueError if required database credentials are missing or placeholders.
    """
    db_user = (os.getenv("DB2_USER") or "").strip()
    db_password = (os.getenv("DB2_PASSWORD") or "").strip()
    if db_user in _PLACEHOLDER_VALUES or db_password in _PLACEHOLDER_VALUES:
        raise ValueError(
            "Missing Db2 credentials! Please configure real DB2_USER and DB2_PASSWORD "
            "in submissions/bakebox-choco-ai/.env before executing live database queries."
        )
    s = get_db2_settings()
    return (
        f"DATABASE={s['database']};"
        f"HOSTNAME={s['host']};"
        f"PORT={s['port']};"
        f"PROTOCOL=TCPIP;"
        f"UID={db_user};"
        f"PWD={db_password};"
    )


def get_masked_connection_string() -> str:
    """Return safe TCPIP connection string with password masked for logging/display."""
    s = get_db2_settings()
    db_user = os.getenv("DB2_USER", "db2inst1")
    return (
        f"DATABASE={s['database']};HOSTNAME={s['host']};PORT={s['port']};"
        f"PROTOCOL=TCPIP;UID={db_user};PWD=********;"
    )


# ==============================================================================
# OFFLINE PEP 249 DB-API 2.0 MOCK ENGINE WITH SNAPSHOT TRANSACTION ROLLBACK
# ==============================================================================

def _digits10(phone: Any) -> str:
    digits = re.sub(r"\D", "", str(phone or ""))
    return digits[-10:] if len(digits) >= 10 else digits


class MockDb2Cursor:
    """
    Thread-safe PEP 249 DB-API 2.0 Cursor emulating IBM Db2 LUW execution semantics.
    Supports ACID snapshot rollback, parameterized predicates, row locks, recursive
    BOM CTEs, stored procedures, SQL views, and Db2 conversation buffers.
    """
    def __init__(self, connection: "MockDb2Connection"):
        self.connection = connection
        self.description: Optional[List[Tuple[str, ...]]] = None
        self.rowcount: int = -1
        self._results: List[Tuple[Any, ...]] = []
        self._idx: int = 0
        self._closed: bool = False

    def close(self) -> None:
        self._closed = True
        self._results = []

    def execute(self, sql: str, params: Tuple = ()) -> "MockDb2Cursor":
        if self._closed:
            raise RuntimeError("Cannot execute on a closed cursor.")

        with self.connection.lock:
            self._idx = 0
            clean_sql = " ".join(sql.strip().split())
            sql_upper = clean_sql.upper()

            if "RECIPE_BOM" in sql_upper:
                return self._exec_recipe_bom(params)
            if "NEXT VALUE FOR SEQ_BB_ORDER_ID" in sql_upper:
                self.connection.begin_tx()
                max_existing = max(self.connection.tables["BB_ORDERS"].keys(), default=1104) + 1
                nxt = max(self.connection._order_id_seq, max_existing)
                self.connection._order_id_seq = nxt + 1
                self.description = [("NEXT_ORDER_ID", "INT")]
                self._results = [(nxt,)]
                self.rowcount = 1
                return self
            if "COALESCE(MAX(ORDER_ID)" in sql_upper:
                max_existing = max(self.connection.tables["BB_ORDERS"].keys(), default=1104)
                self.description = [("NEXT_ORDER_ID", "INT")]
                self._results = [(max_existing + 1,)]
                self.rowcount = 1
                return self
            if "SELECT COUNT(*) AS CNT FROM" in sql_upper:
                return self._exec_count(sql_upper, params)
            if sql_upper.startswith("CALL SP_RESERVE_CAKE_STOCK"):
                return self._exec_sp_reserve(params)
            if "FOR UPDATE" in sql_upper and "BB_CAKES" in sql_upper:
                return self._exec_cakes_for_update(params)
            if sql_upper.startswith("SELECT") and "FROM V_ACTIVE_BAKERY_ORDERS" in sql_upper:
                return self._exec_view_active_orders()
            if sql_upper.startswith("SELECT") and "FROM V_MASKED_BAKERY_ORDERS" in sql_upper:
                return self._exec_view_masked_orders()
            if sql_upper.startswith("SELECT") and "FROM BB_CAKES" in sql_upper:
                return self._exec_select_cakes(sql_upper, params)
            if sql_upper.startswith("INSERT INTO BB_CAKES"):
                return self._exec_insert_cake(params)
            if sql_upper.startswith("UPDATE BB_CAKES") and "STOCK_QTY" in sql_upper:
                return self._exec_update_cake_stock(params)
            if sql_upper.startswith("INSERT INTO BB_AUDIT_LOG"):
                return self._exec_insert_audit(params)
            if sql_upper.startswith("SELECT") and "FROM BB_AUDIT_LOG" in sql_upper:
                return self._exec_select_audit(sql_upper)
            if sql_upper.startswith("SELECT") and "FROM BB_ORDERS" in sql_upper:
                return self._exec_select_orders(sql_upper, params)
            if sql_upper.startswith("INSERT INTO BB_ORDERS"):
                return self._exec_insert_order(clean_sql, params)
            if sql_upper.startswith("UPDATE BB_ORDERS"):
                return self._exec_update_order(sql_upper, params)
            if sql_upper.startswith("SELECT") and "FROM BB_ORDER_ITEMS" in sql_upper:
                return self._exec_select_order_items(params)
            if sql_upper.startswith("INSERT INTO BB_ORDER_ITEMS"):
                return self._exec_insert_order_item(params)
            if sql_upper.startswith("INSERT INTO BB_USER_CONVERSATION_BUFFER"):
                return self._exec_insert_buffer(params)
            if sql_upper.startswith("SELECT") and "FROM BB_USER_CONVERSATION_BUFFER" in sql_upper:
                return self._exec_select_buffer(params)
            if sql_upper.startswith("DELETE FROM BB_USER_CONVERSATION_BUFFER"):
                return self._exec_delete_buffer(params)

            self.description = [("STATUS", "VARCHAR")]
            self._results = [("OK",)]
            self.rowcount = 1
            return self

    def _exec_recipe_bom(self, params: Tuple) -> "MockDb2Cursor":
        if len(params) >= 2:
            qty = int(round(float(params[0])))
            cake_id = int(params[1])
        else:
            qty = 1
            cake_id = int(params[0]) if params else 1
        bom_results = self.connection.get_recipe_bom(cake_id, quantity=max(1, qty))
        self.description = [
            ("INGREDIENT_NAME", "VARCHAR"),
            ("REQUIRED_QTY", "DECIMAL"),
            ("CURRENT_STOCK", "DECIMAL"),
            ("AVAILABILITY", "VARCHAR"),
        ]
        self._results = [
            (r["INGREDIENT_NAME"], r["REQUIRED_QTY"], r["CURRENT_STOCK"], r["AVAILABILITY"])
            for r in bom_results
        ]
        self.rowcount = len(self._results)
        return self

    def _exec_count(self, sql_upper: str, params: Tuple) -> "MockDb2Cursor":
        self.description = [("CNT", "INT")]
        cnt = 0
        if "FROM BB_ORDERS" in sql_upper and params:
            cnt = 1 if params[0] in self.connection.tables["BB_ORDERS"] else 0
        elif "FROM BB_CAKES" in sql_upper:
            if "WHERE CAKE_ID" in sql_upper and params:
                cnt = 1 if params[0] in self.connection.tables["BB_CAKES"] else 0
            else:
                cnt = len(self.connection.tables["BB_CAKES"])
        elif "FROM BB_INVENTORY" in sql_upper and params:
            cnt = 1 if params[0] in self.connection.tables["BB_INVENTORY"] else 0
        elif "FROM BB_RECIPES" in sql_upper:
            cnt = sum(len(v) for v in self.connection.tables["BB_RECIPES"].values())
        elif "FROM BB_INGREDIENT_COMPONENTS" in sql_upper and len(params) >= 2:
            comps = self.connection.tables["BB_INGREDIENT_COMPONENTS"].get(params[0], [])
            cnt = 1 if any(c["COMPONENT_ID"] == params[1] for c in comps) else 0
        elif "FROM BB_AUDIT_LOG" in sql_upper:
            cnt = len(self.connection.tables["BB_AUDIT_LOG"])
        self._results = [(cnt,)]
        self.rowcount = 1
        return self

    def _exec_cakes_for_update(self, params: Tuple) -> "MockDb2Cursor":
        cake_id = params[0] if params else 1
        row = self.connection.tables["BB_CAKES"].get(cake_id)
        self.description = [("STOCK_QTY", "INTEGER")]
        self._results = [(row["STOCK_QTY"],)] if row else []
        self.rowcount = len(self._results)
        return self

    def _exec_select_cakes(self, sql_upper: str, params: Tuple) -> "MockDb2Cursor":
        rows = list(self.connection.tables["BB_CAKES"].values())
        if "WHERE CAKE_ID = ?" in sql_upper and params:
            c = self.connection.tables["BB_CAKES"].get(params[0])
            rows = [c] if c else []
        elif "WHERE SKU_ID = ?" in sql_upper and params:
            rows = [r for r in rows if r.get("SKU_ID") == params[0]]

        self.description = [
            ("CAKE_ID", "INT"), ("NAME", "VARCHAR"), ("SKU_ID", "VARCHAR"),
            ("STOCK_QTY", "INT"), ("PRICE", "DECIMAL"), ("IS_EGGLESS_AVAILABLE", "SMALLINT"),
        ]
        self._results = [
            (r["CAKE_ID"], r["NAME"], r.get("SKU_ID", ""), r["STOCK_QTY"], r["PRICE"], r.get("IS_EGGLESS_AVAILABLE", 1))
            for r in rows
        ]
        self.rowcount = len(self._results)
        return self

    def _exec_insert_cake(self, params: Tuple) -> "MockDb2Cursor":
        self.connection.begin_tx()
        cid, name, sku_id, price, stock_qty, eggless = params[:6]
        self.connection.tables["BB_CAKES"][int(cid)] = {
            "CAKE_ID": int(cid),
            "NAME": name,
            "SKU_ID": sku_id,
            "PRICE": float(price),
            "STOCK_QTY": int(stock_qty),
            "IS_EGGLESS_AVAILABLE": int(eggless),
        }
        self.description = None
        self.rowcount = 1
        return self

    def _exec_update_cake_stock(self, params: Tuple) -> "MockDb2Cursor":
        self.connection.begin_tx()
        deduct_qty = params[0]
        cake_id = params[1]
        min_qty = params[2] if len(params) > 2 else deduct_qty
        cake = self.connection.tables["BB_CAKES"].get(cake_id)
        if cake and cake["STOCK_QTY"] >= min_qty:
            cake["STOCK_QTY"] -= deduct_qty
            self.rowcount = 1
        else:
            self.rowcount = 0
        self.description = None
        return self

    def _exec_sp_reserve(self, params: Tuple) -> "MockDb2Cursor":
        self.connection.begin_tx()
        cake_id, deduct_qty = params[0], params[1]
        cake = self.connection.tables["BB_CAKES"].get(cake_id)
        self.description = [("SUCCESS", "INTEGER")]
        if deduct_qty > 0 and cake and cake["STOCK_QTY"] >= deduct_qty:
            cake["STOCK_QTY"] -= deduct_qty
            self._results = [(1,)]
            self.rowcount = 1
        else:
            self._results = [(0,)]
            self.rowcount = 0
        return self

    def _exec_insert_audit(self, params: Tuple) -> "MockDb2Cursor":
        self.connection.begin_tx()
        log_id = max((l["LOG_ID"] for l in self.connection.tables["BB_AUDIT_LOG"]), default=0) + 1
        ts_val = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.connection.tables["BB_AUDIT_LOG"].append({
            "LOG_ID": log_id,
            "SESSION_ID": params[0],
            "ACTION_TYPE": params[1],
            "PAYLOAD": params[2],
            "PREV_HASH": params[3],
            "CURRENT_HASH": params[4],
            "TIMESTAMP": ts_val,
        })
        self.rowcount = 1
        self.description = None
        return self

    def _exec_select_audit(self, sql_upper: str) -> "MockDb2Cursor":
        logs = self.connection.tables["BB_AUDIT_LOG"]
        if "SELECT CURRENT_HASH FROM" in sql_upper:
            ordered = list(reversed(logs)) if "ORDER BY LOG_ID DESC" in sql_upper else logs
            if "FETCH FIRST 1 ROWS ONLY" in sql_upper:
                ordered = ordered[:1]
            self.description = [("CURRENT_HASH", "VARCHAR")]
            self._results = [(l["CURRENT_HASH"],) for l in ordered]
        else:
            self.description = [
                ("LOG_ID", "INT"), ("SESSION_ID", "VARCHAR"), ("ACTION_TYPE", "VARCHAR"),
                ("PAYLOAD", "VARCHAR"), ("PREV_HASH", "VARCHAR"), ("CURRENT_HASH", "VARCHAR"),
                ("TIMESTAMP", "VARCHAR"),
            ]
            self._results = [
                (l["LOG_ID"], l["SESSION_ID"], l["ACTION_TYPE"], l["PAYLOAD"], l["PREV_HASH"], l["CURRENT_HASH"], l["TIMESTAMP"])
                for l in logs
            ]
        self.rowcount = len(self._results)
        return self

    def _exec_select_orders(self, sql_upper: str, params: Tuple) -> "MockDb2Cursor":
        orders_map = self.connection.tables["BB_ORDERS"]
        matched: List[Dict[str, Any]] = []

        if "WHERE ORDER_ID = ?" in sql_upper and params:
            order = orders_map.get(params[0])
            if order:
                if len(params) > 1 and ("PHONE" in sql_upper or "RIGHT(" in sql_upper):
                    if _digits10(order.get("phone_last10") or order.get("customer_phone")) == str(params[1]):
                        matched = [order]
                else:
                    matched = [order]
        elif ("PHONE_LAST10 = ?" in sql_upper or "RIGHT(" in sql_upper) and params:
            target = str(params[0])
            matched = [
                o for o in orders_map.values()
                if _digits10(o.get("phone_last10") or o.get("customer_phone")) == target
            ]
            matched.sort(key=lambda o: o.get("created_at", ""), reverse=True)
        else:
            matched = list(orders_map.values())

        if "SELECT ORDER_ID FROM" in sql_upper:
            self.description = [("ORDER_ID", "INT")]
            self._results = [(o["order_id"],) for o in matched]
        elif "SELECT ORDER_ID, ORDER_STATUS" in sql_upper:
            self.description = [
                ("ORDER_ID", "INT"), ("ORDER_STATUS", "VARCHAR"),
                ("TOTAL_AMOUNT", "DECIMAL"), ("CREATED_AT", "VARCHAR"), ("CUSTOMER_PHONE", "VARCHAR"),
            ]
            self._results = [
                (o["order_id"], o["order_status"], o["total_amount"], o["created_at"], o["customer_phone"])
                for o in matched
            ]
        else:
            self.description = [
                ("ORDER_ID", "INT"), ("USER_ID", "INT"), ("CUSTOMER_NAME", "VARCHAR"),
                ("CUSTOMER_PHONE", "VARCHAR"), ("ORDER_TYPE", "VARCHAR"), ("ORDER_STATUS", "VARCHAR"),
                ("TOTAL_AMOUNT", "DECIMAL"), ("DELIVERY_ADDRESS", "VARCHAR"),
                ("SPECIAL_NOTES", "VARCHAR"), ("CREATED_AT", "VARCHAR"),
            ]
            self._results = [
                (
                    o["order_id"], o.get("user_id", 1), o["customer_name"], o["customer_phone"],
                    o["order_type"], o["order_status"], o["total_amount"],
                    o["delivery_address"], o["special_notes"], o["created_at"],
                )
                for o in matched
            ]
        self.rowcount = len(self._results)
        return self

    def _exec_insert_order(self, clean_sql: str, params: Tuple) -> "MockDb2Cursor":
        self.connection.begin_tx()
        orders_map = self.connection.tables["BB_ORDERS"]
        if len(params) >= 10:
            # Explicit order_id, user_id, customer_name, customer_phone, phone_last10, order_type, order_status, total_amount, delivery_address, special_notes
            oid = int(params[0])
            user_id, cname, cphone, p10, otype, ostatus, total_amt, addr, notes = params[1:10]
        else:
            oid = max(orders_map.keys(), default=1100) + 1
            user_id, cname, cphone, p10, otype, ostatus, total_amt, addr, notes = params[:9]
        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        orders_map[oid] = {
            "order_id": oid,
            "user_id": user_id,
            "customer_name": cname,
            "customer_phone": cphone,
            "phone_last10": p10 or _digits10(cphone),
            "order_type": otype,
            "order_status": ostatus,
            "total_amount": float(total_amt),
            "delivery_address": addr,
            "special_notes": notes,
            "created_at": now_ts,
        }
        self.connection.last_inserted_order_id = oid
        self.rowcount = 1
        self.description = None
        return self

    def _exec_update_order(self, sql_upper: str, params: Tuple) -> "MockDb2Cursor":
        self.connection.begin_tx()
        if len(params) == 1:
            order_id = params[0]
            status = "REFUNDED" if "REFUNDED" in sql_upper else "CONFIRMED"
        else:
            status = params[0]
            order_id = params[1]
        if order_id in self.connection.tables["BB_ORDERS"]:
            self.connection.tables["BB_ORDERS"][order_id]["order_status"] = status
            self.rowcount = 1
        else:
            self.rowcount = 0
        self.description = None
        return self

    def _exec_select_order_items(self, params: Tuple) -> "MockDb2Cursor":
        order_id = params[0] if params else 1002
        self.description = [
            ("ITEM_ID", "INT"), ("ORDER_ID", "INT"), ("SKU_ID", "VARCHAR"),
            ("ITEM_NAME", "VARCHAR"), ("QUANTITY", "INT"), ("UNIT_PRICE", "DECIMAL"),
            ("CAKE_BASE", "VARCHAR"), ("CAKE_WEIGHT", "VARCHAR"), ("CUSTOM_MESSAGE", "VARCHAR"),
        ]
        items = self.connection.tables["BB_ORDER_ITEMS"].get(order_id, [])
        self._results = [
            (it["ITEM_ID"], it["ORDER_ID"], it["SKU_ID"], it["ITEM_NAME"], it["QUANTITY"], it["UNIT_PRICE"], it["CAKE_BASE"], it["CAKE_WEIGHT"], it["CUSTOM_MESSAGE"])
            for it in items
        ]
        self.rowcount = len(self._results)
        return self

    def _exec_insert_order_item(self, params: Tuple) -> "MockDb2Cursor":
        self.connection.begin_tx()
        order_id, sku_id, item_name, qty, unit_price, cake_base, cake_weight, custom_msg = params[:8]
        items_list = self.connection.tables["BB_ORDER_ITEMS"].setdefault(order_id, [])
        next_item_id = sum(len(v) for v in self.connection.tables["BB_ORDER_ITEMS"].values()) + 1
        items_list.append({
            "ITEM_ID": next_item_id,
            "ORDER_ID": order_id,
            "SKU_ID": sku_id,
            "ITEM_NAME": item_name,
            "QUANTITY": int(qty),
            "UNIT_PRICE": float(unit_price),
            "CAKE_BASE": cake_base,
            "CAKE_WEIGHT": cake_weight,
            "CUSTOM_MESSAGE": custom_msg,
        })
        self.rowcount = 1
        self.description = None
        return self

    def _exec_view_active_orders(self) -> "MockDb2Cursor":
        self.description = [
            ("ORDER_ID", "INT"), ("CUSTOMER_NAME", "VARCHAR"), ("ORDER_STATUS", "VARCHAR"),
            ("TOTAL_AMOUNT", "DECIMAL"), ("CREATED_AT", "VARCHAR"), ("TOTAL_ITEMS", "INT"),
        ]
        rows = []
        for oid, o in self.connection.tables["BB_ORDERS"].items():
            cnt = len(self.connection.tables["BB_ORDER_ITEMS"].get(oid, []))
            rows.append((o["order_id"], o["customer_name"], o["order_status"], o["total_amount"], o["created_at"], cnt))
        self._results = rows
        self.rowcount = len(rows)
        return self

    def _exec_view_masked_orders(self) -> "MockDb2Cursor":
        self.description = [
            ("ORDER_ID", "INT"), ("MASKED_CUSTOMER_NAME", "VARCHAR"), ("MASKED_PHONE", "VARCHAR"),
            ("ORDER_TYPE", "VARCHAR"), ("ORDER_STATUS", "VARCHAR"), ("TOTAL_AMOUNT", "DECIMAL"),
            ("CREATED_AT", "VARCHAR"),
        ]
        rows = []
        for o in self.connection.tables["BB_ORDERS"].values():
            cname = (o["customer_name"] or "C")[:1] + "****"
            p10 = _digits10(o.get("phone_last10") or o.get("customer_phone"))
            mphone = f"+91 ******{p10[-4:]}" if len(p10) >= 4 else "******"
            rows.append((o["order_id"], cname, mphone, o["order_type"], o["order_status"], o["total_amount"], o["created_at"]))
        self._results = rows
        self.rowcount = len(rows)
        return self

    def _exec_insert_buffer(self, params: Tuple) -> "MockDb2Cursor":
        self.connection.begin_tx()
        session_id, user_id, role, content, ui_json, crag_status = params[:6]
        buf = self.connection.tables["BB_USER_CONVERSATION_BUFFER"]
        bid = len(buf) + 1
        buf.append({
            "BUFFER_ID": bid,
            "SESSION_ID": session_id,
            "USER_ID": user_id,
            "ROLE": role,
            "CONTENT": content,
            "UI_CARDS_JSON": ui_json,
            "CRAG_STATUS": crag_status,
            "CREATED_AT": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        })
        self.rowcount = 1
        self.description = None
        return self

    def _exec_select_buffer(self, params: Tuple) -> "MockDb2Cursor":
        session_id = params[0] if params else ""
        self.description = [
            ("ROLE", "VARCHAR"), ("CONTENT", "VARCHAR"),
            ("UI_CARDS_JSON", "VARCHAR"), ("CRAG_STATUS", "VARCHAR"), ("CREATED_AT", "VARCHAR"),
        ]
        rows = [
            (r["ROLE"], r["CONTENT"], r["UI_CARDS_JSON"], r["CRAG_STATUS"], r["CREATED_AT"])
            for r in self.connection.tables["BB_USER_CONVERSATION_BUFFER"]
            if r["SESSION_ID"] == session_id
        ]
        self._results = rows
        self.rowcount = len(rows)
        return self

    def _exec_delete_buffer(self, params: Tuple) -> "MockDb2Cursor":
        self.connection.begin_tx()
        session_id = params[0] if params else ""
        before = len(self.connection.tables["BB_USER_CONVERSATION_BUFFER"])
        self.connection.tables["BB_USER_CONVERSATION_BUFFER"] = [
            r for r in self.connection.tables["BB_USER_CONVERSATION_BUFFER"]
            if r["SESSION_ID"] != session_id
        ]
        self.rowcount = before - len(self.connection.tables["BB_USER_CONVERSATION_BUFFER"])
        self.description = None
        return self

    def fetchone(self) -> Optional[Tuple]:
        if self._idx < len(self._results):
            row = self._results[self._idx]
            self._idx += 1
            return row
        return None

    def fetchall(self) -> List[Tuple]:
        remaining = self._results[self._idx:]
        self._idx = len(self._results)
        return remaining


class MockDb2Connection:
    """Thread-safe PEP 249 connection with snapshot-backed ACID commit/rollback."""
    _instance = None
    _global_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._global_lock:
            if cls._instance is None:
                cls._instance = super(MockDb2Connection, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self) -> None:
        self.lock = threading.RLock()
        self._tx_snapshot: Optional[Dict[str, Any]] = None
        self._order_id_seq: int = 1105
        self.last_inserted_order_id: int = 1104
        self.tables: Dict[str, Any] = {
            "BB_CAKES": {
                1: {"CAKE_ID": 1, "NAME": "Red Velvet Crimson Crumb Crown", "SKU_ID": "BB-RED-01-1kg", "STOCK_QTY": 5, "PRICE": 649.0, "IS_EGGLESS_AVAILABLE": 1},
                2: {"CAKE_ID": 2, "NAME": "Black Forest Classic Cherry Gateau", "SKU_ID": "BB-BLK-01-05kg", "STOCK_QTY": 1, "PRICE": 249.0, "IS_EGGLESS_AVAILABLE": 1},
                3: {"CAKE_ID": 3, "NAME": "Pineapple Classic Spiral Mirror", "SKU_ID": "BB-PIN-01-05kg", "STOCK_QTY": 0, "PRICE": 249.0, "IS_EGGLESS_AVAILABLE": 1},
                4: {"CAKE_ID": 4, "NAME": "Red Velvet Heart Love Affair", "SKU_ID": "BB-RED-02-1kg", "STOCK_QTY": 4, "PRICE": 649.0, "IS_EGGLESS_AVAILABLE": 1},
                5: {"CAKE_ID": 5, "NAME": "Mathura Oven Fresh Paneer Patty", "SKU_ID": "BB-SNK-01-PTY", "STOCK_QTY": 20, "PRICE": 35.0, "IS_EGGLESS_AVAILABLE": 1},
            },
            "BB_INVENTORY": {
                101: {"INGREDIENT_ID": 101, "NAME": "Khoaa Base (Eggless)", "STOCK_QTY": 12.0},
                102: {"INGREDIENT_ID": 102, "NAME": "Belgian Dark Cocoa", "STOCK_QTY": 8.5},
                103: {"INGREDIENT_ID": 103, "NAME": "Cream Cheese Frosting", "STOCK_QTY": 4.0},
                104: {"INGREDIENT_ID": 104, "NAME": "Maraschino Cherries", "STOCK_QTY": 0.2},
                105: {"INGREDIENT_ID": 105, "NAME": "Fresh Milk Solids (Mawa)", "STOCK_QTY": 10.0},
                106: {"INGREDIENT_ID": 106, "NAME": "Whipped Dairy Cream", "STOCK_QTY": 6.0},
                107: {"INGREDIENT_ID": 107, "NAME": "Spiced Paneer Masala Filling", "STOCK_QTY": 15.0},
            },
            "BB_INGREDIENT_COMPONENTS": {
                101: [{"COMPONENT_ID": 105, "COMPONENT_NAME": "Fresh Milk Solids (Mawa)", "QTY_RATIO": 0.65}],
                103: [{"COMPONENT_ID": 106, "COMPONENT_NAME": "Whipped Dairy Cream", "QTY_RATIO": 0.50}],
            },
            "BB_RECIPES": {
                1: [
                    {"CAKE_ID": 1, "INGREDIENT_NAME": "Khoaa Base (Eggless)", "QTY_NEEDED": 0.5, "INGREDIENT_ID": 101},
                    {"CAKE_ID": 1, "INGREDIENT_NAME": "Cream Cheese Frosting", "QTY_NEEDED": 0.4, "INGREDIENT_ID": 103},
                ],
                2: [
                    {"CAKE_ID": 2, "INGREDIENT_NAME": "Khoaa Base (Eggless)", "QTY_NEEDED": 0.3, "INGREDIENT_ID": 101},
                    {"CAKE_ID": 2, "INGREDIENT_NAME": "Belgian Dark Cocoa", "QTY_NEEDED": 0.2, "INGREDIENT_ID": 102},
                    {"CAKE_ID": 2, "INGREDIENT_NAME": "Maraschino Cherries", "QTY_NEEDED": 0.5, "INGREDIENT_ID": 104},
                ],
                3: [
                    {"CAKE_ID": 3, "INGREDIENT_NAME": "Khoaa Base (Eggless)", "QTY_NEEDED": 0.3, "INGREDIENT_ID": 101},
                    {"CAKE_ID": 3, "INGREDIENT_NAME": "Whipped Dairy Cream", "QTY_NEEDED": 0.25, "INGREDIENT_ID": 106},
                ],
                4: [
                    {"CAKE_ID": 4, "INGREDIENT_NAME": "Khoaa Base (Eggless)", "QTY_NEEDED": 0.5, "INGREDIENT_ID": 101},
                    {"CAKE_ID": 4, "INGREDIENT_NAME": "Cream Cheese Frosting", "QTY_NEEDED": 0.4, "INGREDIENT_ID": 103},
                ],
                5: [
                    {"CAKE_ID": 5, "INGREDIENT_NAME": "Spiced Paneer Masala Filling", "QTY_NEEDED": 0.1, "INGREDIENT_ID": 107},
                ],
            },
            "BB_ORDERS": {
                1002: {
                    "order_id": 1002, "user_id": 3, "customer_name": "Rahul Sharma",
                    "customer_phone": "+91 9876543210", "phone_last10": "9876543210",
                    "order_type": "DELIVERY", "order_status": "BAKING",
                    "total_amount": 649.00, "delivery_address": "Flat 402, Krishna Heights, Mathura, UP",
                    "special_notes": "Happy 1st Anniversary Celebration", "created_at": "2026-11-09 10:15:00",
                },
                1104: {
                    "order_id": 1104, "user_id": 5, "customer_name": "Pooja Verma",
                    "customer_phone": "+91 9811223344", "phone_last10": "9811223344",
                    "order_type": "DELIVERY", "order_status": "CONFIRMED",
                    "total_amount": 249.00, "delivery_address": "Civil Lines, Mathura, UP",
                    "special_notes": "Birthday Surprise for Sister", "created_at": "2026-11-09 11:30:00",
                },
            },
            "BB_ORDER_ITEMS": {
                1002: [
                    {
                        "ITEM_ID": 1, "ORDER_ID": 1002, "SKU_ID": "BB-RED-02-1kg",
                        "ITEM_NAME": "Red Velvet Heart Love Affair", "QUANTITY": 1, "UNIT_PRICE": 649.00,
                        "CAKE_BASE": "Khoaa (Eggless)", "CAKE_WEIGHT": "1.0kg", "CUSTOM_MESSAGE": "Happy 1st Anniversary",
                    }
                ],
                1104: [
                    {
                        "ITEM_ID": 2, "ORDER_ID": 1104, "SKU_ID": "BB-BLK-01-05kg",
                        "ITEM_NAME": "Black Forest Classic Cherry Gateau", "QUANTITY": 1, "UNIT_PRICE": 249.00,
                        "CAKE_BASE": "Pure Veg Eggless", "CAKE_WEIGHT": "0.5kg", "CUSTOM_MESSAGE": "Happy Birthday Choti",
                    }
                ],
            },
            "BB_AUDIT_LOG": [],
            "BB_USER_CONVERSATION_BUFFER": [],
            "BB_CHUNKS_VECTOR": {},
        }

    def begin_tx(self) -> None:
        with self.lock:
            if self._tx_snapshot is None:
                self._tx_snapshot = copy.deepcopy(self.tables)

    def reset_state(self) -> None:
        """Reset in-memory state cleanly for isolated unit testing."""
        with self.lock:
            self._initialize()

    def get_recipe_bom(self, cake_id: int, quantity: int = 1) -> List[Dict[str, Any]]:
        """Emulate multi-level Recursive BOM CTE with 4-decimal precision matching Db2."""
        scale = max(1, int(quantity))
        recipes = self.tables["BB_RECIPES"].get(cake_id, [])
        components_map = self.tables.get("BB_INGREDIENT_COMPONENTS", {})
        results: List[Dict[str, Any]] = []
        queue = [(1, r["INGREDIENT_ID"], r["INGREDIENT_NAME"], round(float(r["QTY_NEEDED"]) * scale, 4)) for r in recipes]

        while queue:
            depth, ing_id, ing_name, req_qty = queue.pop(0)
            ing = self.tables["BB_INVENTORY"].get(ing_id)
            curr_stock = ing["STOCK_QTY"] if ing else 0.0
            avail = "IN_STOCK" if curr_stock >= req_qty else "OUT_OF_STOCK"
            results.append({
                "INGREDIENT_NAME": ing_name,
                "REQUIRED_QTY": round(req_qty, 4),
                "CURRENT_STOCK": curr_stock,
                "AVAILABILITY": avail,
            })
            if depth < 5:
                for sub in components_map.get(ing_id, []):
                    queue.append((
                        depth + 1,
                        sub["COMPONENT_ID"],
                        sub["COMPONENT_NAME"],
                        round(req_qty * float(sub["QTY_RATIO"]), 4),
                    ))
        return results

    def cursor(self) -> MockDb2Cursor:
        return MockDb2Cursor(self)

    def commit(self) -> None:
        with self.lock:
            self._tx_snapshot = None

    def rollback(self) -> None:
        with self.lock:
            if self._tx_snapshot is not None:
                self.tables = self._tx_snapshot
                self._tx_snapshot = None

    def close(self) -> None:
        pass


# ==============================================================================
# CONNECTION FACTORY FUNCTIONS & UNIT-OF-WORK HELPERS
# ==============================================================================

def get_raw_connection():
    """Return raw `ibm_db` connection, or MockDb2Connection when offline."""
    if is_live_db2_available():
        return ibm_db.connect(get_connection_string(), "", "")
    return MockDb2Connection()


def get_dbi_connection():
    """Return active PEP 249 connection (`ibm_db_dbi` or MockDb2Connection)."""
    if is_live_db2_available():
        return ibm_db_dbi.connect(get_connection_string(), "", "")
    return MockDb2Connection()


@contextmanager
def db_session():
    """
    Context manager providing an atomic Unit of Work (UOW):
    commits once on clean exit and rolls back automatically on any exception.
    """
    conn = get_dbi_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if is_live_db2_available():
            conn.close()


def execute_query(conn: Any, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
    """Execute a parameterized SELECT query returning uppercase-keyed dicts."""
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        cols = [desc[0].upper() for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return [dict(zip(cols, row)) for row in rows]
    finally:
        cursor.close()


def execute_dml(conn: Any, sql: str, params: Tuple = (), commit: bool = True) -> int:
    """Execute a parameterized INSERT/UPDATE/DELETE statement with optional commit control."""
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        if commit:
            conn.commit()
        return cursor.rowcount
    finally:
        cursor.close()
