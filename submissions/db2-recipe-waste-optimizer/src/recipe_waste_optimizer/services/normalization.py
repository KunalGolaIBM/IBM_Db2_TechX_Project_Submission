"""Deterministic Ingredient Normalization and Unit Conversion Service.

Provides conservative name canonicalization, singularization,
and strict compatible unit conversion rules.
"""
from datetime import date
from typing import Tuple, Optional


# Canonical Aliases mapping: synonym -> canonical_name
COMMON_ALIASES = {
    "tomatoes": "tomato",
    "roma tomato": "tomato",
    "cherry tomatoes": "tomato",
    "potatoes": "potato",
    "russet potato": "potato",
    "onions": "onion",
    "red onion": "onion",
    "yellow onion": "onion",
    "shallot": "onion",
    "garlic clove": "garlic",
    "garlic cloves": "garlic",
    "spinach leaves": "spinach",
    "baby spinach": "spinach",
    "palak": "spinach",
    "coriander": "cilantro",
    "coriander leaves": "cilantro",
    "green chili": "green chilli",
    "chillies": "green chilli",
    "egg": "eggs",
    "chicken egg": "eggs",
    "cooking oil": "cooking oil",
    "vegetable oil": "cooking oil",
    "sunflower oil": "cooking oil",
    "olive oil": "cooking oil",
    "curry powder": "curry powder",
    "turmeric powder": "turmeric",
    "black pepper": "black pepper",
    "peppercorns": "black pepper",
    "toor dal": "lentils",
    "moong dal": "lentils",
    "red lentils": "lentils",
    "yellow lentils": "lentils",
}

# Unit normalizations
UNIT_ALIASES = {
    "g": "g",
    "gram": "g",
    "grams": "g",
    "gm": "g",
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "ml": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "l": "l",
    "liter": "l",
    "liters": "l",
    "litre": "l",
    "litres": "l",
    "piece": "pieces",
    "pieces": "pieces",
    "pc": "pieces",
    "pcs": "pieces",
    "item": "pieces",
    "items": "pieces",
    "clove": "cloves",
    "cloves": "cloves",
    "tbsp": "tbsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tsp": "tsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "cup": "cup",
    "cups": "cup",
}

# Unit conversion factors to base unit
# Base units: weight -> 'g', volume -> 'ml', count -> 'pieces'
WEIGHT_UNITS = {
    "g": 1.0,
    "kg": 1000.0,
}

VOLUME_UNITS = {
    "ml": 1.0,
    "l": 1000.0,
    "tsp": 5.0,
    "tbsp": 15.0,
    "cup": 240.0,
}

COUNT_UNITS = {
    "pieces": 1.0,
    "cloves": 1.0,
}


def normalize_ingredient_name(name: str) -> str:
    """Normalize raw ingredient name to canonical representation."""
    cleaned = name.strip().lower()
    if cleaned in COMMON_ALIASES:
        return COMMON_ALIASES[cleaned]
    # Simple singularization
    if cleaned.endswith("ies") and len(cleaned) > 4:
        cand = cleaned[:-3] + "y"
        if cand in COMMON_ALIASES:
            return COMMON_ALIASES[cand]
    if cleaned.endswith("es") and len(cleaned) > 4 and not cleaned.endswith("cloves"):
        cand = cleaned[:-2]
        if cand in COMMON_ALIASES:
            return COMMON_ALIASES[cand]
    if cleaned.endswith("s") and len(cleaned) > 3 and not cleaned.endswith("eggs"):
        cand = cleaned[:-1]
        if cand in COMMON_ALIASES:
            return COMMON_ALIASES[cand]
        return cand
    return cleaned


def normalize_unit(unit: str) -> str:
    """Normalize unit string."""
    cleaned = unit.strip().lower()
    return UNIT_ALIASES.get(cleaned, cleaned)


def are_units_compatible(unit_a: str, unit_b: str) -> bool:
    """Check if two units belong to the same measurable dimension."""
    ua = normalize_unit(unit_a)
    ub = normalize_unit(unit_b)
    if ua == ub:
        return True
    if ua in WEIGHT_UNITS and ub in WEIGHT_UNITS:
        return True
    if ua in VOLUME_UNITS and ub in VOLUME_UNITS:
        return True
    return False


def convert_quantity(quantity: float, from_unit: str, to_unit: str) -> Optional[float]:
    """Convert quantity between compatible units. Returns None if incompatible."""
    fu = normalize_unit(from_unit)
    tu = normalize_unit(to_unit)
    if fu == tu:
        return quantity

    if fu in WEIGHT_UNITS and tu in WEIGHT_UNITS:
        base_g = quantity * WEIGHT_UNITS[fu]
        return round(base_g / WEIGHT_UNITS[tu], 4)

    if fu in VOLUME_UNITS and tu in VOLUME_UNITS:
        base_ml = quantity * VOLUME_UNITS[fu]
        return round(base_ml / VOLUME_UNITS[tu], 4)

    return None


def calculate_expiry_status(expiry_date: Optional[date], ref_date: Optional[date] = None) -> Tuple[Optional[int], str]:
    """Calculate days until expiry and semantic status."""
    if not expiry_date:
        return None, "unknown"
    today = ref_date or date.today()
    days = (expiry_date - today).days
    if days < 0:
        return days, "expired"
    elif days <= 2:
        return days, "urgent"
    elif days <= 5:
        return days, "approaching"
    else:
        return days, "safe"
