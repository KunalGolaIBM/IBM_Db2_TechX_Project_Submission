import os
from pathlib import Path

import ibm_db
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FILE = PROJECT_ROOT / "db" / "schema.sql"
SCHEMA_NAME = "MOODMUSIC"


def required_setting(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required setting: {name}")
    return value


def connection_dsn() -> str:
    return (
        f"DATABASE={required_setting('DB2_DATABASE')};"
        f"HOSTNAME={required_setting('DB2_HOST')};"
        f"PORT={required_setting('DB2_PORT')};"
        "PROTOCOL=TCPIP;"
        f"UID={required_setting('DB2_USER')};"
        f"PWD={required_setting('DB2_PASSWORD')};"
    )


def execute_schema(connection: object) -> None:
    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
    for statement in schema_sql.split(";"):
        statement = statement.strip()
        if statement:
            try:
                ibm_db.exec_immediate(connection, statement)
            except Exception as error:
                if "42710" not in str(error) and "01550" not in str(error):
                    raise
                print("Already exists; skipped:", statement.splitlines()[0])


def main() -> None:
    load_dotenv()
    connection = ibm_db.connect(connection_dsn(), "", "")
    try:
        try:
            ibm_db.exec_immediate(connection, f"CREATE SCHEMA {SCHEMA_NAME}")
            print(f"Created schema {SCHEMA_NAME}.")
        except Exception as error:
            if "42710" not in str(error):
                raise
            print(f"Schema {SCHEMA_NAME} already exists.")

        ibm_db.exec_immediate(connection, f"SET CURRENT SCHEMA {SCHEMA_NAME}")
        execute_schema(connection)
        print(
            f"Created Mood-to-Music tables in "
            f"{required_setting('DB2_DATABASE')}.{SCHEMA_NAME}."
        )
    finally:
        ibm_db.close(connection)


if __name__ == "__main__":
    main()
