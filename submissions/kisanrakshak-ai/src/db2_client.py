from __future__ import annotations

import os
from typing import Any, Dict, List

try:
    import ibm_db
except ImportError:  # pragma: no cover
    ibm_db = None


def get_db_config() -> Dict[str, str]:
    return {
        "host": os.getenv("DB2_HOST", "localhost"),
        "port": os.getenv("DB2_PORT", "50000"),
        "database": os.getenv("DB2_DATABASE", "testdb"),
        "user": os.getenv("DB2_USER", "db2inst1"),
        "password": os.getenv("DB2_PASSWORD", ""),
    }


def get_connection():
    if ibm_db is None:
        raise RuntimeError(
            "ibm_db is not installed. Run: pip install -r requirements.txt"
        )

    config = get_db_config()
    dsn = (
        "DATABASE={database};"
        "HOSTNAME={host};"
        "PORT={port};"
        "PROTOCOL=TCPIP;"
        "UID={user};"
        "PWD={password};"
    ).format(**config)

    return ibm_db.connect(dsn, "", "")


def ensure_schema(conn) -> None:
    if ibm_db is None:
        return

    sql = """
    CREATE TABLE IF NOT EXISTS fields (
        id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        farmer_name VARCHAR(150),
        village VARCHAR(150),
        crop VARCHAR(100),
        soil_type VARCHAR(100),
        acreage DECIMAL(10,2),
        moisture_level DECIMAL(5,2),
        disease_risk_score INTEGER,
        irrigation_status VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    ibm_db.exec_immediate(conn, sql)

    ibm_db.exec_immediate(
        conn,
        """
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            field_id INTEGER,
            category VARCHAR(50),
            recommendation_text CLOB,
            confidence_score DECIMAL(5,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )


def seed_demo_records(conn) -> None:
    if ibm_db is None:
        return

    rows = [
        (
            "Ramesh Verma",
            "Mathura",
            "Wheat",
            "Loam",
            4.5,
            28.5,
            72,
            "Low irrigation",
        ),
        (
            "Sita Devi",
            "Agra",
            "Rice",
            "Clay",
            3.8,
            41.0,
            55,
            "Moderate watering",
        ),
    ]

    for row in rows:
        try:
            ibm_db.exec_immediate(
                conn,
                "INSERT INTO fields (farmer_name, village, crop, soil_type, acreage, moisture_level, disease_risk_score, irrigation_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
        except Exception:
            # Row already exists or table not ready; ignore for demo flow.
            pass


def fetch_field_summary(conn) -> List[Dict[str, Any]]:
    if ibm_db is None:
        return []

    query = """
        SELECT farmer_name, village, crop, soil_type, acreage, moisture_level, disease_risk_score, irrigation_status
        FROM fields
        ORDER BY created_at DESC
        FETCH FIRST 10 ROWS ONLY
    """
    stmt = ibm_db.exec_immediate(conn, query)
    rows = []
    result = ibm_db.fetch_assoc(stmt)
    while result:
        rows.append(result)
        result = ibm_db.fetch_assoc(stmt)
    return rows


def generate_recommendation(field: Dict[str, Any]) -> Dict[str, Any]:
    moisture = float(field.get("MOISTURE_LEVEL", 0) or 0)
    risk = int(field.get("DISEASE_RISK_SCORE", 0) or 0)
    crop = field.get("CROP", "Crop")
    village = field.get("VILLAGE", "region")

    if moisture < 30:
        action = "Increase irrigation scheduling immediately and monitor the field daily."
    elif risk >= 70:
        action = "Inspect for fungal disease or pest infestation and apply targeted crop protection measures."
    else:
        action = "Keep the field under regular monitoring and follow the standard nutrient schedule."

    confidence = min(0.99, max(0.55, (100 - risk) / 100 + moisture / 200))

    return {
        "category": "Crop Advisory",
        "recommendation": (
            f"For {crop} in {village}, {action} "
            "Review the field conditions and prioritize prevention over emergency treatment."
        ),
        "confidence_score": round(confidence, 2),
    }


def build_sample_output() -> List[Dict[str, Any]]:
    return [
        {
            "FARMER_NAME": "Ramesh Verma",
            "VILLAGE": "Mathura",
            "CROP": "Wheat",
            "SOIL_TYPE": "Loam",
            "ACREAGE": 4.5,
            "MOISTURE_LEVEL": 28.5,
            "DISEASE_RISK_SCORE": 72,
            "IRRIGATION_STATUS": "Low irrigation",
        }
    ]
