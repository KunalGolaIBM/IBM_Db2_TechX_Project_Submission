"""Prove a real Db2 connection. Prints server identity and timestamp, never the DSN or credentials.

Run: python src/check_db2.py
"""
import sys

from db import Db2Error, server_identity

if __name__ == "__main__":
    try:
        info = server_identity()
    except Db2Error as exc:
        print(f"FAILED: {exc}")
        sys.exit(1)
    print(f"Connected: server={info['SERVER']} schema={info['SCHEMA_NAME']} user={info['DB_USER'].strip()} "
          f"product={info['DBMS_NAME']} {info['DBMS_VER']} server_time={info['NOW']}")
