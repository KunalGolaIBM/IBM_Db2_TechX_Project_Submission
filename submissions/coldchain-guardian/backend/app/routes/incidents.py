
from fastapi import APIRouter, HTTPException

from app.database.db import (
    execute_query,
    execute_query_one,
    execute_insert_get_id
)

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])


def determine_severity(sensitivity, deviation):
    """Determine incident severity using product sensitivity and deviation."""

    if deviation >= 10:
        return "CRITICAL"

    if sensitivity == "HIGH" or deviation >= 3:
        return "HIGH"

    return "MEDIUM"


@router.post("/detect")
async def detect_temperature_anomalies():
    """
    Scan existing sensor readings.
    Create incidents for readings outside product temperature limits.
    Avoid creating duplicate OPEN incidents for the same shipment.
    """

    violations = execute_query(
        """
        SELECT
            R.READING_ID,
            R.SHIPMENT_ID,
            R.TEMPERATURE,
            R.RECORDED_AT,
            P.PRODUCT_NAME,
            P.MIN_TEMPERATURE,
            P.MAX_TEMPERATURE,
            P.SENSITIVITY_LEVEL
        FROM SENSOR_READINGS R
        JOIN SHIPMENTS S
            ON R.SHIPMENT_ID = S.SHIPMENT_ID
        JOIN PRODUCTS P
            ON S.PRODUCT_ID = P.PRODUCT_ID
        WHERE R.TEMPERATURE < P.MIN_TEMPERATURE
           OR R.TEMPERATURE > P.MAX_TEMPERATURE
        ORDER BY R.RECORDED_AT
        """
    )

    created = []
    skipped = 0

    for reading in violations:

        shipment_id = reading["shipment_id"]
        temperature = reading["temperature"]
        minimum = reading["min_temperature"]
        maximum = reading["max_temperature"]
        sensitivity = reading["sensitivity_level"]

        deviation = max(
            minimum - temperature,
            temperature - maximum,
            0
        )

        # Avoid duplicate active incidents for the same shipment.
        existing = execute_query_one(
            """
            SELECT INCIDENT_ID
            FROM INCIDENTS
            WHERE SHIPMENT_ID = ?
              AND INCIDENT_TYPE = ?
              AND STATUS = 'OPEN'
            """,
            (shipment_id, "TEMPERATURE_EXCURSION")
        )

        if existing:
            skipped += 1
            continue

        severity = determine_severity(sensitivity, deviation)

        description = (
            f"Temperature anomaly detected for {reading['product_name']}. "
            f"Reading ID: {reading['reading_id']}. "
            f"Recorded temperature: {temperature} C. "
            f"Allowed range: {minimum} C to {maximum} C. "
            f"Deviation: {deviation} C. "
            f"Recorded at: {reading['recorded_at']}."
        )

        incident_id = execute_insert_get_id(
            """
            INSERT INTO INCIDENTS
            (
                SHIPMENT_ID,
                INCIDENT_TYPE,
                SEVERITY,
                DESCRIPTION,
                STATUS
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                shipment_id,
                "TEMPERATURE_EXCURSION",
                severity,
                description,
                "OPEN"
            )
        )

        created.append({
            "incident_id": incident_id,
            "shipment_id": shipment_id,
            "reading_id": reading["reading_id"],
            "product_name": reading["product_name"],
            "temperature": temperature,
            "severity": severity
        })

    return {
        "message": "Temperature anomaly detection completed",
        "violations_found": len(violations),
        "incidents_created": len(created),
        "duplicate_incidents_skipped": skipped,
        "incidents": created
    }


@router.get("/")
async def get_incidents():
    """Retrieve all incidents with their deterministic risk assessment."""

    return execute_query(
        """
        SELECT
            I.INCIDENT_ID,
            I.SHIPMENT_ID,
            I.INCIDENT_TYPE,
            I.SEVERITY,
            I.DESCRIPTION,
            I.STATUS,
            I.CREATED_AT,
            RA.ASSESSMENT_ID AS RISK_ASSESSMENT_ID,
            RA.RISK_SCORE,
            RA.RISK_LEVEL
        FROM INCIDENTS I
        LEFT JOIN RISK_ASSESSMENTS RA
            ON RA.ASSESSMENT_ID = (
                SELECT MIN(RA2.ASSESSMENT_ID)
                FROM RISK_ASSESSMENTS RA2
                WHERE RA2.INCIDENT_ID = I.INCIDENT_ID
            )
        ORDER BY I.CREATED_AT DESC
        """
    )


@router.get("/{incident_id}")
async def get_incident(incident_id: int):
    """Retrieve an incident by ID with its deterministic risk assessment."""

    incident = execute_query_one(
        """
        SELECT
            I.INCIDENT_ID,
            I.SHIPMENT_ID,
            I.INCIDENT_TYPE,
            I.SEVERITY,
            I.DESCRIPTION,
            I.STATUS,
            I.CREATED_AT,
            RA.ASSESSMENT_ID AS RISK_ASSESSMENT_ID,
            RA.RISK_SCORE,
            RA.RISK_LEVEL
        FROM INCIDENTS I
        LEFT JOIN RISK_ASSESSMENTS RA
            ON RA.ASSESSMENT_ID = (
                SELECT MIN(RA2.ASSESSMENT_ID)
                FROM RISK_ASSESSMENTS RA2
                WHERE RA2.INCIDENT_ID = I.INCIDENT_ID
            )
        WHERE I.INCIDENT_ID = ?
        """,
        (incident_id,)
    )

    if not incident:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )

    return incident
