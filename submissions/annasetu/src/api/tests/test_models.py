from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from api.app.models import FoodCreate, VerifyStage


def food_payload(prepared_at: datetime, use_by: datetime) -> dict:
    return {
        "title": "Synthetic QA test batch",
        "category": "prepared meals",
        "quantity_kg": 1,
        "prepared_at": prepared_at,
        "use_by": use_by,
        "storage_type": "cold",
        "storage_temp_c": 4,
        "allergens": ["milk"],
        "allergens_confirmed": True,
        "ingredients": ["rice"],
        "pickup_address": "SYNTHETIC QA location",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "storage_note": "SYNTHETIC QA only",
    }


def test_food_create_rejects_use_by_at_or_before_preparation():
    prepared = datetime.now(timezone.utc) - timedelta(minutes=10)
    with pytest.raises(ValidationError, match="use_by must be later"):
        FoodCreate(**food_payload(prepared, prepared))


def test_food_create_rejects_future_preparation_time():
    prepared = datetime.now(timezone.utc) + timedelta(minutes=10)
    with pytest.raises(ValidationError, match="prepared_at cannot be in the future"):
        FoodCreate(**food_payload(prepared, prepared + timedelta(hours=1)))


def test_food_create_accepts_valid_synthetic_batch_times():
    prepared = datetime.now(timezone.utc) - timedelta(minutes=10)
    batch = FoodCreate(**food_payload(prepared, prepared + timedelta(hours=1)))
    assert batch.use_by > batch.prepared_at


def test_distribution_checkpoint_requires_actual_quantity():
    with pytest.raises(ValidationError, match="actual_distributed_kg is required"):
        VerifyStage(stage="distribution", otp="123456")


def test_distribution_quantity_is_only_valid_for_distribution_stage():
    with pytest.raises(ValidationError, match="only accepted for distribution"):
        VerifyStage(stage="pickup", otp="123456", actual_distributed_kg=1.0)
