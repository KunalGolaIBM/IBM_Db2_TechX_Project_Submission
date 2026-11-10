import os
import ibm_db
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """
    Connect to IBM Db2 using credentials
    stored in environment variables.
    """

    database = os.getenv("DB2_DATABASE")
    hostname = os.getenv("DB2_HOSTNAME")
    port = os.getenv("DB2_PORT", "50000")
    username = os.getenv("DB2_USER")
    password = os.getenv("DB2_PASSWORD")
    security = os.getenv("DB2_SECURITY", "SSL")

    required = [database, hostname, username, password]

    if not all(required):
        raise ValueError(
            "Missing IBM Db2 credentials. Check your .env file."
        )

    connection_string = (
        f"DATABASE={database};"
        f"HOSTNAME={hostname};"
        f"PORT={port};"
        f"PROTOCOL=TCPIP;"
        f"UID={username};"
        f"PWD={password};"
        f"SECURITY={security};"
    )

    return ibm_db.connect(connection_string, "", "")


def test_connection():
    connection = get_connection()

    try:
        return True
    finally:
        ibm_db.close(connection)
