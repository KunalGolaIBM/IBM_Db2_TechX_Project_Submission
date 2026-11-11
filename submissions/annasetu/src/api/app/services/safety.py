from dataclasses import dataclass
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt


@dataclass(frozen=True)
class SafetyEvidence:
    human_verified: bool
    verification_recorded: bool
    allergens_confirmed: bool
    storage_type: str
    storage_temp_c: float | None
    use_by: datetime
    transit_minutes: int | None


@dataclass(frozen=True)
class Feasibility:
    status: str
    reasons: tuple[str, ...]
    remaining_minutes: int | None
    estimated_transit_minutes: int | None
    estimate_label: str = "Estimated; confirm with the assigned volunteer"


def estimate_transit_minutes(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> int:
    """Straight-line distance at 20 km/h plus a 15-minute handoff allowance."""
    return 15 + round(estimate_distance_km(lat_a, lon_a, lat_b, lon_b) / 20 * 60)


def estimate_distance_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (lat_a, lon_a, lat_b, lon_b))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    haversine = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(haversine))


def evaluate_safety(evidence: SafetyEvidence, now: datetime | None = None) -> Feasibility:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    expiry = evidence.use_by.replace(tzinfo=timezone.utc) if evidence.use_by.tzinfo is None else evidence.use_by
    reasons: list[str] = []
    holds: list[str] = []

    if not evidence.human_verified or not evidence.verification_recorded:
        holds.append("A human verifier has not approved this batch.")
    if not evidence.allergens_confirmed:
        holds.append("Allergen declaration is missing or unconfirmed.")
    if evidence.storage_temp_c is None:
        holds.append("No recorded storage temperature is available.")
    elif evidence.storage_type == "cold" and evidence.storage_temp_c > 5:
        holds.append("Cold storage is outside the ≤5°C policy threshold.")
    elif evidence.storage_type == "hot" and evidence.storage_temp_c < 60:
        holds.append("Hot holding is below the 60°C policy threshold.")
    elif evidence.storage_type == "frozen" and evidence.storage_temp_c > -18:
        holds.append("Frozen storage is warmer than the −18°C policy threshold.")
    elif evidence.storage_type == "ambient":
        holds.append("Ambient storage is not eligible in this MVP policy profile.")
    if evidence.transit_minutes is None:
        holds.append("A receiving location is needed to estimate delivery time.")

    remaining = round((expiry - now).total_seconds() / 60)
    if remaining <= 0:
        return Feasibility("INFEASIBLE", ("The declared use-by time has passed.",), remaining, evidence.transit_minutes)
    if evidence.transit_minutes is not None and remaining <= evidence.transit_minutes:
        reasons.append("Estimated transit exceeds the remaining declared usable time.")
        return Feasibility("INFEASIBLE", tuple(reasons), remaining, evidence.transit_minutes)
    if holds:
        return Feasibility("HOLD", tuple(holds), remaining, evidence.transit_minutes)
    reasons.append("Required evidence is present and estimated transit fits before the declared use-by time.")
    reasons.append("This is a logistics feasibility result, not a food-safety certification.")
    return Feasibility("FEASIBLE", tuple(reasons), remaining, evidence.transit_minutes)
