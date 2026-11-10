
from fastapi import APIRouter, HTTPException
from app.database.db import execute_query, execute_query_one

router = APIRouter(prefix="/api/shipments", tags=["Shipments"])


@router.get("/")
async def get_shipments():
    """Retrieve all shipments with product info, permitted range and latest reading."""
    rows = execute_query(
        """
        SELECT
            S.SHIPMENT_ID,
            S.PRODUCT_ID,
            P.PRODUCT_NAME,
            S.VEHICLE_ID,
            S.SOURCE_LOCATION,
            S.DESTINATION_LOCATION,
            S.SHIPMENT_STATUS,
            S.DEPARTURE_TIME,
            S.EXPECTED_ARRIVAL,
            P.MIN_TEMPERATURE,
            P.MAX_TEMPERATURE,
            (
                SELECT R.TEMPERATURE
                FROM SENSOR_READINGS R
                WHERE R.SHIPMENT_ID = S.SHIPMENT_ID
                ORDER BY R.RECORDED_AT DESC
                FETCH FIRST 1 ROW ONLY
            ) AS LATEST_TEMPERATURE,
            (
                SELECT R.RECORDED_AT
                FROM SENSOR_READINGS R
                WHERE R.SHIPMENT_ID = S.SHIPMENT_ID
                ORDER BY R.RECORDED_AT DESC
                FETCH FIRST 1 ROW ONLY
            ) AS LATEST_READING_AT
        FROM SHIPMENTS S
        JOIN PRODUCTS P ON S.PRODUCT_ID = P.PRODUCT_ID
        ORDER BY S.SHIPMENT_ID
        """
    )
    for row in rows:
        row["temperature_violation"] = _is_violation(
            row.get("latest_temperature"),
            row.get("min_temperature"),
            row.get("max_temperature"),
        )
    return rows


def _is_violation(temperature, min_temp, max_temp):
    """Return True/False when a reading and limits exist, else None."""
    if temperature is None or min_temp is None or max_temp is None:
        return None
    return float(temperature) < float(min_temp) or float(temperature) > float(max_temp)


@router.get("/{shipment_id}")
async def get_shipment(shipment_id: int):
    """Retrieve a shipment by ID."""
    shipment = execute_query_one(
        """
        SELECT
            S.SHIPMENT_ID,
            S.PRODUCT_ID,
            P.PRODUCT_NAME,
            S.VEHICLE_ID,
            S.SOURCE_LOCATION,
            S.DESTINATION_LOCATION,
            S.SHIPMENT_STATUS,
            S.DEPARTURE_TIME,
            S.EXPECTED_ARRIVAL
        FROM SHIPMENTS S
        JOIN PRODUCTS P ON S.PRODUCT_ID = P.PRODUCT_ID
        WHERE S.SHIPMENT_ID = ?
        """,
        (shipment_id,)
    )

    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    return shipment


@router.get("/{shipment_id}/readings")
async def get_shipment_readings(shipment_id: int):
    """Retrieve sensor readings for a shipment."""

    shipment = execute_query_one(
        "SELECT SHIPMENT_ID FROM SHIPMENTS WHERE SHIPMENT_ID = ?",
        (shipment_id,)
    )

    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    return execute_query(
        """
        SELECT READING_ID, SHIPMENT_ID, TEMPERATURE,
               HUMIDITY, RECORDED_AT
        FROM SENSOR_READINGS
        WHERE SHIPMENT_ID = ?
        ORDER BY RECORDED_AT
        """,
        (shipment_id,)
    )
