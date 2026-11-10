# `scripts/bootstrap_codespace.sh` test

Date: 2026-11-09 CST (log times are UTC = CST + 6 h). All output is copied from the logs.

## What the script does

Run from `needle/` in a fresh Codespace: `bash scripts/bootstrap_codespace.sh [--sample | --full] [--data-dir DIR]
[--reload]`.
1. Creates `.env` from `.env.example` if it is missing. Every empty or `change_me*` password gets a random value
   (never printed). The script sets mode 600 and writes `DB2_PORT` / `DB2_CONTAINER` from the environment into `.env`.
2. Runs `docker compose up -d`. It then waits until health is `healthy` and the container log shows
   "Setup has completed." since the last container start.
3. Runs `bash scripts/setup_db.sh --with-users`.
4. Creates `.venv` and runs `pip install -r requirements.txt`.
5. Data. `--sample` (default) loads `eval/fixtures`. `--full` runs `gh release download needle-data-2026-11-09 -R
   wiiqz/IBM2026 -D data/load`, then `sha256sum -c SHA256SUMS.txt`, copies `sql/01_schema.sql` and `sql/02_bm25.sql`,
   and runs both loaders with `--dir data/load`. If the rows are already there, the load is skipped (`--reload`
   forces it).
6. Runs `python -m needle.sbom --load` and `bash scripts/setup_db.sh --phase post`.
7. Runs `db2 activate database VECDB` in the container.
8. Smoke check. Sample mode runs `scripts/run_sample_queries.py` (TRIAGE as NDL_JUNIOR, expects
   `SAMPLE MODE OK`). Full mode runs `COUNT(*)` on `NEEDLE.ADV_DOC` per user and expects every count above 0.
9. Prints `BOOTSTRAP OK` and the laptop steps: `gh codespace cp ... .env`, the SSH tunnel
   `gh codespace ssh -c <name> -- -N -L <port>:127.0.0.1:<port>`, and a warning not to use
   `gh codespace ports forward`.

Over `gh codespace ssh`, a Codespace has no `CODESPACE_NAME` and no `gh` login. The script then reads both from the
Codespace's own `/workspaces/.codespaces/shared/.env` and uses that token only for the `gh` download. The token is
never printed.

## Test setup

Host: the NEEDLE development Codespace (Linux 6.8.0-1064-azure x86_64, 4 cores, 15 GB RAM). The main container `db2`
(port 50000) was not touched. Each test unpacked a fresh copy of the folder (no `.env`, `.venv`, `data/`) into
`/tmp/boot/needle`. Environment: `COMPOSE_PROJECT_NAME=needleboot`,
`COMPOSE_FILE=docker-compose.yml:/tmp/boot/memcap.yml` (6 GB memory cap), `DB2_CONTAINER=db2boot`,
`DB2_PORT=50011`, and `--data-dir /tmp/db2boot` (the root disk had 7 GB free and stayed at 7 GB).

## Results

| Run | Command | Result | Wall time |
|---|---|---|---|
| 1 (fresh) | `bash scripts/bootstrap_codespace.sh --data-dir /tmp/db2boot` | **BOOTSTRAP OK**, exit 0; `SAMPLE MODE OK: 9 queries ran`; activate `DB20000I` | 186 s |
| 2 (re-run) | same | **BOOTSTRAP OK**, exit 0; 0 passwords generated; "data already loaded; skipping the load"; activate `SQL1490W` (already active) | 28 s |
| 3 (sample DB -> `--full`) | `... --full --data-dir /tmp/db2boot` | **FAILED**, exit 1: release download OK, 6/6 checksums OK, ADV_* loaded (26,210 docs), then the POSTING reload stopped at 1.4M rows: `SQL1476N ... rolled back because of error "-964"` (transaction log full; db2diag `ADM1822W The active transaction log is being held by dirty pages`). The default log is LOGFILSIZ 1024 x (13 + 12) files. | 274 s |
| 4 (fresh `--full`) | `... --full --data-dir /tmp/db2boot` after the log fix | Steps 1-5 OK: `UPDATE DATABASE CONFIGURATION ... completed successfully`, 6/6 checksums OK, ADV_RAW 26,842, ADV_DOC 26,210, ADV_ALIAS 35,641, ADV_AFFECTED 1,423,113, POSTING 1,944,102 in 38.2 s, `CHECK MATCH`. Step 6 hung in `CALL NEEDLE.SYNC_POSTING_ACL(?)` (`04_rcac.sql`): after 12 min the connection had read 19,033,065,894 rows, with 677 s CPU. Stopped with `force application (307)` on `db2boot` only. | 319 s to step 6, then stopped |
| 5 (re-run of 4 with the rebind fix) | `... --full --data-dir /tmp/db2boot` | **BOOTSTRAP OK**, exit 0. Load skipped (data present). `rebound NEEDLE.TRIAGE_MODE / NEEDLE.TRIAGE / NEEDLE.SYNC_POSTING_ACL`. `04_rcac.sql` post took 11 s. Activate `DB20000I`. `FULL MODE COUNTS OK`: DB2INST1 26210, NDL_SENIOR 26210, NDL_JUNIOR 26183, NDL_P10 2616. Laptop commands printed with the real Codespace name | 79 s |

