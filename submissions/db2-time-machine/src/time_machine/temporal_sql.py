"""Compiles validated query plans into Db2 system-period temporal SQL.

The LLM never writes SQL text. It proposes a structured plan (table, product,
window); these builders turn the plan into SQL using strictly validated values.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .models import fmt_ts


@dataclass(frozen=True)
class TrackedTable:
    """A temporal table the investigator knows how to analyse."""
    name: str
    key: str
    product_col: str
    quantity_col: str
    price_col: str
    order_col: str
    actor_col: str = "CHANGED_BY"
    start_col: str = "SYS_START"
    end_col: str = "SYS_END"
    txn_col: str = "TRANS_ID"


ORDER_ITEMS = TrackedTable(
    name="ORDER_ITEMS", key="ITEM_ID", product_col="PRODUCT_ID",
    quantity_col="QUANTITY", price_col="UNIT_PRICE", order_col="ORDER_ID",
)

# Tables the read-only guard lets agents touch.
ALLOWED_TABLES = {
    "ORDER_ITEMS", "PRODUCTS", "KPI_SNAPSHOTS", "ROW_DELETE_LOG", "ORDER_ITEMS_HISTORY",
    "AUDIT_LOG", "INCIDENT_REPORTS", "ORDERS",
}


def ts_literal(ts: datetime) -> str:
    """A TIMESTAMP literal built from a datetime object (never from free text)."""
    if not isinstance(ts, datetime):
        raise TypeError("timestamp must be a datetime")
    return f"TIMESTAMP('{fmt_ts(ts)}')"


def _product_filter(t: TrackedTable, product_id: Optional[int]) -> str:
    return f" WHERE {t.product_col} = {int(product_id)}" if product_id is not None else ""


def metric_as_of_sql(t: TrackedTable, product_id: Optional[int], ts: datetime) -> str:
    """Revenue of the table as it was at ``ts`` (time travel with FOR SYSTEM_TIME AS OF)."""
    return (
        f"SELECT COALESCE(SUM({t.quantity_col} * {t.price_col}), 0) AS REVENUE, COUNT(*) AS ROW_COUNT "
        f"FROM {t.name} FOR SYSTEM_TIME AS OF {ts_literal(ts)}{_product_filter(t, product_id)}"
    )


def versions_sql(t: TrackedTable, product_id: Optional[int], start: datetime, end: datetime) -> str:
    """Every row version whose validity overlaps the window (FOR SYSTEM_TIME FROM .. TO ..)."""
    fmt6 = "'YYYY-MM-DD HH24:MI:SS.FF6'"
    fmt12 = "'YYYY-MM-DD HH24:MI:SS.FF12'"
    return (
        f"SELECT {t.key} AS ITEM_ID, {t.order_col} AS ORDER_ID, {t.product_col} AS PRODUCT_ID, "
        f"{t.quantity_col} AS QUANTITY, {t.price_col} AS UNIT_PRICE, {t.actor_col} AS CHANGED_BY, "
        f"VARCHAR_FORMAT({t.start_col}, {fmt6}) AS SYS_START, "
        f"VARCHAR_FORMAT({t.end_col}, {fmt6}) AS SYS_END, "
        f"VARCHAR_FORMAT({t.txn_col}, {fmt12}) AS TRANS_ID "
        f"FROM {t.name} FOR SYSTEM_TIME FROM {ts_literal(start)} TO {ts_literal(end)}"
        f"{_product_filter(t, product_id)} ORDER BY {t.key}, {t.start_col}"
    )


def delete_log_sql(start: datetime, end: datetime) -> str:
    """Who deleted rows, from the AFTER DELETE trigger's log table."""
    return (
        "SELECT ITEM_ID, DELETED_BY, VARCHAR_FORMAT(DELETED_AT, 'YYYY-MM-DD HH24:MI:SS.FF6') AS DELETED_AT "
        f"FROM ROW_DELETE_LOG WHERE DELETED_AT >= {ts_literal(start)} AND DELETED_AT <= {ts_literal(end)} "
        "ORDER BY DELETED_AT"
    )


def snapshot_sql(product_id: Optional[int]) -> str:
    where = f"WHERE PRODUCT_ID = {int(product_id)} " if product_id is not None else ""
    return (
        "SELECT PRODUCT_ID, REVENUE, VARCHAR_FORMAT(SNAPSHOT_TS, 'YYYY-MM-DD HH24:MI:SS.FF6') AS SNAPSHOT_TS "
        f"FROM KPI_SNAPSHOTS {where}ORDER BY SNAPSHOT_TS DESC"
    )


NOW_SQL = "VALUES VARCHAR_FORMAT(CURRENT TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS.FF6')"
PRODUCTS_SQL = "SELECT PRODUCT_ID, NAME, CATEGORY FROM PRODUCTS ORDER BY PRODUCT_ID"
TEMPORAL_TABLES_SQL = (
    "SELECT TABNAME, TEMPORALTYPE FROM SYSCAT.TABLES "
    "WHERE TABSCHEMA = CURRENT SCHEMA AND TEMPORALTYPE <> 'N' ORDER BY TABNAME"
)
