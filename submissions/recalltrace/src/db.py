"""IBM Db2 connection and exact product-and-lot inventory lookup."""

import os
import re
import sys
from contextlib import contextmanager, suppress
from pathlib import Path


class Db2Error(RuntimeError):
    def __init__(self, message, state=None):
        self.state = state
        super().__init__(f"{message} (SQLSTATE {state})" if state else message)


def _settings():
    env_file = Path(__file__).with_name(".env")
    if not env_file.is_file():
        return os.environ
    try:
        from dotenv import dotenv_values
    except ImportError:
        raise Db2Error("Install the dependencies with python -m pip install -r requirements.txt.") from None
    try:
        return {**dotenv_values(env_file, interpolate=False), **os.environ}
    except (OSError, UnicodeError):
        raise Db2Error("Could not read the local .env file as UTF-8.") from None


def _connection_string():
    env = _settings()
    required = {
        "DB2_HOST": "HOSTNAME",
        "DB2_PORT": "PORT",
        "DB2_DATABASE": "DATABASE",
        "DB2_USER": "UID",
        "DB2_PASSWORD": "PWD",
    }
    fields = {key: env.get(key) for key in required}
    missing = [key for key, value in fields.items() if not value]
    if missing:
        raise Db2Error(f"Set {', '.join(missing)} before connecting to Db2.")

    port = fields["DB2_PORT"]
    if not re.fullmatch(r"[0-9]{1,5}", port) or not 1 <= int(port) <= 65535:
        raise Db2Error("DB2_PORT must be a port number between 1 and 65535.")

    settings = {"PROTOCOL": "TCPIP", "CONNECTTIMEOUT": "10"}
    for env_name, keyword in required.items():
        settings[keyword] = _cli_value(env_name, fields[env_name])

    schema = env.get("DB2_SCHEMA")
    if schema:
        settings["CURRENTSCHEMA"] = _cli_value("DB2_SCHEMA", schema)

    tls = env.get("DB2_TLS", "1")
    if tls not in {"0", "1"}:
        raise Db2Error("Set DB2_TLS to 1 for TLS or 0 for a local plaintext connection.")
    if tls == "1":
        cert = Path(env.get("DB2_SSL_CERT") or "")
        if not cert.is_absolute() or not cert.is_file():
            raise Db2Error("Set DB2_SSL_CERT to an absolute path to the Db2 TLS certificate.")
        settings["SECURITY"] = "SSL"
        settings["SSLServerCertificate"] = _cli_value("DB2_SSL_CERT", str(cert))

    return "".join(f"{keyword}={value};" for keyword, value in settings.items())


def _cli_value(name, value):
    if any(character in value for character in ";{}\r\n\0"):
        raise Db2Error(f"{name} contains a reserved Db2 connection-string character.")
    return value


def run(action, function, *args, allow_empty=False):
    """Report driver errors with only the operation name and SQLSTATE."""
    try:
        result = function(*args)
    except Exception as error:
        match = re.search(r"\bSQLSTATE\s*=\s*([0-9A-Z]{5})\b", str(error))
        raise Db2Error(action, match.group(1) if match else None) from None
    if result is False and not allow_empty:
        raise Db2Error(action)
    return result


@contextmanager
def connect(*, transactional=False):
    dsn = _connection_string()
    try:
        import ibm_db
    except ImportError:
        raise Db2Error("Install the IBM Db2 driver with python -m pip install -r requirements.txt.") from None

    connection = run("Db2 connection failed", ibm_db.connect, dsn, "", "")
    try:
        if transactional:
            run(
                "Could not start the Db2 seed transaction",
                ibm_db.autocommit, connection, ibm_db.SQL_AUTOCOMMIT_OFF,
            )
        yield ibm_db, connection
        if transactional:
            run("Could not commit the Db2 seed transaction", ibm_db.commit, connection)
    except BaseException:
        if transactional:
            with suppress(Db2Error):
                run("Could not roll back the Db2 seed transaction", ibm_db.rollback, connection)
        raise
    finally:
        with suppress(Db2Error):
            run("Could not close the Db2 connection", ibm_db.close, connection)


def find_matches(product_code: str, lot_codes: list[str]) -> list[dict]:
    if not lot_codes:
        return []

    placeholders = ", ".join("?" for _ in lot_codes)
    query = f"""
        SELECT p.product_code, i.lot_code, p.product_name, i.site, i.quantity
        FROM recalltrace_products p
        JOIN recalltrace_inventory i ON i.product_code = p.product_code
        WHERE p.product_code = ? AND i.lot_code IN ({placeholders})
        ORDER BY i.lot_code, i.site
    """
    with connect() as (driver, connection):
        statement = run("Could not prepare the inventory lookup", driver.prepare, connection, query)
        run("Could not look up inventory in Db2", driver.execute, statement, (product_code, *lot_codes))
        matches = []
        while row := run(
            "Could not read the inventory rows", driver.fetch_tuple, statement, allow_empty=True
        ):
            code, lot, name, site, quantity = row
            matches.append({
                "product_code": code,
                "lot_code": lot,
                "product_name": name,
                "site": site,
                "quantity": quantity,
            })
        return matches


def check_connection():
    with connect() as (driver, connection):
        statement = run(
            "Could not query the current Db2 schema",
            driver.exec_immediate, connection, "VALUES (CURRENT SCHEMA)",
        )
        run("Could not read the current Db2 schema", driver.fetch_tuple, statement)


if __name__ == "__main__":
    try:
        check_connection()
    except Db2Error as error:
        print(error, file=sys.stderr)
        sys.exit(1)
    print("Db2 connection and schema query succeeded.")
