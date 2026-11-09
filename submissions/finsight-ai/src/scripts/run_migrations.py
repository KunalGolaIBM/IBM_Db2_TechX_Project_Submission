#!/usr/bin/env python3
"""
FinSight AI — Migration Runner (run_migrations.py)
Executes versioned SQL files against IBM Db2 container 'finsight-db2'.
Tracks applied migrations in FINSIGHT.SCHEMA_MIGRATIONS.
"""

import os
import sys
import subprocess
from pathlib import Path

CONTAINER_NAME = "finsight-db2"
DB_NAME = "FINDB"

def run_db2(sql):
    cmd = [
        "docker", "exec", "-i", CONTAINER_NAME,
        "su", "-", "db2inst1", "-c",
        f"db2 -x connect to {DB_NAME} > /dev/null && db2 -x \"{sql}\""
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout.strip(), res.returncode

def main():
    print("=" * 60)
    print("      FinSight AI — IBM Db2 Database Migrations")
    print("=" * 60)

    # 1. Verify container
    check = subprocess.run(
        ["docker", "ps", "--filter", f"name={CONTAINER_NAME}", "--filter", "status=running", "-q"],
        capture_output=True, text=True
    )
    if not check.stdout.strip():
        print(f"[!] ERROR: Container '{CONTAINER_NAME}' is not running.")
        sys.exit(1)

    project_root = Path(__file__).parent.parent
    migrations_dir = project_root / "database" / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))

    print(f"Found {len(migration_files)} migration file(s).")
    subprocess.run(["docker", "exec", CONTAINER_NAME, "mkdir", "-p", "/tmp/migrations"])

    for f in migration_files:
        migration_id = f.name
        print(f"\n>>> Processing: {migration_id}")

        # Check if already applied
        check_sql = f"SELECT count(*) FROM FINSIGHT.SCHEMA_MIGRATIONS WHERE migration_id = '{migration_id}'"
        out, code = run_db2(check_sql)
        if code == 0 and out.strip() == "1":
            print(f"    [SKIPPED] {migration_id} already applied.")
            continue

        print(f"    [APPLYING] Executing {migration_id}...")
        # Copy file to container
        target = f"/tmp/migrations/{migration_id}"
        subprocess.run(["docker", "cp", str(f), f"{CONTAINER_NAME}:{target}"], check=True)

        # Run with db2 -tvf
        exec_bash = f"db2 connect to {DB_NAME} && db2 -tvf {target} && db2 \"INSERT INTO FINSIGHT.SCHEMA_MIGRATIONS (migration_id) VALUES ('{migration_id}')\" && db2 connect reset"
        exec_cmd = ["docker", "exec", "-i", CONTAINER_NAME, "su", "-", "db2inst1", "-c", exec_bash]
        res = subprocess.run(exec_cmd, capture_output=True, text=True)

        if res.returncode == 0:
            print(f"    [SUCCESS] {migration_id} applied successfully.")
        else:
            print(f"    [ERROR] Failed to apply {migration_id}:")
            print(res.stderr or res.stdout)
            sys.exit(1)

    print("\n" + "=" * 60)
    print("       All Migrations Processed Successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main()
