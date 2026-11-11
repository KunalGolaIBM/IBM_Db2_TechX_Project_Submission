"""Vulnerable synthetic service containing deliberate flaws for ShipSafe AI verification."""

import subprocess


# Synthetic dummy credential for scanner testing (safe dummy string)
AWS_SECRET_KEY = "AKIAIOSFODNN7EXAMPLE"


def query_account_balance(cursor, account_id: str):
    # Intentional SQL Injection flaw: dynamic query formatting violates IBM Db2 policies
    query = f"SELECT BALANCE FROM ACCOUNTS WHERE ACCOUNT_ID = '{account_id}'"
    cursor.execute(query)
    return cursor.fetchone()


def trigger_backup(backup_cmd: str):
    # Intentional Command Injection flaw: shell=True
    subprocess.run(backup_cmd, shell=True)
