"""Unit tests for StockSage deterministic inventory calculations."""

import pytest
from src.db_connection import db_manager
from src.database_setup import initialize_database
from src.inventory_tools import (
    get_current_stock_df,
    get_expiry_risk_analysis,
    get_fast_and_slow_moving_products,
    get_inventory_health_summary,
    get_low_stock_alerts,
    get_reorder_recommendations,
    get_stockout_risk_forecast,
)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    """Ensure database has clean schema and seeded data before running tests."""
    initialize_database(db_manager, force_recreate=True)
    yield


def test_inventory_health_summary():
    """Test KPI summary returns positive values and accurate counts."""
    summary = get_inventory_health_summary(db_manager)
    assert summary["total_products"] > 0
    assert summary["total_categories"] >= 4
    assert summary["total_units_in_stock"] > 0
    assert summary["total_inventory_valuation"] > 0.0
    assert "low_stock_count" in summary
    assert "critical_expiry_count" in summary


def test_current_stock_dataframe():
    """Test current stock DataFrame structure and data types."""
    df = get_current_stock_df(db_manager)
    assert not df.empty
    assert "product_id" in df.columns
    assert "total_available_stock" in df.columns
    assert "reorder_level" in df.columns
    assert "inventory_value" in df.columns
    assert all(df["total_available_stock"] >= 0)


def test_low_stock_alerts():
    """Test that low stock alerts accurately flag products at or below reorder level."""
    alerts = get_low_stock_alerts(db_manager)
    assert isinstance(alerts, list)
    for alert in alerts:
        assert alert["current_stock"] <= alert["reorder_level"]
        assert alert["deficit"] >= 0
        assert "supplier_name" in alert
        assert "lead_time_days" in alert


def test_stockout_risk_forecast():
    """Test days of inventory remaining calculation and risk categorization."""
    forecast = get_stockout_risk_forecast(db_manager, days_horizon=3)
    assert isinstance(forecast, list)
    assert len(forecast) > 0
    for item in forecast:
        assert item["risk_level"] in ["CRITICAL", "MODERATE", "SAFE"]
        assert item["days_of_stock_remaining"] >= 0
        if item["risk_level"] == "CRITICAL":
            assert item["days_of_stock_remaining"] <= 3.0


def test_expiry_risk_analysis():
    """Test batch-level expiry countdown and classification."""
    expiry = get_expiry_risk_analysis(db_manager, warning_days=7, critical_days=3)
    assert "critical_batches" in expiry
    assert "warning_batches" in expiry
    assert "safe_batches" in expiry

    for batch in expiry["critical_batches"]:
        assert batch["days_to_expiry"] <= 3

    for batch in expiry["warning_batches"]:
        assert 3 < batch["days_to_expiry"] <= 7


def test_fast_and_slow_moving_rankings():
    """Test sales velocity rankings."""
    vel = get_fast_and_slow_moving_products(db_manager, lookback_days=7, top_n=5)
    fast = vel["fast_moving"]
    slow = vel["slow_moving"]

    assert len(fast) <= 5
    assert len(slow) <= 5
    assert fast[0]["total_quantity_sold"] >= fast[-1]["total_quantity_sold"]
    assert slow[0]["total_quantity_sold"] <= slow[-1]["total_quantity_sold"]


def test_reorder_recommendations_formula():
    """Test deterministic reorder recommendations logic."""
    reorders = get_reorder_recommendations(db_manager, sales_lookback_days=7)
    assert isinstance(reorders, list)
    for r in reorders:
        assert r["recommended_order_quantity"] > 0
        assert r["estimated_purchase_cost"] > 0.0
        assert r["urgency"] in ["HIGH", "NORMAL"]
        assert "supplier_name" in r

