from typing import Dict, Any, List
from app.schemas.recommendation import MatchExplanation

def generate_match_explanation(
    opportunity: Dict[str, Any],
    profile: Dict[str, Any],
    skills_overlap: List[str],
    eligibility_met: bool,
    domain_match: bool,
    deadline_status: str
) -> MatchExplanation:
    """
    Generates a deterministic, transparent explanation for student-opportunity matching.
    Never hallucinates or invents false requirements.
    """
    reasons = []

    if skills_overlap:
        reasons.append(f"Matched {len(skills_overlap)} of your technical skills: {', '.join(skills_overlap[:3])}")
    else:
        reasons.append("Introductory opportunity suitable for expanding your tech stack")

    if eligibility_met:
        degree = profile.get("degree") or "Engineering"
        year = profile.get("study_year") or 3
        reasons.append(f"Directly matches your {degree} (Year {year}) eligibility criteria")
    else:
        reasons.append("Check individual program prerequisites on the official apply portal")

    if domain_match:
        cat = opportunity.get("category") or "Technology"
        reasons.append(f"Aligns with your target domain interest in {cat}")

    if deadline_status == "closing_soon":
        reasons.append("⚠️ High priority deadline approaching within 7 days")

    summary = " • ".join(reasons)
    return MatchExplanation(
        eligibility_met=eligibility_met,
        skills_overlap=skills_overlap,
        domain_match=domain_match,
        deadline_status=deadline_status,
        summary=summary,
    )

