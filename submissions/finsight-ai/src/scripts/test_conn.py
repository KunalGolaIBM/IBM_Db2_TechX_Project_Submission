import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env relative to script location or current directory
proj_env = Path(__file__).resolve().parents[2] / ".env"
if not proj_env.exists():
    proj_env = Path(".env")
load_dotenv(proj_env)

# Find and register clidriver/bin
import site
for p in site.getsitepackages():
    c_bin = os.path.join(p, "clidriver", "bin")
    if os.path.exists(c_bin):
        os.add_dll_directory(c_bin)
        break

# Also check uv cache site-packages
import glob
for c_bin in glob.glob(os.path.expanduser(r"~\AppData\Local\uv\cache\**\clidriver\bin"), recursive=True):
    if os.path.exists(c_bin):
        try:
            os.add_dll_directory(c_bin)
        except Exception:
            pass

import ibm_db
db = os.getenv("DB2_DATABASE", "FINDB")
host = os.getenv("DB2_HOST", "127.0.0.1")
port = os.getenv("DB2_PORT", "50000")
user = os.getenv("DB2_USER", "db2inst1")
pwd = os.getenv("DB2_PASSWORD")

conn_str = f"DATABASE={db};HOSTNAME={host};PORT={port};PROTOCOL=TCPIP;UID={user};PWD={pwd};"
conn = ibm_db.connect(conn_str, "", "")
stmt = ibm_db.exec_immediate(conn, "SELECT count(*) FROM FINSIGHT.TRANSACTIONS")
row = ibm_db.fetch_tuple(stmt)
print(f"CONNECTED TO DB2 OVER TCP! Total transactions in Db2: {row[0]}")
ibm_db.close(conn)
