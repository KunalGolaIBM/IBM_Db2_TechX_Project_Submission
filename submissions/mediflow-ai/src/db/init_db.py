from pathlib import Path
from src.config import DATA_BACKEND, DB2_HOST, DB2_PORT, DB2_DATABASE, DB2_USER, DB2_PASSWORD, DB2_SECURITY

def main():
    if DATA_BACKEND != "db2":
        raise SystemExit("Set DATA_BACKEND=db2 in .env before initialising the Db2 schema.")
    import ibm_db
    security = "Security=SSL;" if DB2_SECURITY else ""
    dsn = f"DATABASE={DB2_DATABASE};HOSTNAME={DB2_HOST};PORT={DB2_PORT};PROTOCOL=TCPIP;UID={DB2_USER};PWD={DB2_PASSWORD};{security}"
    conn = ibm_db.connect(dsn, "", "")
    ddl = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    for statement in [part.strip() for part in ddl.split(";") if part.strip()]:
        ibm_db.exec_immediate(conn, statement)
    ibm_db.commit(conn)
    print("Db2 schema created.")

if __name__ == "__main__":
    main()
