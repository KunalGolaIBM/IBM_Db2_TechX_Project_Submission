"""Create reDB's own objects and the deliberately under-indexed RETAIL demo schema, with data generated in Db2."""
from __future__ import annotations

import logging

from . import explain, ledger, memory

log = logging.getLogger("redb.seed")

RETAIL_DDL = [
    """CREATE TABLE RETAIL.CUSTOMERS (CUSTOMER_ID INTEGER NOT NULL PRIMARY KEY, FULL_NAME VARCHAR(100) NOT NULL,
       EMAIL VARCHAR(120) NOT NULL, COUNTRY CHAR(2) NOT NULL, SEGMENT VARCHAR(20) NOT NULL, SIGNUP_DATE DATE NOT NULL)""",
    """CREATE TABLE RETAIL.PRODUCTS (PRODUCT_ID INTEGER NOT NULL PRIMARY KEY, SKU VARCHAR(20) NOT NULL,
       PRODUCT_NAME VARCHAR(100) NOT NULL, CATEGORY VARCHAR(40) NOT NULL, UNIT_PRICE DECIMAL(10,2) NOT NULL)""",
    """CREATE TABLE RETAIL.ORDERS (ORDER_ID INTEGER NOT NULL PRIMARY KEY, CUSTOMER_ID INTEGER NOT NULL,
       ORDER_DATE DATE NOT NULL, STATUS VARCHAR(12) NOT NULL, CHANNEL VARCHAR(10) NOT NULL,
       TOTAL_AMOUNT DECIMAL(12,2) NOT NULL)""",
    """CREATE TABLE RETAIL.ORDER_ITEMS (ORDER_ID INTEGER NOT NULL, LINE_NO SMALLINT NOT NULL,
       PRODUCT_ID INTEGER NOT NULL, QUANTITY INTEGER NOT NULL, UNIT_PRICE DECIMAL(10,2) NOT NULL,
       PRIMARY KEY (ORDER_ID, LINE_NO))""",
    # informational constraints: not enforced, but the optimizer uses them
    """ALTER TABLE RETAIL.ORDERS ADD CONSTRAINT FK_ORD_CUST FOREIGN KEY (CUSTOMER_ID)
       REFERENCES RETAIL.CUSTOMERS NOT ENFORCED ENABLE QUERY OPTIMIZATION""",
    """ALTER TABLE RETAIL.ORDER_ITEMS ADD CONSTRAINT FK_ITEM_ORD FOREIGN KEY (ORDER_ID)
       REFERENCES RETAIL.ORDERS NOT ENFORCED ENABLE QUERY OPTIMIZATION""",
    """ALTER TABLE RETAIL.ORDER_ITEMS ADD CONSTRAINT FK_ITEM_PROD FOREIGN KEY (PRODUCT_ID)
       REFERENCES RETAIL.PRODUCTS NOT ENFORCED ENABLE QUERY OPTIMIZATION""",
]

SEQ = "WITH N(I) AS (SELECT {lo} FROM SYSIBM.SYSDUMMY1 UNION ALL SELECT I + 1 FROM N WHERE I < {hi}) "

CUSTOMERS_INS = SEQ + """SELECT I, 'Customer ' || CHAR(I), 'customer' || TRIM(CHAR(I)) || '@example.com',
  CASE MOD(I, 6) WHEN 0 THEN 'US' WHEN 1 THEN 'IN' WHEN 2 THEN 'AE' WHEN 3 THEN 'GB' WHEN 4 THEN 'DE' ELSE 'AU' END,
  CASE MOD(I, 10) WHEN 0 THEN 'ENTERPRISE' WHEN 1 THEN 'SMB' WHEN 2 THEN 'SMB' ELSE 'CONSUMER' END,
  DATE('2020-01-01') + MOD(I * 13, 1800) DAYS FROM N"""

PRODUCTS_INS = SEQ + """SELECT I, 'SKU-' || TRIM(CHAR(I)), 'Product ' || TRIM(CHAR(I)),
  CASE MOD(I, 5) WHEN 0 THEN 'BOOKS' WHEN 1 THEN 'TOYS' WHEN 2 THEN 'HOME' WHEN 3 THEN 'TECH' ELSE 'GARDEN' END,
  DECIMAL(MOD(I * 37, 9900) / 100.0 + 1, 10, 2) FROM N"""

ORDERS_INS = SEQ + """SELECT I, MOD(BIGINT(I) * 7919, {nc}) + 1, DATE('2023-01-01') + MOD(I * 37, 1000) DAYS,
  CASE MOD(I, 10) WHEN 0 THEN 'PENDING' WHEN 1 THEN 'CANCELLED' WHEN 2 THEN 'PROCESSING' ELSE 'SHIPPED' END,
  CASE MOD(I, 3) WHEN 0 THEN 'WEB' WHEN 1 THEN 'STORE' ELSE 'MOBILE' END,
  DECIMAL(MOD(BIGINT(I) * 7907, 99991) / 100.0 + 5, 12, 2) FROM N"""

ITEMS_INS = """SELECT O.ORDER_ID, L.N, MOD(O.ORDER_ID * 31 + L.N * 17, 2000) + 1, MOD(O.ORDER_ID + L.N, 5) + 1,
  DECIMAL(MOD(O.ORDER_ID * 13 + L.N, 9900) / 100.0 + 1, 10, 2)
  FROM RETAIL.ORDERS O, (VALUES 1, 2, 3) AS L(N) WHERE O.ORDER_ID BETWEEN {lo} AND {hi}"""


def _exists(db, schema: str, table: str) -> bool:
    return bool(db.scalar("SELECT COUNT(*) FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = ?", (schema, table)))


