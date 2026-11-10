
"""Seed ColdChain Guardian with realistic sample data.

Features:
- Uses actual DB2-generated identity IDs.
- Avoids duplicate products, shipments and sensor readings.
- Preserves existing database records.
- Maintains foreign-key relationships.
- Safe to execute multiple times.
"""

from app.database.db import (
    execute_query,
    execute_insert_get_id,
)


def get_or_create_product(product):
    """Find a product by name or insert it."""

    name, category, min_temp, max_temp, sensitivity = product

    rows = execute_query(
        "SELECT PRODUCT_ID FROM PRODUCTS WHERE PRODUCT_NAME = ?",
        (name,)
    )

    if rows:
        product_id = rows[0]["product_id"]
        print(f"[EXISTS] Product: {name} (ID: {product_id})")
        return product_id

    sql = """
        INSERT INTO PRODUCTS (
            PRODUCT_NAME,
            PRODUCT_CATEGORY,
            MIN_TEMPERATURE,
            MAX_TEMPERATURE,
            SENSITIVITY_LEVEL
        )
        VALUES (?, ?, ?, ?, ?)
    """

    product_id = execute_insert_get_id(sql, product)

    print(f"[INSERTED] Product: {name} (ID: {product_id})")

    return product_id


def get_or_create_shipment(shipment):
    """Find a shipment by vehicle ID or insert it."""

    (
        product_id,
        vehicle_id,
        source,
        destination,
        status,
        departure,
        arrival,
    ) = shipment

    rows = execute_query(
        "SELECT SHIPMENT_ID FROM SHIPMENTS WHERE VEHICLE_ID = ?",
        (str(vehicle_id),)
    )

    if rows:
        shipment_id = rows[0]["shipment_id"]
        print(
            f"[EXISTS] Shipment: {vehicle_id} "
            f"(ID: {shipment_id})"
        )
        return shipment_id

    sql = """
        INSERT INTO SHIPMENTS (
            PRODUCT_ID,
            VEHICLE_ID,
            SOURCE_LOCATION,
            DESTINATION_LOCATION,
            SHIPMENT_STATUS,
            DEPARTURE_TIME,
            EXPECTED_ARRIVAL
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """

    shipment_id = execute_insert_get_id(
        sql,
        (
            product_id,
            str(vehicle_id),
            source,
            destination,
            status,
            departure,
            arrival,
        )
    )

    print(
        f"[INSERTED] Shipment: {vehicle_id} "
        f"(ID: {shipment_id})"
    )

    return shipment_id


def insert_sensor_reading(reading):
    """Insert a sensor reading only if it doesn't exist."""

    shipment_id, temperature, humidity, recorded_at = reading

    rows = execute_query(
        """
        SELECT READING_ID
        FROM SENSOR_READINGS
        WHERE SHIPMENT_ID = ?
          AND RECORDED_AT = ?
        """,
        (shipment_id, recorded_at)
    )

    if rows:
        print(
            f"[EXISTS] Sensor reading for shipment "
            f"{shipment_id} at {recorded_at}"
        )
        return False

    sql = """
        INSERT INTO SENSOR_READINGS (
            SHIPMENT_ID,
            TEMPERATURE,
            HUMIDITY,
            RECORDED_AT
        )
        VALUES (?, ?, ?, ?)
    """

    execute_insert_get_id(sql, reading)

    return True


def seed():

    print("=" * 55)
    print(" COLDCHAIN GUARDIAN - DATABASE SEEDING")
    print("=" * 55)

    # ------------------------------------------------
    # 1. PRODUCTS
    # ------------------------------------------------

    products = [
        ("Vaccine‑A", "Vaccine", -80, -60, "HIGH"),
        ("Vaccine‑B", "Vaccine", -70, -50, "MEDIUM"),
        ("Dairy‑Milk", "Dairy", 0, 4, "LOW"),
        ("Ice‑Cream", "Dessert", -25, -18, "MEDIUM"),
        ("Fresh‑Fish", "Seafood", 0, 2, "HIGH"),
    ]

    product_ids = {}

    print("\n--- PRODUCTS ---")

    for product in products:
        product_id = get_or_create_product(product)
        product_ids[product[0]] = product_id

    # ------------------------------------------------
    # 2. SHIPMENTS
    # ------------------------------------------------

    shipments = [
        (
            product_ids["Vaccine‑A"],
            "101",
            "Factory A",
            "Clinic X",
            "IN_TRANSIT",
            "2026-11-01 08:00:00",
            "2026-11-05 12:00:00",
        ),
        (
            product_ids["Vaccine‑B"],
            "102",
            "Factory B",
            "Hospital Y",
            "IN_TRANSIT",
            "2026-11-02 09:30:00",
            "2026-11-06 15:45:00",
        ),
        (
            product_ids["Dairy‑Milk"],
            "103",
            "Dairy Farm",
            "Supermarket Z",
            "IN_TRANSIT",
            "2026-11-03 07:15:00",
            "2026-11-07 10:20:00",
        ),
        (
            product_ids["Ice‑Cream"],
            "104",
            "Ice-Cream Plant",
            "Retail A",
            "IN_TRANSIT",
            "2026-11-04 06:00:00",
            "2026-11-08 09:30:00",
        ),
        (
            product_ids["Fresh‑Fish"],
            "105",
            "Fishery",
            "Restaurant B",
            "IN_TRANSIT",
            "2026-11-05 11:00:00",
            "2026-11-09 14:00:00",
        ),
    ]

    shipment_ids = {}

    print("\n--- SHIPMENTS ---")

    for shipment in shipments:
        shipment_id = get_or_create_shipment(shipment)
        shipment_ids[shipment[1]] = shipment_id

    # ------------------------------------------------
    # 3. SENSOR READINGS
    # ------------------------------------------------

    readings = [
        # Shipment 101: Vaccine-A
        (shipment_ids["101"], -70, 30, "2026-11-01 09:00:00"),
        (shipment_ids["101"], -71, 31, "2026-11-01 12:00:00"),
        (shipment_ids["101"], -69, 29, "2026-11-01 15:00:00"),
        (shipment_ids["101"], -55, 35, "2026-11-01 18:00:00"),

        # Shipment 102: Vaccine-B
        (shipment_ids["102"], -65, 32, "2026-11-02 10:00:00"),
        (shipment_ids["102"], -49, 40, "2026-11-02 14:00:00"),
    ]

    inserted_readings = 0

    print("\n--- SENSOR READINGS ---")

    for reading in readings:
        if insert_sensor_reading(reading):
            inserted_readings += 1

    # ------------------------------------------------
    # 4. SUMMARY
    # ------------------------------------------------

    print("\n" + "=" * 55)
    print(" SEEDING SUMMARY")
    print("=" * 55)

    for table in [
        "PRODUCTS",
        "SHIPMENTS",
        "SENSOR_READINGS",
    ]:
        rows = execute_query(
            f"SELECT COUNT(*) AS TOTAL FROM {table}"
        )
        print(f"{table}: {rows[0]['total']}")

    print(f"New sensor readings inserted: {inserted_readings}")

    print("\n[SUCCESS] Seed data operation completed!")
    print("=" * 55)


if __name__ == "__main__":
    seed()
