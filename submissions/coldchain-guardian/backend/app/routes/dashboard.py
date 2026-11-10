"""Dashboard endpoint providing quick statistics for the UI."""

from fastapi import APIRouter
from app.database.db import execute_query_one, execute_query

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/")
def get_stats():
    """Return aggregated counts and summaries for the front-end dashboard."""
    stats = {}
    stats["products"] = execute_query_one("SELECT COUNT(*) AS cnt FROM PRODUCTS")["cnt"]
    stats["shipments"] = execute_query_one("SELECT COUNT(*) AS cnt FROM SHIPMENTS")["cnt"]
    stats["shipments_in_transit"] = execute_query_one(
        "SELECT COUNT(*) AS cnt FROM SHIPMENTS WHERE SHIPMENT_STATUS = 'IN_TRANSIT'"
    )["cnt"]
    stats["open_incidents"] = execute_query_one(
        "SELECT COUNT(*) AS cnt FROM INCIDENTS WHERE STATUS='OPEN'"
    )["cnt"]
    stats["pending_recommendations"] = execute_query_one(
        "SELECT COUNT(*) AS cnt FROM RECOMMENDATIONS WHERE APPROVAL_STATUS = 'PENDING'"
    )["cnt"]
    stats["temperature_violations"] = execute_query_one(
        "SELECT COUNT(*) AS cnt FROM INCIDENTS WHERE INCIDENT_TYPE = 'TEMPERATURE_EXCURSION' AND STATUS = 'OPEN'"
    )["cnt"]

    # Risk distribution
    risk_rows = execute_query(
        "SELECT RISK_LEVEL, COUNT(*) AS cnt FROM RISK_ASSESSMENTS GROUP BY RISK_LEVEL"
    )
    stats["risk_distribution"] = {row["risk_level"]: row["cnt"] for row in risk_rows}

    # Recent incidents (last 5)
    stats["recent_incidents"] = execute_query(
        """
        SELECT INCIDENT_ID, SHIPMENT_ID, INCIDENT_TYPE, SEVERITY, STATUS, CREATED_AT
        FROM INCIDENTS
        ORDER BY CREATED_AT DESC
        FETCH FIRST 5 ROWS ONLY
        """
    )
    # Serialize timestamps
    for inc in stats["recent_incidents"]:
        if inc.get("created_at") and not isinstance(inc["created_at"], str):
            inc["created_at"] = inc["created_at"].isoformat()

    # Recent shipment activity (last 5 by departure time)
    stats["recent_shipments"] = execute_query(
        """
        SELECT S.SHIPMENT_ID, P.PRODUCT_NAME, S.VEHICLE_ID,
               S.SOURCE_LOCATION, S.DESTINATION_LOCATION,
               S.SHIPMENT_STATUS, S.DEPARTURE_TIME, S.EXPECTED_ARRIVAL
        FROM SHIPMENTS S
        JOIN PRODUCTS P ON S.PRODUCT_ID = P.PRODUCT_ID
        ORDER BY S.DEPARTURE_TIME DESC
        FETCH FIRST 5 ROWS ONLY
        """
    )

    # Temperature trends: most recent real sensor readings, chronological order.
    trend_rows = execute_query(
        """
        SELECT R.READING_ID, R.SHIPMENT_ID, R.TEMPERATURE, R.RECORDED_AT,
               P.PRODUCT_NAME
        FROM SENSOR_READINGS R
        JOIN SHIPMENTS S ON R.SHIPMENT_ID = S.SHIPMENT_ID
        JOIN PRODUCTS P ON S.PRODUCT_ID = P.PRODUCT_ID
        ORDER BY R.RECORDED_AT DESC
        FETCH FIRST 20 ROWS ONLY
        """
    )
    trend_rows.reverse()
    for row in trend_rows:
        if row.get("recorded_at") and not isinstance(row["recorded_at"], str):
            row["recorded_at"] = row["recorded_at"].isoformat()
    stats["temperature_trends"] = trend_rows

    return stats
