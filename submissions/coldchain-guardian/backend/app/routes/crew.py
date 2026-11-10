"""CrewAI analysis endpoint for ColdChain Guardian.

Runs the same structured collaborative analysis used by the LangGraph workflow
node. The deterministic risk score from RISK_ASSESSMENTS stays authoritative;
CrewAI only adds explanation and suggested actions. Stored analysis is reused
from AUDIT_LOGS so repeated calls do not re-invoke the model.
"""

from fastapi import APIRouter, HTTPException

from app.database.db import execute_query_one
from app.agents.crew_analysis import run as run_crew_analysis

router = APIRouter(prefix="/api/crew", tags=["CrewAI"])


@router.post("/analyse/{incident_id}")
def analyse_incident(incident_id: int):
    """Run CrewAI collaborative analysis for an incident.

    Returns structured AI analysis from three specialist agents plus the
    authoritative deterministic risk score. If no AI API key is configured,
    returns a graceful deterministic fallback built only from stored facts.
    """
    incident = execute_query_one(
        """
        SELECT I.INCIDENT_ID, I.SHIPMENT_ID, I.SEVERITY, I.DESCRIPTION, I.STATUS,
               RA.RISK_SCORE, RA.RISK_LEVEL, RA.EXPLANATION AS RISK_EXPLANATION,
               RA.ASSESSMENT_ID AS RISK_ASSESSMENT_ID
        FROM INCIDENTS I
        LEFT JOIN RISK_ASSESSMENTS RA ON I.INCIDENT_ID = RA.INCIDENT_ID
        WHERE I.INCIDENT_ID = ?
        """,
        (incident_id,)
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    shipment = execute_query_one(
        """
        SELECT S.SHIPMENT_ID, S.SOURCE_LOCATION, S.DESTINATION_LOCATION, S.VEHICLE_ID,
               S.SHIPMENT_STATUS, P.PRODUCT_NAME, P.PRODUCT_CATEGORY,
               P.MIN_TEMPERATURE, P.MAX_TEMPERATURE, P.SENSITIVITY_LEVEL
        FROM SHIPMENTS S
        JOIN PRODUCTS P ON S.PRODUCT_ID = P.PRODUCT_ID
        WHERE S.SHIPMENT_ID = ?
        """,
        (incident["shipment_id"],)
    )

    # Ground the temperature deviation in the latest real reading for the
    # shipment. Never fabricate a reading when none exists.
    latest = execute_query_one(
        """
        SELECT READING_ID, TEMPERATURE, HUMIDITY, RECORDED_AT
        FROM SENSOR_READINGS
        WHERE SHIPMENT_ID = ?
        ORDER BY RECORDED_AT DESC
        FETCH FIRST 1 ROW ONLY
        """,
        (incident["shipment_id"],)
    )

    product_ctx = {}
    shipment_ctx = {}
    sensor_ctx = {}
    deviation = None
    temp_status = None
    if shipment:
        product_ctx = {
            "product_name": shipment.get("product_name"),
            "product_category": shipment.get("product_category"),
            "sensitivity_level": shipment.get("sensitivity_level"),
            "min_temperature": shipment.get("min_temperature"),
            "max_temperature": shipment.get("max_temperature"),
        }
        shipment_ctx = {
            "shipment_id": shipment.get("shipment_id"),
            "source_location": shipment.get("source_location"),
            "destination_location": shipment.get("destination_location"),
            "vehicle_id": shipment.get("vehicle_id"),
            "shipment_status": shipment.get("shipment_status"),
        }
    if latest:
        sensor_ctx = {
            "reading_id": latest.get("reading_id"),
            "shipment_id": incident["shipment_id"],
            "temperature": latest.get("temperature"),
            "humidity": latest.get("humidity"),
            "recorded_at": latest.get("recorded_at"),
        }
        temp = latest.get("temperature")
        mint = product_ctx.get("min_temperature")
        maxt = product_ctx.get("max_temperature")
        if temp is not None and mint is not None and maxt is not None:
            temp, mint, maxt = float(temp), float(mint), float(maxt)
            if temp < mint:
                temp_status, deviation = "VIOLATION", mint - temp
            elif temp > maxt:
                temp_status, deviation = "VIOLATION", temp - maxt
            else:
                temp_status, deviation = "NORMAL", 0.0

    state = {
        "incident_id": incident_id,
        "severity": incident.get("severity"),
        "risk_assessment_id": incident.get("risk_assessment_id"),
        "risk_score": incident.get("risk_score"),
        "risk_level": incident.get("risk_level"),
        "risk_explanation": incident.get("risk_explanation"),
        "temperature_deviation": deviation,
        "temperature_status": temp_status,
        "product": product_ctx,
        "shipment": shipment_ctx,
        "sensor": sensor_ctx,
    }

    result = run_crew_analysis(state)
    analysis = result.get("crew_analysis", {})

    return {
        "incident_id": incident_id,
        "severity": incident.get("severity"),
        "risk_score": incident.get("risk_score"),
        "risk_level": incident.get("risk_level"),
        "risk_assessment_id": incident.get("risk_assessment_id"),
        "risk_explanation": incident.get("risk_explanation"),
        "temperature_deviation": deviation,
        "product_name": product_ctx.get("product_name"),
        "product_sensitivity": product_ctx.get("sensitivity_level"),
        "crew_status": result.get("crew_status"),
        "crew_analysis": analysis,
    }
