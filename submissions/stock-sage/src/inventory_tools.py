"""Deterministic inventory analytics and decision tools for StockSage.

Implements verified mathematical calculations for:
- Low-stock identification
- Days-of-inventory & stockout risk estimation
- Fast-moving and slow-moving categorization
- Batch-level expiry risk classification
- Safety-stock-aware reorder recommendations

Guarantees 100% deterministic calculations; no LLM hallucinations.
"""

from datetime import date, datetime, timedelta
import math
from typing import Any, Dict, List, Optional
import pandas as pd

from src.db_connection import Db2ConnectionManager, db_manager
from src.sql_queries import (
    QUERY_BATCH_EXPIRY,
    QUERY_CATEGORY_PERFORMANCE,
    QUERY_CURRENT_STOCK,
    QUERY_DAILY_SALES_TREND,
    QUERY_LOW_STOCK_PRODUCTS,
    QUERY_SALES_VELOCITY,
    QUERY_SUPPLIERS,
)


def get_current_stock_df(db: Db2ConnectionManager = db_manager) -> pd.DataFrame:
    """Fetch current stock levels for all products as a pandas DataFrame."""
    rows = db.execute_query(QUERY_CURRENT_STOCK)
    df = pd.DataFrame(rows)
    if not df.empty:
        df["total_available_stock"] = df["total_available_stock"].astype(int)
        df["reorder_level"] = df["reorder_level"].astype(int)
        df["unit_price"] = df["unit_price"].astype(float)
        df["lead_time_days"] = df["lead_time_days"].astype(int)
        df["inventory_value"] = df["total_available_stock"] * df["unit_price"]
    return df


def get_inventory_health_summary(db: Db2ConnectionManager = db_manager) -> Dict[str, Any]:
    """High-level summary KPIs for store owner dashboard."""
    df = get_current_stock_df(db)
    if df.empty:
        return {
            "total_products": 0,
            "total_categories": 0,
            "total_units_in_stock": 0,
            "total_inventory_valuation": 0.0,
            "low_stock_count": 0,
            "critical_expiry_count": 0,
        }

    low_stock = df[df["total_available_stock"] <= df["reorder_level"]]
    expiry_data = get_expiry_risk_analysis(db, warning_days=7, critical_days=3)

    return {
        "total_products": len(df),
        "total_categories": int(df["category"].nunique()),
        "total_units_in_stock": int(df["total_available_stock"].sum()),
        "total_inventory_valuation": round(float(df["inventory_value"].sum()), 2),
        "low_stock_count": len(low_stock),
        "critical_expiry_count": len(expiry_data["critical_batches"]),
    }


def get_low_stock_alerts(db: Db2ConnectionManager = db_manager) -> List[Dict[str, Any]]:
    """Return products whose current stock is at or below reorder level."""
    rows = db.execute_query(QUERY_LOW_STOCK_PRODUCTS)
    alerts = []
    for r in rows:
        stock = int(r.get("total_stock", 0))
        reorder_lvl = int(r.get("reorder_level", 0))
        deficit = max(0, reorder_lvl - stock)
        alerts.append({
            "product_id": r["product_id"],
            "product_name": r["product_name"],
            "category": r["category"],
            "unit_price": float(r["unit_price"]),
            "current_stock": stock,
            "reorder_level": reorder_lvl,
            "deficit": deficit,
            "supplier_name": r.get("supplier_name", "N/A"),
            "contact_details": r.get("contact_details", "N/A"),
            "lead_time_days": int(r.get("lead_time_days", 1)),
        })
    return alerts


