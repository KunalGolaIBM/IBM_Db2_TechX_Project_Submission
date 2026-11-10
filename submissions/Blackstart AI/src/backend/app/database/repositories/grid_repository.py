import ibm_db
from app.integrations.db2.client import connect_db2


def fetch_all(sql):
    conn = connect_db2()
    try:
        stmt = ibm_db.exec_immediate(conn, sql)
        rows = []
        row = ibm_db.fetch_assoc(stmt)
        while row:
            rows.append({str(k).lower(): v for k, v in row.items()})
            row = ibm_db.fetch_assoc(stmt)
        return rows
    finally:
        ibm_db.close(conn)


def get_grid_data():
    return {
        "plants": fetch_all(
            "SELECT * FROM POWER_PLANT"
        ),
        "substations": fetch_all(
            "SELECT * FROM SUBSTATION"
        ),
        "lines": fetch_all(
            "SELECT * FROM TRANSMISSION_LINE"
        ),
        "incidents": fetch_all(
            "SELECT * FROM GRID_INCIDENT"
        )
    }


def save_agent_events(events):
    conn = connect_db2()
    try:
        sql = """
        INSERT INTO AGENT_EVENT
        (AGENT_NAME, EVENT_TYPE, FINDING, CONFIDENCE)
        VALUES (?, ?, ?, ?)
        """
        for event in events:
            stmt = ibm_db.prepare(conn, sql)
            ibm_db.execute(stmt, (
                event["agent"],
                event["event_type"],
                event["finding"][:1000],
                float(event["confidence"])
            ))
    finally:
        ibm_db.close(conn)
