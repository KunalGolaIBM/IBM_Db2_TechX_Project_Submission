import os
from dataclasses import dataclass
from typing import Any, List, Optional

import ibm_db
from dotenv import load_dotenv


@dataclass
class Db2Config:
    host: str
    port: str
    database: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "Db2Config":
        load_dotenv()
        return cls(
            host=os.getenv("DB2_HOST", "localhost"),
            port=os.getenv("DB2_PORT", "50000"),
            database=os.getenv("DB2_DATABASE", "SAMPLE"),
            user=os.getenv("DB2_USER", "db2inst1"),
            password=os.getenv("DB2_PASSWORD", ""),
        )


class Db2Client:
    def __init__(self, config: Optional[Db2Config] = None):
        self.config = config or Db2Config.from_env()
        self.conn = None

    def connect(self):
        dsn = (
            "DATABASE={database};HOSTNAME={host};PORT={port};PROTOCOL=TCPIP;"
            "UID={user};PWD={password};".format(
                database=self.config.database,
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
            )
        )

        try:
            self.conn = ibm_db.connect(dsn, "", "")
            return self.conn
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"Unable to connect to IBM Db2: {exc}") from exc

    def execute_query(self, sql: str) -> List[dict]:
        if not self.conn:
            self.connect()

        stmt = ibm_db.exec_immediate(self.conn, sql)
        columns = [col[0].lower() for col in ibm_db.field_names(stmt)]
        rows = []
        for row in ibm_db.fetch_both(stmt):
            rows.append(dict(zip(columns, row)))
        return rows

    def list_tables(self) -> List[str]:
        sql = "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = CURRENT SCHEMA"
        return [row["tabname"] for row in self.execute_query(sql)]
