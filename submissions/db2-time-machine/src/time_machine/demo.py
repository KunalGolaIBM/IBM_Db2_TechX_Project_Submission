"""Demo data: schema setup, a realistic baseline, and fault injection.

Each fault is one SQL transaction run as a named "application user" (via
SYSPROC.WLM_SET_CLIENT_INFO) so the investigation can report who changed the data.
"""
from __future__ import annotations

import random
import re
import time
from pathlib import Path

from .db import Db2Gateway

SQL_DIR = Path(__file__).resolve().parents[2] / "db2"

PRODUCTS = [
    (1, "Aurora Laptop", "Computers", 500), (2, "Pulse Headphones", "Audio", 120),
    (3, "Nimbus Phone", "Phones", 800), (4, "Orbit Watch", "Wearables", 250),
    (5, "Zephyr Keyboard", "Accessories", 90), (6, "Atlas Monitor", "Computers", 320),
]
FAULTS = {
    "price": ("nightly_batch", "A nightly batch silently cuts the Aurora Laptop price from 500 to 50"),
    "duplicate": ("etl_rerun", "An ETL job is re-run and loads duplicate Aurora Laptop order lines"),
    "quantity": ("bulk_import", "A bad bulk import sets the quantity of many Aurora Laptop lines to 0"),
    "deleted": ("cleanup_job", "A cleanup job deletes many Aurora Laptop order lines"),
}


def set_actor(db: Db2Gateway, name: str) -> bool:
    """Tag the connection with an application user name (read by the CHANGED_BY triggers)."""
    if not re.fullmatch(r"[a-z_]{1,30}", name):
        raise ValueError("invalid actor name")
    try:
        db.execute(f"CALL SYSPROC.WLM_SET_CLIENT_INFO('{name}', CAST(NULL AS VARCHAR(255)), "
                   "CAST(NULL AS VARCHAR(255)), CAST(NULL AS VARCHAR(255)), CAST(NULL AS VARCHAR(255)))")
        return True
    except Exception:
        db.rollback()
        return False  # falls back to SESSION_USER in the triggers


def init_schema(db: Db2Gateway, reset: bool = True) -> None:
    try:
        db.execute(f"CREATE SCHEMA {db.s.db_schema}")
    except Exception:
        db.rollback()  # already exists
    db.execute(f"SET CURRENT SCHEMA = {db.s.db_schema}")
    if reset:
        db.run_script(SQL_DIR / "00_drop.sql", ignore_errors=True)
    db.run_script(SQL_DIR / "01_schema.sql")


def seed_baseline(db: Db2Gateway, seed: int = 42) -> dict:
    """Load products/orders/order lines as 'erp_loader', snapshot KPIs, then add a little normal activity."""
    rnd = random.Random(seed)
    set_actor(db, "erp_loader")
    for pid, name, cat, price in PRODUCTS:
        db.execute("INSERT INTO PRODUCTS (PRODUCT_ID, NAME, CATEGORY, LIST_PRICE) VALUES (:a, :b, :c, :d)",
                   {"a": pid, "b": name, "c": cat, "d": price}, commit=False)
    item = 0
    for order in range(1, 81):
        db.execute("INSERT INTO ORDERS (ORDER_ID, CUSTOMER, ORDER_DATE) VALUES (:a, :b, CURRENT DATE)",
                   {"a": order, "b": f"Customer {order:03d}"}, commit=False)
        for pid in rnd.sample([p[0] for p in PRODUCTS], k=rnd.randint(1, 3)):
            item += 1
            price = next(p[3] for p in PRODUCTS if p[0] == pid)
            db.execute("INSERT INTO ORDER_ITEMS (ITEM_ID, ORDER_ID, PRODUCT_ID, QUANTITY, UNIT_PRICE) "
                       "VALUES (:a, :b, :c, :d, :e)",
                       {"a": item, "b": order, "c": pid, "d": rnd.randint(1, 4), "e": price}, commit=False)
    db.commit()
    time.sleep(1.2)
    db.execute("INSERT INTO KPI_SNAPSHOTS (PRODUCT_ID, REVENUE, SNAPSHOT_TS) "
               "SELECT PRODUCT_ID, SUM(QUANTITY * UNIT_PRICE), CURRENT TIMESTAMP FROM ORDER_ITEMS GROUP BY PRODUCT_ID")
    time.sleep(1.2)
    set_actor(db, "web_checkout")  # normal activity after the snapshot
    for k in range(3):
        item += 1
        order = 100 + k
        db.execute("INSERT INTO ORDERS (ORDER_ID, CUSTOMER, ORDER_DATE) VALUES (:a, :b, CURRENT DATE)",
                   {"a": order, "b": f"Web customer {k}"}, commit=False)
        db.execute("INSERT INTO ORDER_ITEMS (ITEM_ID, ORDER_ID, PRODUCT_ID, QUANTITY, UNIT_PRICE) "
                   "VALUES (:a, :b, 1, 1, 500)", {"a": item, "b": order}, commit=False)
        db.commit()
    set_actor(db, "app")
    return {"products": len(PRODUCTS), "order_lines": item}


def inject(db: Db2Gateway, fault: str) -> str:
    """Inject one fault as a single transaction. Returns a human-readable description."""
    if fault not in FAULTS:
        raise ValueError(f"unknown fault '{fault}' (choose from {', '.join(FAULTS)})")
    actor, description = FAULTS[fault]
    time.sleep(1.1)  # make sure the change lands strictly after earlier activity
    set_actor(db, actor)
    if fault == "price":
        db.execute("UPDATE ORDER_ITEMS SET UNIT_PRICE = 50 WHERE PRODUCT_ID = 1 AND UNIT_PRICE = 500 "
                   "AND MOD(ITEM_ID, 2) = 0")
    elif fault == "duplicate":
        db.execute("INSERT INTO ORDER_ITEMS (ITEM_ID, ORDER_ID, PRODUCT_ID, QUANTITY, UNIT_PRICE) "
                   "SELECT ITEM_ID + 100000, ORDER_ID, PRODUCT_ID, QUANTITY, UNIT_PRICE FROM ORDER_ITEMS "
                   "WHERE PRODUCT_ID = 1 AND MOD(ITEM_ID, 3) = 0")
    elif fault == "quantity":
        db.execute("UPDATE ORDER_ITEMS SET QUANTITY = 0 WHERE PRODUCT_ID = 1 AND MOD(ITEM_ID, 2) = 0")
    elif fault == "deleted":
        db.execute("DELETE FROM ORDER_ITEMS WHERE PRODUCT_ID = 1 AND MOD(ITEM_ID, 3) = 0")
    set_actor(db, "app")
    return description


class DemoOps:
    """Thin wrapper used by the web UI's demo buttons."""

    def __init__(self, db: Db2Gateway):
        self.db = db

    def reset(self) -> dict:
        init_schema(self.db, reset=True)
        stats = seed_baseline(self.db)
        return {"message": "Demo data reset: baseline loaded, KPI snapshot taken.", **stats}

    def inject(self, fault: str) -> dict:
        return {"fault": fault, "message": inject(self.db, fault)}
