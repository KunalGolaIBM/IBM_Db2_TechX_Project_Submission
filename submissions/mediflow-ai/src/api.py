from fastapi import FastAPI, HTTPException
from src.repository import get_repository
from src.agent import run_workflow
from src.models import ReviewRequest

app = FastAPI(title="MediFlow AI", version="0.1.0")
repo = get_repository()

@app.get("/health")
def health():
    return {"status": "ok", "service": "mediflow-ai"}

@app.get("/inventory")
def inventory():
    return {"items": [item.model_dump(mode="json") for item in repo.list_inventory()]}

@app.post("/recommendations/run")
def run_recommendations():
    findings, recommendations, engine = run_workflow(repo.list_inventory(), repo)
    return {"engine": engine, "findings": [f.model_dump(mode="json") for f in findings],
            "recommendations": [r.model_dump(mode="json") for r in recommendations]}

@app.post("/recommendations/{recommendation_id}/review")
def review_recommendation(recommendation_id: str, payload: ReviewRequest):
    existing = getattr(repo, "recommendations", {}).get(recommendation_id)
    if repo.__class__.__name__ == "DemoRepository" and not existing:
        raise HTTPException(status_code=404, detail="Run the workflow first; recommendation not found.")
    quantity = payload.edited_quantity if payload.edited_quantity is not None else (existing.suggested_quantity if existing else 0)
    status = "APPROVED" if payload.action == "approve" else "REJECTED"
    try:
        result = repo.review_recommendation(recommendation_id, status, payload.reviewer, quantity)
        return result.model_dump(mode="json")
    except KeyError:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
