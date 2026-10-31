import ibm_db

# Connection credentials (can use Db2 on Cloud or local Db2 container)
dsn = (
    "DATABASE=bludb;"
    "HOSTNAME=your-db2-host;"
    "PORT=50000;"
    "PROTOCOL=TCPIP;"
    "UID=your_user;"
    "PWD=your_password;"
    "SECURITY=SSL;"
)

try:
    conn = ibm_db.connect(dsn, "", "")
    print("Connected to IBM Db2 successfully!")

    # Example query
    sql = "SELECT 1 FROM SYSIBM.SYSDUMMY1"
    stmt = ibm_db.exec_immediate(conn, sql)
    result = ibm_db.fetch_both(stmt)
    print(result)

    ibm_db.close(conn)
except Exception as e:
    print("Db2 Error:", e)