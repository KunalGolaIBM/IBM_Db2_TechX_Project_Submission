import logging
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from app.core.config import settings
from app.repositories.opportunity_repository import opportunity_repo
from app.ai.embeddings import generate_embedding
from app.ai.vector_search import cosine_similarity

logger = logging.getLogger("cloud_loop.service.match")

class MatchService:
    async def _try_generate_llm_why(
        self,
        opportunity_title: str,
        opportunity_org: str,
        matched_skills: List[str],
        user_skills: List[str],
        year: Optional[str]
    ) -> Optional[str]:
        """
        Attempts to call Ollama (or OpenAI compatible local endpoint) to draft
        a personalized 1-sentence explanation of why this opportunity matches.
        """
        if not settings.OLLAMA_BASE_URL:
            return None

        prompt = (
            f"You are a career mentor for college students. Explain in exactly ONE concise sentence "
            f"why the opportunity '{opportunity_title}' at '{opportunity_org}' matches a student "
            f"with skills: {', '.join(user_skills)} (overlapping: {', '.join(matched_skills)}). "
            f"Keep it professional, encouraging, and under 25 words."
        )

        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                res = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/chat/completions",
                    json={
                        "model": settings.OLLAMA_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 50,
                        "temperature": 0.3,
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    if content:
                        return content
        except Exception as e:
            logger.debug(f"Ollama local LLM offline or timed out ({e}); proceeding with deterministic why line.")
        return None

    def _build_deterministic_why(
        self,
        opportunity_title: str,
        opportunity_org: str,
        matched_skills: List[str],
        user_skills: List[str],
        year: Optional[str]
    ) -> str:
        """
        Builds a crisp, deterministic explanation grounded in exact skill overlaps.
        """
        if matched_skills:
            if len(matched_skills) == 1:
                return f"Direct match for your core skill in {matched_skills[0]} at {opportunity_org}."
            elif len(matched_skills) <= 3:
                return f"Strong alignment with your profile in {', '.join(matched_skills)}."
            else:
                return f"Exceptional multi-skill match covering {len(matched_skills)} of your competencies ({', '.join(matched_skills[:3])} + more)."
        return f"Broad profile relevance based on your student tech background and current {opportunity_org} focus."

    async def match_opportunities(
        self,
        skills: List[str],
        interests: Optional[List[str]] = None,
        year: Optional[str] = None,
        limit: int = 6
    ) -> Dict[str, Any]:
        interests = interests or []
        user_skills_clean = [s.strip() for s in skills if s.strip()]
        user_skills_lower = set(s.lower() for s in user_skills_clean)
        interests_lower = set(i.lower() for i in interests if i.strip())

        # Construct profile semantic vector
        profile_text = f"{' '.join(user_skills_clean)} {' '.join(interests)} {year or ''}"
        profile_vec = generate_embedding(profile_text)

        # Retrieve active opportunities
        all_opps, _ = opportunity_repo.list_opportunities(limit=100, include_synthetic=False)

        scored_items = []
        today_str = date.today().isoformat()

        for opp in all_opps:
            # Check deadline - drop expired
            dl = opp.get("deadline")
            if dl and dl < today_str:
                continue

            opp_skills = opp.get("skills") or []
            matched = [s for s in opp_skills if s.lower() in user_skills_lower]

            # Vector similarity
            opp_text = f"{opp.get('title')} {opp.get('org')} {' '.join(opp_skills)} {opp.get('description', '')}"
            opp_vec = generate_embedding(opp_text)
            sim = cosine_similarity(profile_vec, opp_vec)

            # Combined match score (0.0 to 100.0)
            skill_ratio = (len(matched) / max(1, len(user_skills_lower))) if user_skills_lower else 0.0
            score = (sim * 55.0) + (min(1.0, skill_ratio) * 45.0)
            match_percentage = min(99.0, max(25.0, round(score, 1)))

            scored_items.append({
                "opportunity": opp,
                "match_percentage": match_percentage,
                "matched_skills": matched,
            })

        # Sort descending
        scored_items.sort(key=lambda x: x["match_percentage"], reverse=True)
        top_candidates = scored_items[:limit]

        # Generate reasons
        results = []
        overall_mode = "deterministic"

        for item in top_candidates:
            opp = item["opportunity"]
            matched = item["matched_skills"]
            llm_why = await self._try_generate_llm_why(
                opp.get("title", ""),
                opp.get("org", ""),
                matched,
                user_skills_clean,
                year
            )

            if llm_why:
                why_line = llm_why
                mode = "llm"
                overall_mode = "llm"
            else:
                why_line = self._build_deterministic_why(
                    opp.get("title", ""),
                    opp.get("org", ""),
                    matched,
                    user_skills_clean,
                    year
                )
                mode = "deterministic"

            results.append({
                "opportunity": opp,
                "match_percentage": item["match_percentage"],
                "why": why_line,
                "explanation_mode": mode,
                "matched_skills": matched,
            })

        return {
            "total_matches": len(results),
            "explanation_mode": overall_mode,
            "matches": results,
        }

match_service = MatchService()
