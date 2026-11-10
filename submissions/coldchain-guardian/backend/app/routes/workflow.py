"""Workflow API routes for ColdChain Guardian.

Triggers the LangGraph workflow for a given sensor reading. CrewAI collaborative
analysis runs as a node inside the graph (after risk assessment), so the result
already contains the crew analysis and the deterministic risk score.
"""

from fastapi import APIRouter, HTTPException, status

from app.workflow.graph import run_workflow

router = APIRouter(prefix="/api/workflow", tags=["Workflow"])


@router.post("/run/{reading_id}", status_code=status.HTTP_200_OK)
def run_workflow_endpoint(reading_id: int):
    """Execute the LangGraph workflow for a specific reading.

    Args:
        reading_id: Positive integer identifier of the sensor reading.

    Returns:
        Workflow result dict including incident, deterministic risk assessment,
        CrewAI analysis (or graceful fallback), and recommendations.

    Raises:
        HTTPException 400: if reading_id is not a positive integer.
        HTTPException 500: if the workflow reports a failure.
    """
    if not isinstance(reading_id, int) or reading_id <= 0:
        raise HTTPException(status_code=400, detail="reading_id must be a positive integer")

    try:
        result = run_workflow(reading_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Workflow execution failed",
        ) from exc

    if result.get("workflow_status") == "FAILED":
        raise HTTPException(
            status_code=500,
            detail=result.get("error") or "Workflow execution failed",
        )

    return result
