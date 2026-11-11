from typing import Optional, Dict, Any, List
from app.repositories.opportunity_repository import opportunity_repo

class OpportunityService:
    def get_opportunity(self, opportunity_id: str) -> Optional[Dict[str, Any]]:
        # Try ID, then slug
        opp = opportunity_repo.get_by_id(opportunity_id)
        if not opp:
            opp = opportunity_repo.get_by_slug(opportunity_id)
        return opp

    def list_opportunities(
        self,
        opp_type: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> (List[Dict[str, Any]], int):
        return opportunity_repo.list_opportunities(
            opp_type=opp_type,
            category=category,
            search=search,
            page=page,
            limit=limit,
        )

opportunity_service = OpportunityService()