`.env` mode after the runs: `-rw-------`. Password values found in the bootstrap logs: 0 (checked with `grep -F` per
value).

Fix after run 3: `scripts/setup_db.sh` now runs `db2 update db cfg for VECDB using LOGFILSIZ 16384 LOGPRIMARY 10
LOGSECOND 30` right after `create database`. It does this only for a new database, never deactivates a database,
and so cannot touch an existing one. Limit: a database created by an older `setup_db.sh` keeps the small log. On
such a database, `--full` on top of a sample load can still fill the log. Recreate the database or raise the log
by hand (`db2 update db cfg ...`, then `db2 deactivate`/`activate` on that container only).

Fix after run 4: `NEEDLE.SYNC_POSTING_ACL` holds a static MERGE. `setup_db.sh` creates the procedure in the pre
phase, on empty tables, so its package is bound with empty-table statistics. On the full corpus that plan read
about 19 billion rows. `scripts/setup_db.sh --phase post` now rebinds every NEEDLE SQL procedure first
(`CALL SYSPROC.REBIND_ROUTINE_PACKAGE('P', '<schema.name>', 'ANY')`), after the loaders' RUNSTATS. The README
full-corpus path (step 6, then `setup_db.sh --phase post`) had the same problem and gets the same fix. Sample mode
was not affected in practice (2,000 docs: the post step took about 20 s).

Not tested: one uninterrupted fresh `--full` run with both fixes. Runs 4 and 5 together cover it: run 4 did
steps 1-5 on a fresh database, and run 5 did steps 6-9 with the fix. Also not tested: a Codespace other than the
development one, and a non-draft release (the release is still a draft; the Codespace token could download it here).

Laptop steps printed by run 5 (verbatim):

```text
BOOTSTRAP OK: Db2 VECDB in container db2boot on 127.0.0.1:50011 (full data) in 79 s.
       gh codespace cp -c db2hack-needle-jj7gxr4xqg4vhw95 -e 'remote:/tmp/boot/needle/.env' needle/.env
       gh codespace ssh -c db2hack-needle-jj7gxr4xqg4vhw95 -- -N -L 50011:127.0.0.1:50011
```

Cleanup: `docker rm -f db2boot`, the `needleboot_default` network, `/tmp/db2boot` and `/tmp/boot` were removed after
run 5. `docker ps -a` then listed only `db2`.

## Run 1 (fresh, sample) output, verbatim

