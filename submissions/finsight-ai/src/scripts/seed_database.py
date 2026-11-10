#!/usr/bin/env python3
"""
FinSight AI — Database Seed Runner (seed_database.py)
Executes seed scripts against IBM Db2 container 'finsight-db2'.
"""

import sys
import subprocess
from pathlib import Path

CONTAINER_NAME = "finsight-db2"
DB_NAME = "FINDB"

def main():
    print("=" * 60)
    print("         FinSight AI — IBM Db2 Seed Population")
    print("=" * 60)

    project_root = Path(__file__).parent.parent
    seeds_dir = project_root / "database" / "seeds"
    seed_files = sorted(seeds_dir.glob("*.sql"))

    print(f"Found {len(seed_files)} seed file(s).")
    subprocess.run(["docker", "exec", CONTAINER_NAME, "mkdir", "-p", "/tmp/seeds"])

    for f in seed_files:
        seed_id = f.name
        print(f"\n>>> Applying Seed File: {seed_id}")

        target = f"/tmp/seeds/{seed_id}"
        subprocess.run(["docker", "cp", str(f), f"{CONTAINER_NAME}:{target}"], check=True)

        exec_bash = f"db2 connect to {DB_NAME} && db2 -tvf {target} && db2 connect reset"
        exec_cmd = ["docker", "exec", "-i", CONTAINER_NAME, "su", "-", "db2inst1", "-c", exec_bash]
        res = subprocess.run(exec_cmd, capture_output=True, text=True)

        if res.returncode == 0:
            print(f"    [SUCCESS] Seed {seed_id} executed successfully.")
        else:
            print(f"    [ERROR] Failed to execute seed {seed_id}:")
            print(res.stderr or res.stdout)
            sys.exit(1)

    print("\n" + "=" * 60)
    print("         Synthetic Seeds Populated Successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main()
