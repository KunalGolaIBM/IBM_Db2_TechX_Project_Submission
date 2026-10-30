"""Explainable rules engine. Travel estimates are fictional static demo values."""
from datetime import datetime

SAFETY_FIELDS = {
    "handling_verified": "Human handling checks are not verified.",
    "temperature_verified": "Storage temperature has not been verified by a human.",
    "packaging_verified": "Packaging integrity has not been verified by a human.",
    "local_requirements_verified": "Applicable local requirements have not been verified by a human.",
}

def assess_risk(listing: dict, candidates: list[dict], rejected: list[dict], volunteer_available_count: int = 0) -> dict:
    """Score observed blockers with transparent weights; this is not a trained model."""
    reasons = []
    score = 0
    best = candidates[0] if candidates else None
    if not best:
        # An unavailable rescue path is inherently risky, but the final score
        # must also reflect which real rules blocked the current candidates.
        score += 50
        reasons.append("No recipient currently meets every configured eligibility rule (50 points).")
        if not rejected:
            score += 20
            reasons.append("No active, approved recipient organization is available to evaluate (20 points).")
        total = max(1, len(rejected))
        operational_rules = (
            ("availability", 15, "currently unavailable"),
            ("capacity", 20, "Capacity is configured"),
            ("pickup deadline", 25, "Estimated travel is"),
            ("food category", 15, "Food category"),
        )
        for label, weight, marker in operational_rules:
            affected = sum(any(marker.casefold() in reason.casefold() for reason in item.get("reasons", []))
                           for item in rejected)
            if affected:
                points = round(weight * affected / total)
                score += points
                reasons.append(f"{label.capitalize()} blocks {affected} of {total} reviewed recipient(s) ({points} points).")

    else:
        margin = best.get("time_margin_minutes", 0)
        if margin <= 15:
            score += 50
            reasons.append(f"Only {margin} minutes remain after the simulated travel estimate.")
        elif margin <= 45:
            score += 30
            reasons.append(f"The simulated pickup margin is tight at {margin} minutes.")
        elif margin <= 120:
            score += 15
            reasons.append(f"Pickup is feasible, with a moderate {margin}-minute time margin.")
        if best.get("capacity_after", 0) < max(5, int(listing["portions"] * 0.1)):
            score += 15
            reasons.append("The top-ranked recipient has little spare configured capacity after this reservation.")
        if len(candidates) == 1:
            score += 15
            reasons.append("There is no second feasible recipient as a fallback.")
    if listing.get("demo"):
        points = 12 * len(SAFETY_FIELDS)
        score += points
        reasons.append(
            f"Fictional demo inputs have no human verification for {len(SAFETY_FIELDS)} required checks ({points} points); simulation only."
        )
    else:
        safety = listing.get("safety", {})
        missing_safety = [message for key, message in SAFETY_FIELDS.items() if not safety.get(key, False)]
        if missing_safety:
            points = 12 * len(missing_safety)
            score += points
            reasons.extend(f"{message} ({12} points)." for message in missing_safety)
        if not missing_safety and not listing.get("safety_verified_by", "").strip():
            score += 8
            reasons.append("Responsible human verifier name is missing (8 points).")
    if volunteer_available_count <= 0:
        score += 15
        reasons.append("No approved volunteer has a currently usable availability profile; volunteer schedules are not live-tracked.")
    score = min(100, score)
    category = "High" if score >= 60 else "Medium" if score >= 30 else "Low"
    return {
        "category": category,
        "score": score,
        "reasons": list(dict.fromkeys(reasons)) or ["The current configured recipient and deadline checks show a low operational risk."],
        "deadline_margin_minutes": best.get("time_margin_minutes") if best else None,
        "volunteer_available_count": max(0, int(volunteer_available_count)),
        "alternative_recipient_ids": [candidate["id"] for candidate in candidates[1:]],
        "method": "Transparent rule-based assessment; not a trained AI model. Travel estimates are simulated.",
    }