```text

=== [03:18:48, t+0s] 0. Checks (mode: sample)
root disk free: 7.5G

=== [03:18:48, t+0s] 1. .env
created .env from .env.example
passwords generated now: 7 (values not shown); .env mode 600
container=db2boot host_port=50011 database=VECDB

=== [03:18:48, t+0s] 2. Db2 container
Db2 data directory: /tmp/db2boot (bind mount; data/compose.datadir.yml)
compose files: docker-compose.yml:/tmp/boot/memcap.yml:data/compose.datadir.yml  project: needleboot
 Network needleboot_default Creating 
 Network needleboot_default Creating 
 Network needleboot_default Created 
 Network needleboot_default Created 
 Container db2boot Creating 
 Container db2boot Created 
 Container db2boot Starting 
 Container db2boot Started 
waiting for Db2 setup (health=healthy and a 'Setup has completed.' line since the last container start)...
  [03:18:49] health=starting
  [03:19:04] health=starting
Db2 is up: db2boot Up 30 seconds (healthy) 22/tcp, 55000/tcp, 60006-60007/tcp, 127.0.0.1:50011->50000/tcp

=== [03:19:19, t+31s] 3. Database, users, pre-load SQL
[setup_db 03:19:19] Waiting for the Db2 image setup to finish (marker /database/config/.shared-data/setup_complete, up to 30 min)...
[setup_db 03:19:19] Db2 image setup is complete.
Informational tokens are "DB2 v12.1.5.0", "special_85816", 
[setup_db 03:19:21] Creating database VECDB with PAGESIZE 32 K (this can take several minutes)...
DB20000I  The CREATE DATABASE command completed successfully.
[setup_db 03:19:49] USERSPACE1 page size = 32768.
[setup_db 03:19:51] EXPLAIN tables present.
[setup_db 03:19:51] User ndl_senior ready (Db2 authorization ID NDL_SENIOR).
[setup_db 03:19:51] User ndl_junior ready (Db2 authorization ID NDL_JUNIOR).
[setup_db 03:19:51] User ndl_p10 ready (Db2 authorization ID NDL_P10).
[setup_db 03:19:52] User ndl_p25 ready (Db2 authorization ID NDL_P25).
[setup_db 03:19:52] User ndl_p50 ready (Db2 authorization ID NDL_P50).
[setup_db 03:19:52] User ndl_p75 ready (Db2 authorization ID NDL_P75).
[setup_db 03:19:52] Applying 01_schema.sql (pre) -> /tmp/boot/needle/data/logs/setup_pre_01_schema_20261110_031952.log
[setup_db 03:19:54]   OK
[setup_db 03:19:54] Applying 02_bm25.sql (pre) -> /tmp/boot/needle/data/logs/setup_pre_02_bm25_20261110_031954.log
[setup_db 03:19:57]   OK
[setup_db 03:19:57] Applying 03_triage_proc.sql (pre) -> /tmp/boot/needle/data/logs/setup_pre_03_triage_proc_20261110_031957.log
[setup_db 03:19:59]   OK
[setup_db 03:19:59] Applying 04_rcac.sql (pre) -> /tmp/boot/needle/data/logs/setup_pre_04_rcac_20261110_031959.log
[setup_db 03:20:01]   warning SQL0100W (see log).
[setup_db 03:20:01]   OK
[setup_db 03:20:01] Applying 05_sbom_temporal.sql (pre) -> /tmp/boot/needle/data/logs/setup_pre_05_sbom_temporal_20261110_032001.log
[setup_db 03:20:04]   OK
[setup_db 03:20:04] Finished: database VECDB, mode pre, 5 file(s).

=== [03:20:04, t+76s] 4. Python environment
Python 3.14.2

=== [03:20:54, t+126s] 5. Data (sample)
NEEDLE.ADV_DOC rows=0  NEEDLE.POSTING rows=0
SAMPLE MODE: loading the frozen fixtures in /tmp/boot/needle/eval/fixtures
[ddl] exists, skipped: CREATE SCHEMA NEEDLE
[ddl] exists, skipped: CREATE TABLE NEEDLE.ADV_RAW (
[ddl] exists, skipped: CREATE TABLE NEEDLE.ADV_DOC (
[ddl] exists, skipped: CREATE INDEX NEEDLE.ADV_DOC_CANON ON NEEDLE.ADV_DOC (CANON_ID)
[ddl] exists, skipped: CREATE TABLE NEEDLE.ADV_ALIAS (
[ddl] exists, skipped: CREATE INDEX NEEDLE.ADV_ALIAS_ALIAS ON NEEDLE.ADV_ALIAS (ALIAS)
[ddl] exists, skipped: CREATE TABLE NEEDLE.ADV_AFFECTED (
[ddl] exists, skipped: CREATE INDEX NEEDLE.ADV_AFFECTED_PV ON NEEDLE.ADV_AFFECTED (PACKAGE, VERSION)
LOADED NEEDLE.ADV_RAW: inserted=2000 skipped_existing_ids=0 time=0.9s total_rows=2000
LOADED NEEDLE.ADV_DOC: inserted=2000 skipped_existing_ids=0 time=1.9s total_rows=2000 non_withdrawn_without_embedding=0
LOADED NEEDLE.ADV_ALIAS: inserted=3944 skipped_existing_ids=0 time=0.1s total_rows=3944
[affected] 29165 rows 1s (38176 rows/s)
[affected] 63302 rows 2s (38953 rows/s)
[affected] 94170 rows 2s (38851 rows/s)
[affected] 124134 rows 3s (38322 rows/s)
[affected] 156664 rows 4s (38219 rows/s)
LOADED NEEDLE.ADV_AFFECTED: inserted=169390 skipped_existing_ids=0 time=4.4s total_rows=169390
[post] OK 3.7s: CREATE VECTOR INDEX NEEDLE.ADV_DOC_VIX ON NEEDLE.ADV_DOC (EMB) WITH DISTANCE COSINE
[post] OK 0.1s: CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE NEEDLE.ADV_DOC WITH DISTRIBUTION AND INDEXES ALL
[post] OK 0.0s: CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE NEEDLE.ADV_ALIAS WITH DISTRIBUTION AND INDEXES A
[post] OK 0.0s: CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE NEEDLE.ADV_AFFECTED WITH DISTRIBUTION AND INDEXE
[post] OK 0.0s: CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE NEEDLE.ADV_RAW')
POST_LOAD time=3.9s
ALL DONE 11.4s
SAMPLE MODE: loading the frozen fixtures in /tmp/boot/needle/eval/fixtures
[ddl] exists/skipped: CREATE TABLE NEEDLE.POSTING ( TERM VARCHAR(128) NOT NULL, ADV_ID VARCHAR(64) NOT NULL, TF SMALLINT N (SQL0601N )
[ddl] exists/skipped: CREATE TABLE NEEDLE.TERM_DF ( TERM VARCHAR(128) NOT NULL PRIMARY KEY, DF INTEGER NOT NULL ) (SQL0601N )
[ddl] exists/skipped: CREATE TABLE NEEDLE.CORPUS_STATS ( ID SMALLINT NOT NULL PRIMARY KEY CHECK (ID = 1), N INTEGER NOT NU (SQL0601N )
[load] ADV_DOC rows=2000 with EMBARGO_UNTIL set=0
LOADED NEEDLE.POSTING rows=180282 skipped_not_in_adv_doc=0 time=3.5s
[post] OK 0.3s: CREATE UNIQUE INDEX NEEDLE.POSTING_PK_IX ON NEEDLE.POSTING (TERM, ADV_ID) INCLUDE (TF, BM25_DL, ROW_
[post] OK 0.0s: ALTER TABLE NEEDLE.POSTING ADD CONSTRAINT POSTING_PK PRIMARY KEY (TERM, ADV_ID)
[post] OK 0.1s: CREATE INDEX NEEDLE.POSTING_ADV_IX ON NEEDLE.POSTING (ADV_ID)
[post] OK 0.3s: MERGE INTO NEEDLE.POSTING P USING (SELECT ADV_ID, ROW_BUCKET, EMBARGO_UNTIL FROM NEEDLE.ADV_DOC) D O
[post] OK 0.0s: DELETE FROM NEEDLE.TERM_DF
[post] OK 0.1s: INSERT INTO NEEDLE.TERM_DF (TERM, DF) SELECT TERM, COUNT(*) FROM NEEDLE.POSTING WHERE EMBARGO_UNTIL 
[post] OK 0.0s: DELETE FROM NEEDLE.CORPUS_STATS
[post] OK 0.1s: INSERT INTO NEEDLE.CORPUS_STATS (ID, N, AVGDL, AVG_IDF, K1, B, EPSILON) WITH D (ADV_ID, DL) AS (SELE
[post] OK 0.1s: CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE NEEDLE.POSTING WITH DISTRIBUTION AND INDEXES ALL')
[post] OK 0.0s: CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE NEEDLE.TERM_DF WITH DISTRIBUTION AND INDEXES ALL')
[post] OK 0.0s: CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE NEEDLE.CORPUS_STATS')
CHECK db: postings=180282 acl_drift_vs_adv_doc=0 TERM_DF=28496 public_terms=28496 df_not_public_count=0 N=2000 public_docs=2000 embargoed_docs=0 AVGDL=170.8565 AVG_IDF=6.4960177433481485
CHECK py (full corpus): postings=180282 vocab=28496 N=2000 AVGDL=170.8565 AVG_IDF=6.4960177433493005
CHECK MATCH
ALL DONE 4.8s

=== [03:21:17, t+149s] 6. Synthetic fleet and post-load SQL (embargo marks, RCAC, grants)
services=20 components=306 deployed_now=91 seed=2026
{'SERVICE': 20, 'SBOM_COMPONENT': 306}
[setup_db 03:21:19] Waiting for the Db2 image setup to finish (marker /database/config/.shared-data/setup_complete, up to 30 min)...
[setup_db 03:21:19] Db2 image setup is complete.
Informational tokens are "DB2 v12.1.5.0", "special_85816", 
[setup_db 03:21:20] Database VECDB already exists.
[setup_db 03:21:22] USERSPACE1 page size = 32768.
[setup_db 03:21:24] EXPLAIN tables present.
[setup_db 03:21:25] Applying 01_schema.sql (post) -> /tmp/boot/needle/data/logs/setup_post_01_schema_20261110_032125.log
[setup_db 03:21:27]   SQL0605W reported (treated as already applied).
[setup_db 03:21:27]   OK
[setup_db 03:21:27] Applying 02_bm25.sql (post) -> /tmp/boot/needle/data/logs/setup_post_02_bm25_20261110_032127.log
[setup_db 03:21:30]   warning SQL0100W (see log).
[setup_db 03:21:30]   SQL0605W reported (treated as already applied).
[setup_db 03:21:30]   SQL0623N reported (treated as already applied).
[setup_db 03:21:30]   SQL0624N reported (treated as already applied).
[setup_db 03:21:30]   OK
[setup_db 03:21:30] Applying 04_rcac.sql (post) -> /tmp/boot/needle/data/logs/setup_post_04_rcac_20261110_032130.log
[setup_db 03:21:50]   SQL0556N reported (treated as already applied).
[setup_db 03:21:50]   OK
[setup_db 03:21:50] Applying 05_sbom_temporal.sql (post) -> /tmp/boot/needle/data/logs/setup_post_05_sbom_temporal_20261110_032150.log
[setup_db 03:21:52]   OK
[setup_db 03:21:52] Finished: database VECDB, mode post, 4 file(s).

=== [03:21:52, t+184s] 7. Activate the database
DB20000I  The ACTIVATE DATABASE command completed successfully.

=== [03:21:54, t+186s] 8. Smoke check
visible rows in NEEDLE.ADV_DOC per user (RCAC): DB2INST1=2000  NDL_SENIOR=2000  NDL_JUNIOR=1964  NDL_P10=195
  exposure join on the top 10 ids: 42 rows, 4 AFFECTED, services ['SVC-16']
vector leg access path at 2000 rows (EXPLAIN, FETCH APPROX FIRST 10, literal k): operators=['RETURN', 'TBSCAN', 'SORT', 'NLJOIN', 'FETCH', 'IXSCAN', 'FILTER', 'NLJOIN', 'FETCH', 'IXSCAN', 'TBSCAN'] ob
SAMPLE MODE OK: 9 queries ran; ground-truth queries with a hit in the top 10: 3/4

=== [03:21:54, t+186s] 9. Done

BOOTSTRAP OK: Db2 VECDB in container db2boot on 127.0.0.1:50011 (sample data) in 186 s.
Log: /tmp/boot/needle/data/logs/bootstrap_20261110_031848.log

Next steps on your laptop (from the folder that contains needle/):
  1. Copy the credentials (the file holds the generated passwords; never commit it):
       gh codespace cp -c <codespace-name, see: gh codespace list> -e 'remote:/tmp/boot/needle/.env' needle/.env
  2. Open an SSH tunnel and keep it running in its own terminal:
       gh codespace ssh -c <codespace-name, see: gh codespace list> -- -N -L 50011:127.0.0.1:50011
     Do NOT use 'gh codespace ports forward': large transfers through it hung during development. Use the SSH tunnel.
  3. With the tunnel open, the laptop reaches Db2 at localhost:50011 with the copied .env, for example:
       cd needle && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
       PYTHONPATH=src python scripts/run_sample_queries.py
       PYTHONPATH=src python -m streamlit run src/needle/app.py     # the app also needs Ollama for query embeddings
```