def _batched(db, table: str, select_tpl: str, total: int, batch: int, **fmt) -> None:
    for lo in range(1, total + 1, batch):
        hi = min(lo + batch - 1, total)
        db.execute(f"INSERT INTO RETAIL.{table} " + select_tpl.format(lo=lo, hi=hi, **fmt))
        log.info("  %s: %d/%d", table, hi, total)


def runstats(db, table: str) -> None:
    db.execute(f"CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE {table} WITH DISTRIBUTION AND DETAILED INDEXES ALL')")


def setup(db, scale: float = 1.0, reset: bool = False, embed_dim: int = 768, reseed: bool = False) -> list[str]:
    msgs = []
    if reseed:  # rebuild RETAIL at a new --scale
        for t in ("ORDER_ITEMS", "ORDERS", "PRODUCTS", "CUSTOMERS"):
            if _exists(db, "RETAIL", t):
                db.execute(f"DROP TABLE RETAIL.{t}")
    explain.ensure_explain_tables(db)
    # more secondary log space for the bulk load (online-configurable)
    try:
        db.execute("CALL SYSPROC.ADMIN_CMD('UPDATE DB CFG USING LOGSECOND 60')")
    except Exception as e:  # noqa: BLE001
        msgs.append(f"could not raise LOGSECOND: {str(e)[:120]}")
    if not db.scalar("SELECT COUNT(*) FROM SYSCAT.BUFFERPOOLS WHERE BPNAME = 'REDB_BP32'"):
        db.execute("CREATE BUFFERPOOL REDB_BP32 SIZE 2000 PAGESIZE 32K")
        msgs.append("created bufferpool REDB_BP32 (32K)")
    if not db.scalar("SELECT COUNT(*) FROM SYSCAT.TABLESPACES WHERE TBSPACE = 'REDB_TS32'"):
        db.execute("CREATE TABLESPACE REDB_TS32 PAGESIZE 32K MANAGED BY AUTOMATIC STORAGE BUFFERPOOL REDB_BP32")
        msgs.append("created tablespace REDB_TS32 (32K)")
    if not _exists(db, "REDB", "CHANGES"):
        for stmt in ledger.DDL:
            db.execute(stmt)
        msgs.append("created temporal ledger REDB.CHANGES (+ CHANGES_HISTORY)")
    if not _exists(db, "REDB", "TUNING_MEMORY"):
        try:
            db.execute(memory.DDL.format(dim=embed_dim))
            msgs.append("created REDB.TUNING_MEMORY with VECTOR column")
        except Exception as e:  # noqa: BLE001
            msgs.append(f"WARNING: VECTOR not supported, memory disabled: {str(e)[:160]}")

    seeded = _exists(db, "RETAIL", "ORDER_ITEMS") and db.scalar("SELECT COUNT(*) FROM RETAIL.ORDER_ITEMS") > 0
    if not seeded:  # (re)build from scratch, also cleans up after an interrupted seed
        for t in ("ORDER_ITEMS", "ORDERS", "PRODUCTS", "CUSTOMERS"):
            if _exists(db, "RETAIL", t):
                db.execute(f"DROP TABLE RETAIL.{t}")
        nc, no = int(100_000 * scale), int(400_000 * scale)
        for stmt in RETAIL_DDL:
            db.execute(stmt)
        _batched(db, "CUSTOMERS", CUSTOMERS_INS, nc, 100_000)
        _batched(db, "PRODUCTS", PRODUCTS_INS, 2_000, 2_000)
        _batched(db, "ORDERS", ORDERS_INS, no, 100_000, nc=nc)
        for lo in range(1, no + 1, 33_000):
            db.execute("INSERT INTO RETAIL.ORDER_ITEMS " + ITEMS_INS.format(lo=lo, hi=min(lo + 32_999, no)))
        for t in ("CUSTOMERS", "PRODUCTS", "ORDERS", "ORDER_ITEMS"):
            runstats(db, f"RETAIL.{t}")
        msgs.append(f"seeded RETAIL: {nc:,} customers, 2,000 products, {no:,} orders, {3 * no:,} order items")
    if reset:
        msgs += reset_demo(db)
    else:
        _legacy_index(db)
    return msgs


LEGACY_INDEX = "IX_CUSTOMERS_SIGNUP_LEGACY"


def _legacy_index(db) -> None:
    """A deliberately useless index (nothing filters on SIGNUP_DATE) for reDB to find and propose dropping."""
    if not db.scalar("SELECT COUNT(*) FROM SYSCAT.INDEXES WHERE INDSCHEMA = 'RETAIL' AND INDNAME = ?", (LEGACY_INDEX,)):
        db.execute(f'CREATE INDEX "RETAIL"."{LEGACY_INDEX}" ON "RETAIL"."CUSTOMERS" ("SIGNUP_DATE" ASC)')


def reset_demo(db) -> list[str]:
    """Drop every index reDB created and mark its ledger rows ROLLED_BACK, so the demo can be replayed."""
    msgs = []
    for r in db.query("SELECT TRIM(INDSCHEMA) AS S, TRIM(INDNAME) AS N, TRIM(TABNAME) AS T FROM SYSCAT.INDEXES "
                      "WHERE INDNAME LIKE 'REDB\\_IX\\_%' ESCAPE '\\'"):
        db.execute(f'DROP INDEX "{r["S"]}"."{r["N"]}"')
        msgs.append(f"dropped {r['S']}.{r['N']}")
        runstats(db, f"{r['S']}.{r['T']}")
    _legacy_index(db)
    if _exists(db, "REDB", "CHANGES"):
        db.execute("UPDATE REDB.CHANGES SET STATUS = 'ROLLED_BACK' "
                   "WHERE STATUS = 'APPLIED' AND KIND IN ('INDEX', 'DROP_INDEX')")
    return msgs