def get_stockout_risk_forecast(
    db: Db2ConnectionManager = db_manager,
    days_horizon: int = 3,
    sales_lookback_days: int = 7,
) -> List[Dict[str, Any]]:
    """Calculate days of stock remaining based on recent daily velocity.

    Flag items that will run out within `days_horizon` days.
    """
    today = date.today()
    since_date = (today - timedelta(days=sales_lookback_days)).isoformat()

    velocity_rows = db.execute_query(QUERY_SALES_VELOCITY, (sales_lookback_days, since_date))
    stock_df = get_current_stock_df(db)

    if stock_df.empty:
        return []

    stock_map = {row["product_id"]: row for _, row in stock_df.iterrows()}
    forecast = []

    for vr in velocity_rows:
        pid = vr["product_id"]
        if pid not in stock_map:
            continue

        prod_info = stock_map[pid]
        current_stock = int(prod_info["total_available_stock"])
        avg_daily = float(vr.get("avg_daily_sales") or 0.0)

        if avg_daily > 0:
            days_remaining = round(current_stock / avg_daily, 1)
        else:
            days_remaining = 999.0  # Zero sales recorded

        if days_remaining <= days_horizon:
            risk_level = "CRITICAL"
        elif days_remaining <= 7:
            risk_level = "MODERATE"
        else:
            risk_level = "SAFE"

        est_stockout_date = None
        if avg_daily > 0 and days_remaining < 999:
            est_stockout_date = (today + timedelta(days=int(math.ceil(days_remaining)))).isoformat()

        forecast.append({
            "product_id": pid,
            "product_name": vr["product_name"],
            "category": vr["category"],
            "current_stock": current_stock,
            "reorder_level": int(prod_info["reorder_level"]),
            "avg_daily_sales": avg_daily,
            "days_of_stock_remaining": days_remaining,
            "estimated_stockout_date": est_stockout_date,
            "risk_level": risk_level,
            "supplier_name": prod_info["supplier_name"],
            "lead_time_days": prod_info["lead_time_days"],
        })

    # Sort so most critical risk is top
    forecast.sort(key=lambda x: x["days_of_stock_remaining"])
    return forecast


def get_expiry_risk_analysis(
    db: Db2ConnectionManager = db_manager,
    warning_days: int = 7,
    critical_days: int = 3,
) -> Dict[str, Any]:
    """Examine batch-level expiry data and categorize by freshness & loss risk."""
    rows = db.execute_query(QUERY_BATCH_EXPIRY)
    today = date.today()

    critical_batches = []
    warning_batches = []
    safe_batches = []
    expired_batches = []
    total_at_risk_units = 0

    for r in rows:
        exp_date_raw = r["expiry_date"]
        if isinstance(exp_date_raw, str):
            exp_date = datetime.strptime(exp_date_raw[:10], "%Y-%m-%d").date()
        elif isinstance(exp_date_raw, (date, datetime)):
            exp_date = exp_date_raw if isinstance(exp_date_raw, date) else exp_date_raw.date()
        else:
            exp_date = today

        days_to_expiry = (exp_date - today).days
        qty = int(r["available_quantity"])

        batch_item = {
            "batch_id": r["batch_id"],
            "product_id": r["product_id"],
            "product_name": r["product_name"],
            "category": r["category"],
            "available_quantity": qty,
            "received_date": str(r["received_date"]),
            "expiry_date": str(exp_date),
            "days_to_expiry": days_to_expiry,
            "supplier_name": r.get("supplier_name", "N/A"),
        }

        if days_to_expiry < 0:
            batch_item["status"] = "EXPIRED"
            expired_batches.append(batch_item)
            total_at_risk_units += qty
        elif days_to_expiry <= critical_days:
            batch_item["status"] = "CRITICAL"
            critical_batches.append(batch_item)
            total_at_risk_units += qty
        elif days_to_expiry <= warning_days:
            batch_item["status"] = "WARNING"
            warning_batches.append(batch_item)
            total_at_risk_units += qty
        else:
            batch_item["status"] = "SAFE"
            safe_batches.append(batch_item)

    return {
        "critical_batches": critical_batches,
        "warning_batches": warning_batches,
        "safe_batches": safe_batches,
        "expired_batches": expired_batches,
        "total_at_risk_units": total_at_risk_units,
    }


def get_fast_and_slow_moving_products(
    db: Db2ConnectionManager = db_manager,
    lookback_days: int = 7,
    top_n: int = 5,
) -> Dict[str, List[Dict[str, Any]]]:
    """Rank products by quantity sold and revenue over the lookback window."""
    today = date.today()
    since_date = (today - timedelta(days=lookback_days)).isoformat()
    rows = db.execute_query(QUERY_SALES_VELOCITY, (lookback_days, since_date))

    items = []
    for r in rows:
        items.append({
            "product_id": r["product_id"],
            "product_name": r["product_name"],
            "category": r["category"],
            "total_quantity_sold": int(r.get("total_quantity_sold", 0)),
            "total_revenue": round(float(r.get("total_revenue", 0.0)), 2),
            "avg_daily_sales": float(r.get("avg_daily_sales", 0.0)),
        })

    # Sort descending for fast moving, ascending for slow moving
    fast_moving = sorted(items, key=lambda x: x["total_quantity_sold"], reverse=True)[:top_n]
    slow_moving = sorted(items, key=lambda x: x["total_quantity_sold"])[:top_n]

    return {
        "fast_moving": fast_moving,
        "slow_moving": slow_moving,
        "lookback_days": lookback_days,
    }


