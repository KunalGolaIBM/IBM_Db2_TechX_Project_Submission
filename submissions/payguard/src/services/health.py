"""Deep dependency checks; probe results are bounded and never contain credentials."""
import httpx

from cache import TTLCache
from config import settings

_gemini = TTLCache(1, 30)


def gemini_probe() -> dict:
    if not settings.llm_enabled:
        return {"configured": False, "reachable": None}

    def probe():
        try:
            response = httpx.get(
                f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}",
                headers={"x-goog-api-key": settings.gemini_api_key}, timeout=settings.gemini_timeout,
            )
            return {"configured": True, "reachable": response.status_code == 200,
                    "status": response.status_code}
        except httpx.HTTPError:
            return {"configured": True, "reachable": False}

    return _gemini.get_or_load(settings.gemini_model, probe)


def deep_health(s) -> dict:
    try:
        db_ok = s.repo.ping()
    except Exception:
        db_ok = False
    gemini = gemini_probe()
    pool = getattr(s.repo, "pool", None)
    return {"db2": db_ok, "pool": pool.stats() if pool else None,
            "embedder": s.embedder.name, "llm": settings.llm_enabled,
            "gemini": gemini, "paypal": s.paypal.enabled,
            "model": settings.gemini_model if settings.llm_enabled else None,
            "degraded": not db_ok or gemini["reachable"] is False}
