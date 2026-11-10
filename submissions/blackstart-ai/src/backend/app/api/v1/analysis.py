from fastapi import APIRouter, HTTPException
from app.database.repositories.grid_repository import (
    get_grid_data,
    save_agent_events
)
from app.orchestration.graph import analyze_grid

router = APIRouter()


@router.get("/overview")
def grid_overview():
    try:
        return get_grid_data()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/analyze")
def run_analysis():
    try:
        grid = get_grid_data()
        output = analyze_grid(grid)
        save_agent_events(output["events"])
        return output["result"]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
