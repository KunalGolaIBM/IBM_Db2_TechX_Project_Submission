from app.database.db import execute_query, execute_insert_get_id

readings = [
    # Dairy-Milk: allowed 0°C to 4°C
    (61, 2.5, 65, "2026-11-03 08:00:00"),
    (61, 6.5, 68, "2026-11-03 10:00:00"),

    # Ice-Cream: allowed -25°C to -18°C
    (81, -22, 40, "2026-11-04 07:00:00"),
    (81, -15, 45, "2026-11-04 09:00:00"),

    # Fresh-Fish: allowed 0°C to 2°C
    (101, 1.0, 75, "2026-11-05 12:00:00"),
    (101, 4.5, 80, "2026-11-05 14:00:00"),
]

sql = """
INSERT INTO SENSOR_READINGS
(SHIPMENT_ID, TEMPERATURE, HUMIDITY, RECORDED_AT)
VALUES (?, ?, ?, ?)
"""

for reading in readings:
    execute_insert_get_id(sql, reading)

print("Additional sensor readings inserted!")