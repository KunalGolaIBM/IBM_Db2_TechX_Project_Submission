from datetime import date, timedelta
from src.models import InventoryItem
from src.agent import assess_item, draft_recommendation
from src.repository import DemoRepository

def test_stockout_risk_when_cover_below_lead_time():
    item = InventoryItem(medicine_id="X", medicine_name="Test med", on_hand=100, reorder_level=20,
        avg_daily_use=20, supplier_lead_days=8)
    finding = assess_item(item)
    assert finding.stockout_risk is True
    assert finding.days_of_cover == 5.0

def test_expiry_risk_is_reported():
    item = InventoryItem(medicine_id="X", medicine_name="Test med", on_hand=100, reorder_level=20,
        avg_daily_use=5, supplier_lead_days=4, nearest_expiry=date.today()+timedelta(days=10),
        expiring_quantity=25)
    finding = assess_item(item)
    assert finding.expiry_risk is True
    assert any("25 units" in reason for reason in finding.reasons)

def test_recommendation_starts_pending():
    item = InventoryItem(medicine_id="X", medicine_name="Test med", on_hand=100, reorder_level=200,
        avg_daily_use=10, supplier_lead_days=5)
    rec = draft_recommendation(item, assess_item(item))
    assert rec.suggested_quantity >= 0
    assert rec.status == "PENDING_REVIEW"

def test_demo_repository_records_review():
    repo = DemoRepository()
    item = repo.list_inventory()[0]
    rec = draft_recommendation(item, assess_item(item))
    repo.save_recommendation(rec)
    updated = repo.review_recommendation(rec.recommendation_id, "APPROVED", "Reviewer", rec.suggested_quantity)
    assert updated.status == "APPROVED"
    assert repo.events[-1]["reviewer"] == "Reviewer"
