"""Reproducible database initialization: schema -> seed data -> metric registry -> stats -> grants."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from metricguard.config import REPO_ROOT, Settings
from metricguard.core.registry import METRICS
from metricguard.db import Db2Client, Db2Error

from .generator import Dataset, generate
from .migrations import grant_audit_writer, migrate_audit_table

SCHEMA = "METRICGUARD"
SCHEMA_FILES = [REPO_ROOT / "db" / "schema" / "001_tables.sql", REPO_ROOT / "db" / "schema" / "002_indexes.sql"]
# Child tables first.
TABLES = ["QUERY_AUDIT_LOG", "METRIC_DEFINITIONS", "REFUNDS", "ORDER_ITEMS", "ORDERS", "PRODUCTS"]
READ_TABLES = ["ORDERS", "ORDER_ITEMS", "PRODUCTS", "REFUNDS", "METRIC_DEFINITIONS"]

Log = Callable[[str], None]


def split_sql(path: Path) -> list[str]:
    lines = [ln for ln in path.read_text().splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def _ts(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def drop_schema(db: Db2Client, log: Log) -> None:
    existing = {
        r[0]
        for r in db.query("SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ?", (SCHEMA,)).rows
    }
    for table in TABLES:
        if table in existing:
            db.execute(f"DROP TABLE {SCHEMA}.{table}")
            log(f"dropped {SCHEMA}.{table}")
    if db.scalar("SELECT COUNT(*) FROM SYSCAT.SCHEMATA WHERE SCHEMANAME = ?", (SCHEMA,)):
        db.execute(f"DROP SCHEMA {SCHEMA} RESTRICT")
        log(f"dropped schema {SCHEMA}")


def create_schema(db: Db2Client, log: Log) -> int:
    count = 0
    for path in SCHEMA_FILES:
        for stmt in split_sql(path):
            db.execute(stmt)
            count += 1
        log(f"applied {path.relative_to(REPO_ROOT)}")
    return count


def load_dataset(db: Db2Client, ds: Dataset, log: Log) -> dict[str, int]:
    inserted: dict[str, int] = {}
    inserted["PRODUCTS"] = db.execute_many(
        f"INSERT INTO {SCHEMA}.PRODUCTS (PRODUCT_ID, SKU, PRODUCT_NAME, CATEGORY, LIST_PRICE, IS_ACTIVE, CREATED_AT) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(p.product_id, p.sku, p.product_name, p.category, str(p.list_price), p.is_active, "2025-12-01 00:00:00")
         for p in ds.products],
    )
    inserted["ORDERS"] = db.execute_many(
        f"INSERT INTO {SCHEMA}.ORDERS (ORDER_ID, ORDER_NUMBER, CUSTOMER_ID, ORDER_TS, STATUS, REGION_CODE, "
        "CHANNEL_CODE, CURRENCY_CODE, SHIPPING_AMOUNT, PROMO_CODE, CANCELLED_TS) VALUES (?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?)",
        [(o.order_id, o.order_number, o.customer_id, _ts(o.order_ts), o.status, o.region_code, o.channel_code,
          str(o.shipping_amount), o.promo_code, _ts(o.cancelled_ts)) for o in ds.orders],
    )
    inserted["ORDER_ITEMS"] = db.execute_many(
        f"INSERT INTO {SCHEMA}.ORDER_ITEMS (ORDER_ITEM_ID, ORDER_ID, LINE_NUMBER, PRODUCT_ID, QUANTITY, UNIT_PRICE, "
        "DISCOUNT_AMOUNT) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(i.order_item_id, i.order_id, i.line_number, i.product_id, i.quantity, str(i.unit_price),
          str(i.discount_amount)) for i in ds.items],
    )
    inserted["REFUNDS"] = db.execute_many(
        f"INSERT INTO {SCHEMA}.REFUNDS (REFUND_ID, ORDER_ID, ORDER_ITEM_ID, REFUND_TS, REFUND_AMOUNT, STATUS, "
        "REASON_CODE) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(r.refund_id, r.order_id, r.order_item_id, _ts(r.refund_ts), str(r.refund_amount), r.status,
          r.reason_code) for r in ds.refunds],
    )
    for table, n in inserted.items():
        log(f"inserted {n} rows into {SCHEMA}.{table}")
    return inserted


def register_metrics(db: Db2Client, log: Log) -> int:
    rows: list[tuple[Any, ...]] = []
    for m in METRICS.values():
        rows.append((
            m.name, m.version, m.display_name, m.description, m.calculation, m.unit.value, m.kind,
            int(m.additive), ",".join(m.eligible_order_statuses), m.date_attribution, m.null_handling,
            m.refund_treatment, m.discount_treatment, json.dumps(m.allowed_dimensions),
            json.dumps(m.allowed_filters), m.canonical_json(), m.definition_hash(), m.lifecycle_status, m.owner,
        ))
    n = db.execute_many(
        f"INSERT INTO {SCHEMA}.METRIC_DEFINITIONS (METRIC_NAME, METRIC_VERSION, DISPLAY_NAME, DESCRIPTION, "
        "CALCULATION, UNIT, METRIC_KIND, IS_ADDITIVE, ELIGIBLE_ORDER_STATUSES, DATE_ATTRIBUTION, NULL_HANDLING, "
        "REFUND_TREATMENT, DISCOUNT_TREATMENT, ALLOWED_DIMENSIONS, ALLOWED_FILTERS, DEFINITION_JSON, "
        "DEFINITION_HASH, LIFECYCLE_STATUS, OWNER) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    log(f"registered {n} approved metric definitions")
    return n


STATS_TABLES = ["PRODUCTS", "ORDERS", "ORDER_ITEMS", "REFUNDS", "METRIC_DEFINITIONS"]


def collect_statistics(db: Db2Client, log: Log) -> str:
    """RUNSTATS through SYSPROC.ADMIN_CMD.

    ADMIN_CMD is a fenced routine. Under amd64 emulation on Apple Silicon the fenced
    process cannot start (SQL1646N); the Makefile then runs scripts/db2_runstats.sh, which
    issues the same RUNSTATS through the Db2 CLP inside the container.
    """
    try:
        for table in STATS_TABLES:
            db.execute(
                f"CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE {SCHEMA}.{table} WITH DISTRIBUTION AND DETAILED INDEXES ALL')"
            )
    except Db2Error as exc:
        if exc.sqlcode != -1646:
            raise
        log("RUNSTATS via ADMIN_CMD unavailable (SQL1646N: fenced routines cannot start under emulation); "
            "falling back to scripts/db2_runstats.sh (CLP)")
        return "deferred_to_clp"
    log("RUNSTATS completed via SYSPROC.ADMIN_CMD")
    return "admin_cmd"


def grant_reader(db: Db2Client, settings: Settings, log: Log) -> bool:
    user = settings.db2_reader_user
    if not user:
        log("no DB2_READER_USER configured; skipping least-privilege grants")
        return False
    user = user.upper()
    db.execute(f"GRANT CONNECT ON DATABASE TO USER {user}")
    for table in READ_TABLES:
        db.execute(f"GRANT SELECT ON {SCHEMA}.{table} TO USER {user}")
    log(f"granted CONNECT + SELECT on {', '.join(READ_TABLES)} to {user} (no INSERT/UPDATE/DELETE)")
    return True


def initialize(settings: Settings, *, reset: bool, log: Log = print) -> dict[str, Any]:
    started = time.perf_counter()
    ds = generate()
    with Db2Client(settings) as db:
        if reset:
            drop_schema(db, log)
        statements = create_schema(db, log)
        migrate_audit_table(db, log)
        inserted = load_dataset(db, ds, log)
        metrics = register_metrics(db, log)
        stats = collect_statistics(db, log)
        try:
            granted = grant_reader(db, settings, log)
        except Db2Error as exc:
            log(f"WARNING: reader grants failed ({exc.sqlstate}); analytical queries will use the admin user")
            granted = False
        try:
            audit_granted = grant_audit_writer(db, settings, log)
        except Db2Error as exc:
            log(f"WARNING: audit writer grants failed ({exc.sqlstate}); audit writes will use the admin user")
            audit_granted = False
    return {
        "seed": ds.seed,
        "ddl_statements": statements,
        "inserted": inserted,
        "metric_definitions": metrics,
        "runstats": stats,
        "reader_granted": granted,
        "audit_writer_granted": audit_granted,
        "elapsed_s": round(time.perf_counter() - started, 2),
    }
