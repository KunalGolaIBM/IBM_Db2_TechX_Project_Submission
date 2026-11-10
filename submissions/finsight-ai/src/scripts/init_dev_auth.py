#!/usr/bin/env python3
"""
FinSight AI — Dev Auth Initializer (init_dev_auth.py)
Seeds demo user 'usr_demo_synthetic_01' with an Argon2id password hash for 'DemoPassword123!'.
Uses OWASP recommended parameters: m=19456 KiB, t=2, p=1.
Pipes SQL directly to db2 stdin to avoid shell variable expansion of '$'.
"""

import os
import sys
import subprocess
from argon2 import PasswordHasher, Type

CONTAINER_NAME = "finsight-db2"
DB_NAME = "FINDB"
DEMO_USER_ID = "usr_demo_synthetic_01"
DEMO_EMAIL = "alex.chen.demo@finsight.internal"
DEMO_PASSWORD = "DemoPassword123!"

def exec_db2_script(script_text: str):
    cmd = ["docker", "exec", "-i", CONTAINER_NAME, "su", "-", "db2inst1", "-c", "db2 -tv"]
    res = subprocess.run(cmd, input=script_text, capture_output=True, text=True)
    return res.stdout, res.returncode

def main():
    env = os.environ.get("ENVIRONMENT", os.environ.get("VITE_APP_ENV", "development")).lower()
    if env in ["production", "prod"]:
        print("[!] FATAL: init_dev_auth.py cannot be executed in production environments.")
        sys.exit(1)

    print(f"[*] Initializing dev auth for demo user: {DEMO_EMAIL} ({DEMO_USER_ID})")
    
    ph = PasswordHasher(
        time_cost=2,
        memory_cost=19456,
        parallelism=1,
        hash_len=32,
        type=Type.ID
    )
    
    pwd_hash = ph.hash(DEMO_PASSWORD)
    print(f"[*] Generated Argon2id hash: {pwd_hash}")
    assert ph.verify(pwd_hash, DEMO_PASSWORD)
    print("[*] Verified Argon2id hash successfully.")
    
    # Db2 SQL script piped via stdin
    sql = (
        f"connect to {DB_NAME};\n"
        f"UPDATE FINSIGHT.USERS SET password_hash = '{pwd_hash}', is_active = 1, updated_at = CURRENT TIMESTAMP WHERE user_id = '{DEMO_USER_ID}';\n"
        f"SELECT user_id, email, password_hash, is_active FROM FINSIGHT.USERS WHERE user_id = '{DEMO_USER_ID}';\n"
        f"connect reset;\n"
    )
    
    out, code = exec_db2_script(sql)
    print(out)
    if code != 0:
        print("[!] Error executing Db2 script.")
        sys.exit(1)
        
    print("[✓] Demo user password_hash updated successfully in Db2.")

if __name__ == "__main__":
    main()
