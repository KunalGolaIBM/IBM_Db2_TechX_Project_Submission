import re
from typing import Dict, Any, Tuple
from datetime import datetime

class EligibilityService:
    """
    Deterministic eligibility verification for student opportunities.
    Prevents hallucinated or fabricated qualifications.
    """
    def check_eligibility(self, opportunity: Dict[str, Any], profile: Dict[str, Any]) -> Tuple[bool, str]:
        eligibility_str = (opportunity.get("eligibility") or "").lower()
        opp_type = (opportunity.get("opportunity_type") or "").lower()
        batch = str(profile.get("graduation_batch") or "")
        study_year = profile.get("study_year") or 3

        # Default is eligible unless explicit constraint violated
        is_eligible = True
        notes = []

        # Check Year / Role constraints
        if "intern" in opp_type and study_year > 4:
            is_eligible = False
            notes.append("Internships typically reserved for currently enrolled undergraduate/postgraduate students.")

        if "job" in opp_type and study_year < 3:
            # Junior year students should prioritize internships
            notes.append("Full-time roles typically require graduating batch status.")

        # Batch check if explicitly in eligibility string
        if batch and eligibility_str:
            if "202" in eligibility_str and batch not in eligibility_str:
                # If eligibility specifies a specific year different from student batch
                year_matches = re.findall(r"202[0-9]", eligibility_str)
                if year_matches and batch not in year_matches:
                    is_eligible = False
                    notes.append(f"Opportunity specifies batch {', '.join(year_matches)}.")

        return is_eligible, (" • ".join(notes) if notes else "Fully eligible based on student academic profile.")

    def check_deadline_status(self, deadline: str) -> str:
        if not deadline or deadline.lower() in ["ongoing", "rolling", "open"]:
            return "ongoing"
        try:
            d_date = datetime.strptime(deadline[:10], "%Y-%m-%d")
            diff = (d_date - datetime.now()).days
            if diff < 0:
                return "expired"
            elif diff <= 7:
                return "closing_soon"
            return "open"
        except Exception:
            return "open"

eligibility_service = EligibilityService()

