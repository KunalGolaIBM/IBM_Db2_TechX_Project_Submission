"""Sensor reading ingestion endpoint.

This router provides a single POST endpoint that stores a new sensor reading
into the `SENSOR_READINGS` table.  It uses the generic DB helpers defined in
`app.database.db`.  The endpoint returns the generated `reading_id` and a simple
status message.  Future work can invoke the LangGraph workflow after insertion.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from datetime import datetime

from app.database.db import execute_insert_get_id, execute_dml
from app.workflow.graph import run_workflow
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/readings", tags=["SensorReadings"])

class ReadingIn(BaseModel):
    shipment_id: int = Field(..., description="ID of the shipment the reading belongs to")
    temperature: float = Field(..., description="Temperature in Celsius")
    humidity: float = Field(..., description="Relative humidity percentage")
    recorded_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of the reading")

@router.post("/", status_code=status.HTTP_201_CREATED)
def ingest_reading(reading: ReadingIn):
    """Insert a new sensor reading and run the workflow.

    Returns a JSON object containing the ``reading_id`` and ``status`` of the DB insert,
    as well as the ``workflow`` result. If the workflow fails, the error is included under
    ``workflow_error`` while the reading remains stored.
    """
    try:
        # Insert the reading into DB and obtain the generated ID.
        sql = """
            INSERT INTO SENSOR_READINGS (SHIPMENT_ID, TEMPERATURE, HUMIDITY, RECORDED_AT)
            VALUES (?, ?, ?, ?)
        """
        reading_id = execute_insert_get_id(
            sql,
            (
                reading.shipment_id,
                reading.temperature,
                reading.humidity,
                reading.recorded_at,
            ),
        )
    except Exception as exc:
        # DB insertion failed – propagate as a server error.
        raise HTTPException(status_code=500, detail=f"DB insert failed: {exc}") from exc

    # At this point the reading is safely stored. Run the LangGraph workflow.
    workflow_result: dict | None = None
    workflow_error: str | None = None
    try:
        workflow_result = run_workflow(int(reading_id))
    except Exception as wf_exc:
        # Preserve the stored reading but capture workflow failure details.
        workflow_error = str(wf_exc)

    response = {
        "reading_id": reading_id,
        "status": "stored",
    }
    if workflow_result is not None:
        response["workflow"] = workflow_result
    if workflow_error is not None:
        response["workflow_error"] = workflow_error
    return response
