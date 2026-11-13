import os

import ibm_db
from dotenv import load_dotenv


def required_setting(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required setting: {name}")
    return value


def main() -> None:
    load_dotenv()
    dsn = (
        f"DATABASE={required_setting('DB2_DATABASE')};"
        f"HOSTNAME={required_setting('DB2_HOST')};"
        f"PORT={required_setting('DB2_PORT')};"
        "PROTOCOL=TCPIP;"
        f"UID={required_setting('DB2_USER')};"
        f"PWD={required_setting('DB2_PASSWORD')};"
    )

    connection = ibm_db.connect(dsn, "", "")
    try:
        statement = ibm_db.exec_immediate(
            connection,
            "SELECT CURRENT SERVER, CURRENT TIMESTAMP "
            "FROM SYSIBM.SYSDUMMY1",
        )
        print("Connected to Db2:", ibm_db.fetch_tuple(statement))
    finally:
        ibm_db.close(connection)


if __name__ == "__main__":
    main()
