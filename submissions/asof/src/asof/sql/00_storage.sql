-- AsOf storage: its own 32K-page tablespace and bufferpool, holding every AsOf table.
-- Why 32K: a vector index key on VECTOR(384, FLOAT32) is 1,536 bytes and Db2 limits an index
-- key to a quarter of the page size, so a 4K tablespace rejects the index (SQL0614N); and a
-- ledger row (up to 30 KB of verdicts JSON) fits in one page. A dedicated tablespace also
-- keeps AsOf's I/O, backup and sizing separate from anything else in the database.
-- These are database-level objects shared by every AsOf schema (ASOF, ASOF_TEST, ...);
-- each statement is skipped when the object already exists.

-- bufferpool: ASOF_BP32K
CREATE BUFFERPOOL ASOF_BP32K SIZE AUTOMATIC PAGESIZE 32K
@

-- tablespace: ASOF_TS32K
CREATE TABLESPACE ASOF_TS32K PAGESIZE 32K MANAGED BY AUTOMATIC STORAGE BUFFERPOOL ASOF_BP32K
@