def evaluate(listing: dict, recipients: list[dict], excluded_recipient_ids: set[int] | None = None,
             volunteer_available_count: int = 0) -> dict:
    excluded_recipient_ids = excluded_recipient_ids or set()
    now = datetime.now()
    deadline = datetime.fromisoformat(listing["deadline"])
    if deadline.tzinfo is not None and deadline.utcoffset() is not None:
        raise ValueError("Deadline must be a local time without a timezone offset.")
    remaining = (deadline - now).total_seconds() / 60
    safety = listing["safety"]
    failed_safety = [message for key, message in SAFETY_FIELDS.items() if not safety.get(key, False)]
    simulation_only = bool(listing.get("demo"))
    if simulation_only:
        # Fictional fixtures exercise the matching workflow, but their
        # synthetic fields can never count as human food-safety verification.
        failed_safety = []
    elif not failed_safety and not listing.get("safety_verified_by", "").strip():
        failed_safety.append("Responsible human verifier name is missing.")
    candidates, rejected = [], []
    for rec in recipients:
        reasons = []
        if not rec["available"]:
            reasons.append("Recipient is currently unavailable.")
        elif rec["id"] in excluded_recipient_ids:
            reasons.append("Recipient already rejected this listing offer.")
        available_capacity = rec.get("available_capacity", rec["capacity"])
        if available_capacity < listing["portions"]:
            reasons.append(f"Capacity is configured for {rec['capacity']} portions; {available_capacity} remain after active reservations, but {listing['portions']} are required.")
        if remaining <= 0 or rec["travel_minutes"] > remaining:
            reasons.append(f"Estimated travel is {rec['travel_minutes']} min, but only {max(0,int(remaining))} min remain before deadline.")
        categories = rec.get("food_categories", [])
        if listing["food_type"] not in categories:
            reasons.append(f"Food category '{listing['food_type']}' is not accepted by this recipient.")
        if failed_safety:
            reasons.extend(failed_safety)
        item = {**rec, "available_capacity": available_capacity, "capacity_after": available_capacity - listing["portions"],
                "time_margin_minutes": max(0, int(remaining - rec["travel_minutes"])),
                "travel_estimate_label": "Simulated estimate"}
        if reasons:
            rejected.append({**item, "feasible": False, "reasons": reasons})
        else:
            # Lower score is better: travel time first, with a small spare-capacity penalty.
            item["_score"] = rec["travel_minutes"] + 12 * (available_capacity - listing["portions"]) / max(1, available_capacity)
            candidates.append(item)
    candidates.sort(key=lambda r: (r["_score"], r["travel_minutes"], r["id"]))
    for rank, item in enumerate(candidates, 1):
        item["rank"] = rank
        item["feasible"] = True
        item.pop("_score")
    if candidates and simulation_only:
        explanation = (
            f"{len(candidates)} fictional recipient(s) meet the configured availability, capacity, deadline, and category rules for simulation only. "
            "Required human food-safety verification is incomplete; this result does not make the listing operationally eligible."
        )
    elif candidates:
        explanation = f"{len(candidates)} recipient(s) meet availability, capacity, deadline, category, and human safety checks."
    else:
        detail = []
        if failed_safety:
            detail.append("A responsible human must complete or verify: " + "; ".join(failed_safety))
        operational_reasons = list(dict.fromkeys(
            reason for item in rejected for reason in item["reasons"]
            if reason not in failed_safety
        ))
        if operational_reasons:
            detail.append("Other candidate-specific blockers: " + "; ".join(operational_reasons[:4]))
        if not detail:
            detail.append("An active, approved recipient organization must be available for evaluation.")
        explanation = "No recipient meets all configured operational and human safety checks. " + " ".join(detail) + " Recalculate after verified changes."
    return {"feasible": bool(candidates), "recommended": candidates[0] if candidates else None,
            "alternative": candidates[1] if len(candidates) > 1 else None,
            "feasible_candidates": candidates, "rejected_candidates": rejected,
            "remaining_minutes": max(0, int(remaining)),
            "food_safety_passed": not simulation_only and not failed_safety,
            "simulation_only": simulation_only,
            "risk_assessment": assess_risk(listing, candidates, rejected, volunteer_available_count),
            "explanation": explanation}
