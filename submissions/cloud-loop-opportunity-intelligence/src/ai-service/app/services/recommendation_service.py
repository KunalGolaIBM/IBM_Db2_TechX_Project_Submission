from typing import List, Dict, Any, Optional
from app.repositories.opportunity_repository import opportunity_repo
from app.repositories.profile_repository import profile_repo
from app.services.eligibility_service import eligibility_service
from app.ai.embeddings import generate_embedding
from app.ai.vector_search import cosine_similarity
from app.ai.match_explainer import generate_match_explanation
from app.schemas.recommendation import RecommendationItem, MatchExplanation
from app.schemas.opportunity import OpportunityResponse

class RecommendationService:
    def get_recommendations(
        self,
        user_id: Optional[str] = None,
        limit: int = 6
    ) -> List[RecommendationItem]:
        # 1. Fetch profile or fallback default
        profile = None
        if user_id:
            profile = profile_repo.get_by_user_id(user_id)

        if not profile:
            profile = {
                "degree": "B.Tech / B.E.",
                "study_year": 3,
                "graduation_batch": "2026",
                "skills": ["Python", "JavaScript", "React", "Cloud", "Git"],
                "interests": ["Full Stack", "AI/ML", "Cloud Computing"],
                "preferred_domains": ["Software", "Cloud", "AI/ML", "Open Source"],
                "preferred_locations": ["Remote", "Bengaluru", "Hyderabad"],
            }

        user_skills = set(s.lower() for s in (profile.get("skills") or []))
        preferred_domains = set(d.lower() for d in (profile.get("preferred_domains") or []))
        profile_text = f"{' '.join(profile.get('skills') or [])} {' '.join(profile.get('interests') or [])} {' '.join(profile.get('preferred_domains') or [])}"
        profile_vec = generate_embedding(profile_text)

        # 2. Candidate generation from Db2 / repository
        all_opportunities, _ = opportunity_repo.list_opportunities(limit=150)

        scored_items = []
        for opp in all_opportunities:
            deadline_status = eligibility_service.check_deadline_status(opp.get("deadline"))
            if deadline_status == "expired":
                continue

            # Deterministic criteria
            is_eligible, _ = eligibility_service.check_eligibility(opp, profile)
            opp_skills = opp.get("skills") or []
            matched_skills = [s for s in opp_skills if s.lower() in user_skills]

            cat = (opp.get("category") or "").lower()
            domain_match = any(d in cat or cat in d for d in preferred_domains)

            # AI Semantic Vector Similarity (384-dim)
            opp_text = f"{opp.get('title', '')} {opp.get('organization', '')} {opp.get('category', '')} {' '.join(opp_skills)} {opp.get('description', '')}"
            opp_vec = generate_embedding(opp_text)
            sim_score = cosine_similarity(profile_vec, opp_vec) # 0.0 to 1.0

            # Composite Multi-Factor Scoring (0 to 100)
            score = 30.0 # Base score for active verified opportunity

            # Skills overlap: up to 35 points
            if opp_skills:
                skill_ratio = min(1.0, len(matched_skills) / max(1, len(opp_skills)))
                score += skill_ratio * 35.0
            else:
                score += 15.0

            # Semantic Vector Similarity: up to 20 points
            score += sim_score * 20.0

            # Domain preference: 10 points
            if domain_match:
                score += 10.0

            # Eligibility pass: 5 points
            if is_eligible:
                score += 5.0
            else:
                score -= 15.0 # Eligibility penalty

            final_score = round(max(10.0, min(99.0, score)), 1)

            # Generate transparent explanation
            explanation = generate_match_explanation(
                opportunity=opp,
                profile=profile,
                skills_overlap=matched_skills,
                eligibility_met=is_eligible,
                domain_match=domain_match,
                deadline_status=deadline_status,
            )

            scored_items.append({
                "opportunity": OpportunityResponse(**opp),
                "match_score": final_score,
                "explanation": explanation,
            })

        scored_items.sort(key=lambda x: x["match_score"], reverse=True)
        return [
            RecommendationItem(
                opportunity=item["opportunity"],
                match_score=item["match_score"],
                explanation=item["explanation"],
            )
            for item in scored_items[:limit]
        ]

recommendation_service = RecommendationService()

