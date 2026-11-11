from pydantic import BaseModel
from typing import Dict

class DashboardStatsResponse(BaseModel):
    counts_per_kind: Dict[str, int]
    closing_within_7_days: int
    total_active: int
