"""Unit tests for Normalization and Unit Conversion Service."""
from datetime import date, timedelta
from recipe_waste_optimizer.services.normalization import (
    normalize_ingredient_name,
    normalize_unit,
    are_units_compatible,
    convert_quantity,
    calculate_expiry_status
)


def test_ingredient_normalization():
    assert normalize_ingredient_name("Tomatoes") == "tomato"
    assert normalize_ingredient_name("roma tomato") == "tomato"
    assert normalize_ingredient_name("cherry tomatoes") == "tomato"
    assert normalize_ingredient_name("Spinach leaves") == "spinach"
    assert normalize_ingredient_name("baby spinach") == "spinach"
    assert normalize_ingredient_name("Potatoes") == "potato"
    assert normalize_ingredient_name("Onions") == "onion"
    assert normalize_ingredient_name("coriander leaves") == "cilantro"
    assert normalize_ingredient_name("chicken egg") == "eggs"


def test_unit_normalization():
    assert normalize_unit("Grams") == "g"
    assert normalize_unit("kg") == "kg"
    assert normalize_unit("milliliters") == "ml"
    assert normalize_unit("Litres") == "l"
    assert normalize_unit("pcs") == "pieces"
    assert normalize_unit("clove") == "cloves"


def test_unit_compatibility():
    assert are_units_compatible("g", "kg") is True
    assert are_units_compatible("ml", "l") is True
    assert are_units_compatible("tbsp", "ml") is True
    assert are_units_compatible("g", "pieces") is False
    assert are_units_compatible("ml", "g") is False


def test_quantity_conversion():
    # Weight conversions
    assert convert_quantity(1.5, "kg", "g") == 1500.0
    assert convert_quantity(500, "g", "kg") == 0.5

    # Volume conversions
    assert convert_quantity(1.0, "l", "ml") == 1000.0
    assert convert_quantity(250, "ml", "l") == 0.25
    assert convert_quantity(2, "tbsp", "ml") == 30.0

    # Incompatible conversions
    assert convert_quantity(3, "pieces", "g") is None


def test_expiry_status_calculation():
    today = date(2026, 11, 5)

    # Expired yesterday
    days, status = calculate_expiry_status(today - timedelta(days=1), ref_date=today)
    assert days == -1
    assert status == "expired"

    # Urgent: 1 day left
    days, status = calculate_expiry_status(today + timedelta(days=1), ref_date=today)
    assert days == 1
    assert status == "urgent"

    # Approaching: 4 days left
    days, status = calculate_expiry_status(today + timedelta(days=4), ref_date=today)
    assert days == 4
    assert status == "approaching"

    # Safe: 10 days left
    days, status = calculate_expiry_status(today + timedelta(days=10), ref_date=today)
    assert days == 10
    assert status == "safe"

    # None provided
    days, status = calculate_expiry_status(None, ref_date=today)
    assert days is None
    assert status == "unknown"