def get_reorder_recommendations(
    db: Db2ConnectionManager = db_manager,
    sales_lookback_days: int = 7,
    safety_buffer_ratio: float = 0.5,
) -> List[Dict[str, Any]]:
    """Deterministic reorder recommendation engine.

    Formula:
        Lead Time Demand = Average Daily Sales * Supplier Lead Time (Days)
        Safety Stock = Lead Time Demand * safety_buffer_ratio
        Target Stock = max(reorder_level, Lead Time Demand + Safety Stock)
        Recommended Reorder = max(0, Target Stock - Current Available Stock)
    """
    today = date.today()
    since_date = (today - timedelta(days=sales_lookback_days)).isoformat()

    velocity_rows = db.execute_query(QUERY_SALES_VELOCITY, (sales_lookback_days, since_date))
    stock_df = get_current_stock_df(db)

    if stock_df.empty:
        return []

    stock_map = {row["product_id"]: row for _, row in stock_df.iterrows()}
    recommendations = []

    for vr in velocity_rows:
        pid = vr["product_id"]
        if pid not in stock_map:
            continue

        prod = stock_map[pid]
        current_stock = int(prod["total_available_stock"])
        reorder_lvl = int(prod["reorder_level"])
        unit_price = float(prod["unit_price"])
        lead_time = int(prod["lead_time_days"])
        avg_daily = float(vr.get("avg_daily_sales") or 0.0)

        # Mathematical calculation
        lead_time_demand = avg_daily * lead_time
        safety_stock = math.ceil(lead_time_demand * safety_buffer_ratio)
        target_stock = max(reorder_lvl, math.ceil(lead_time_demand + safety_stock))
        reorder_qty = max(0, target_stock - current_stock)

        # Trigger if stock is low or reorder qty > 0
        if reorder_qty > 0 or current_stock <= reorder_lvl:
            # Ensure minimum sensible batch order if needed
            suggested_order = max(reorder_qty, reorder_lvl - current_stock)
            if suggested_order > 0:
                est_order_cost = round(suggested_order * unit_price, 2)
                urgency = "HIGH" if current_stock == 0 or current_stock < (reorder_lvl // 2) else "NORMAL"
                recommendations.append({
                    "product_id": pid,
                    "product_name": vr["product_name"],
                    "category": vr["category"],
                    "current_stock": current_stock,
                    "reorder_level": reorder_lvl,
                    "avg_daily_sales": avg_daily,
                    "supplier_name": prod["supplier_name"],
                    "lead_time_days": lead_time,
                    "recommended_order_quantity": int(suggested_order),
                    "estimated_purchase_cost": est_order_cost,
                    "urgency": urgency,
                })

    recommendations.sort(key=lambda x: (x["urgency"] != "HIGH", -x["recommended_order_quantity"]))
    return recommendations


def get_sales_trends_df(db: Db2ConnectionManager = db_manager) -> pd.DataFrame:
    """Fetch daily aggregated sales history for timeline charts."""
    rows = db.execute_query(QUERY_DAILY_SALES_TREND)
    df = pd.DataFrame(rows)
    if not df.empty:
        df["total_units_sold"] = df["total_units_sold"].astype(int)
        df["total_daily_revenue"] = df["total_daily_revenue"].astype(float)
        df["distinct_products_sold"] = df["distinct_products_sold"].astype(int)
    return df


def get_category_performance_df(db: Db2ConnectionManager = db_manager) -> pd.DataFrame:
    """Fetch sales and revenue broken down by product category."""
    rows = db.execute_query(QUERY_CATEGORY_PERFORMANCE)
    df = pd.DataFrame(rows)
    if not df.empty:
        df["units_sold"] = df["units_sold"].astype(int)
        df["category_revenue"] = df["category_revenue"].astype(float)
    return df

