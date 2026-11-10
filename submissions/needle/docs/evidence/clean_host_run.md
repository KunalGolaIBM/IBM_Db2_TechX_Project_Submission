# Clean-host run (R19) and sample mode (R18)

Date: 2026-11-09 CST (log times are UTC = CST + 6 h). All output below is copied from the run logs. No value was
typed by hand.

## Result

- **Pass.** A fresh copy of the submission folder (no `.env`, `.venv`, `data/`) went
  through README steps 1-4 and the README "Sample mode" block on a Linux Docker host with no Ollama. Every
  step exited 0. Total time from the fresh copy to the end of the sample-mode block: **197 s** (200 s including
  the Db2-free tests). The Db2 image was already on
  this host, so the image download is not in that number. A real reviewer also downloads the image first (about
  2.6 GB compressed, 7.31 GB on disk).
- In the final run, `python -m pytest -q -m "not db" tests` exited 2. Pytest could not collect
  `tests/test_haystack_component.py`, because `haystack` was not yet in `requirements.txt`. After
  `haystack-ai==3.4.1` was added, a fresh copy with a fresh venv passed: **133 passed, 2 skipped, exit 0**
  (section "Db2-free tests after the requirements fix").
- Sample-mode output: as `NDL_JUNIOR`, `NEEDLE.TRIAGE` ran 9 queries with precomputed vectors. The exposure join
  found 4 AFFECTED rows (service `SVC-16`, `pyyaml==5.1`). Row permissions gave 2000 / 2000 / 1964 / 195 visible
  rows for DB2INST1 / NDL_SENIOR / NDL_JUNIOR / NDL_P10. Ground-truth queries with a hit in the top 10: 3 of 4.
- EXPLAIN of the vector leg (`FETCH APPROX FIRST 10`, literal k) at 2,000 rows chose TBSCAN + SORT: **the vector
  index was not used** at this size, as the README states.

## Host and input

| Item | Value |
|---|---|
| Host | GitHub Codespace `db2hack-needle-jj7gxr4xqg4vhw95`, Linux 6.8.0-1064-azure x86_64, 4 cores, 15 GB RAM |
| Tools | Docker Compose v5.6.1, Python 3.14.2 (system `python3`), image `icr.io/db2_community/db2:12.1.5.0` (already pulled) |
| Input | `tar` of the working folder with the same exclusions as `make_submission.ps1`: no `.env`, `.venv`, `data/`, caches, `CONTRACT.md`, `docs/PLAN.md`, internal reviews. Packaged 20:28:24 CST, SHA-256 `f5ff8167cb65ba18241c8335212ad520c5e707d228dd0c1a800386d5f8bb5788` |
| Run directory | `/tmp/judge/final5/needle` (a new directory; the archive was unpacked into it) |
| Driver | `judge_run.sh` (test harness, not part of the submission). It runs the README commands in order with `set -x` and prints every exit code |

## Deviations from the README (test host only)

The main NEEDLE Db2 container `db2` (port 50000) shared this host and was not touched.
1. `.env` was created with `cp .env.example .env`. The harness then replaced every `change_me` value with a random
   password, and set `DB2_PORT=50010` and `DB2_CONTAINER=db2judge`. The README documents both keys after this run.
   No password value appears in any log (checked with `grep -F` for each value: 0 matches).
2. `docker compose -p needlejudge -f docker-compose.yml -f ../override.yml`. The override caps memory at 6 GB and
   bind-mounts the Db2 data at `/tmp/db2judge`. The named volume would sit on the root disk (7 GB free), which the
   main `db2` container uses.
3. `/tmp` on this host has a default POSIX ACL (`other::rw-`, no `x`). The bind mount inherited it, and `db2inst1`
   could not enter `/database/config/db2inst1` (`su: warning: cannot change directory ... Permission denied`,
   `db2: command not found`, exit 127). The harness removes the ACL from `/tmp/db2judge` before start. This is a
   property of this host, not of NEEDLE. A normal named volume (README default) does not have the problem: run 1
   used one.
4. `PIP_CACHE_DIR=/tmp/judge/pipcache` keeps pip's cache off the root disk.

## Steps, times and exit codes (final run, 2026-11-10 02:28:48-02:32:08 UTC)

| README step | Command | Time | Exit |
|---|---|---|---|
| 1 | `cp .env.example .env` (+ edit) | <1 s | 0 |
| 2 | `docker compose up -d`, wait for `healthy` | 46 s to healthy | 0 |
| 3 | `bash scripts/setup_db.sh --with-users` | 46.5 s | 0 |
| 4 | `python3 -m venv .venv`, `pip install -r requirements.txt` | 39.1 s (pip) | 0 |
| Sample | `python scripts/load_in_codespace.py --sample` | 13.7 s | 0 |
| Sample | `python scripts/load_postings_in_codespace.py --sample` (prints `CHECK MATCH`) | 6.3 s | 0 |
| Sample | `python -m needle.sbom --load` | 1.3 s | 0 |
| Sample | `bash scripts/setup_db.sh --phase post` | 33.6 s | 0 |
| Sample | `python scripts/run_sample_queries.py` | 7.1 s | 0 |
| Testing | `python -m pytest -q -m "not db" tests` | 3.0 s | **2** (haystack import, see Open problems) |
| Testing | `python eval/build_queries.py --verify` | <1 s | 0 (3 slices OK) |

Disk: the root disk stayed at 7 GB free. `/tmp/db2judge` grew to 534 MB, and the venv used 852 MB.

## Where the README or the setup scripts were wrong, and the fixes

| # | Problem (observed) | Fix (file) |
|---|---|---|
| 1 | No Ollama-free path. Every route to data needed Ollama to embed about 26k documents. | Sample mode: `eval/fixtures/` (2,000 advisories, precomputed embeddings, postings, 9 query vectors; [fixtures README](../../eval/fixtures/README.md)), `--sample` in both loaders, `scripts/run_sample_queries.py`, README "Sample mode" block. Builder: `eval/build_fixtures.py` (a rebuild gave byte-identical files). |
| 2 | `docker-compose.yml` hard-coded container `needle-db2` and host port 50000. `setup_db.sh` read `DB2_CONTAINER` only from the environment. A second Db2 or a used port blocks step 2. | `container_name: ${DB2_CONTAINER:-needle-db2}`, port `${DB2_PORT:-50000}` (both from `.env`); `setup_db.sh` reads `DB2_CONTAINER` from `.env` too; README note + configuration row. |
| 3 | `setup_db.sh --phase post` after the postings loader: `ERROR in 02_bm25.sql: SQL0623N` ("A clustering index already exists on table NEEDLE.POSTING"), "Finished with errors", exit 1 (run 1). This hits the full-corpus step 6 too. | Accept SQL0623N as "already applied" in `setup_db.sh`; also in the postings loader's ignore list. |
| 4 | `setup_db.sh` skipped `03_triage_proc.sql` in both phases (run 3): no "Applying 03_triage_proc.sql" line, then `SQL0440N No authorized routine named "NEEDLE.SYNC_POSTING_ACL"` and `SQL0204N "NEEDLE.TRIAGE" is an undefined name`. Cause: `grep -vE ... \| grep -q .` under `set -o pipefail`. `grep -q` exits at the first match, the first `grep` dies of SIGPIPE, and the test returns 141. With the 10,006-byte file, the old test returned 141 in 20 of 20 tries; the other four files returned 0. | One `grep -qvE` without a pipe. The two other `cmd \| grep -q` tests in `setup_db.sh` (database exists, terminator directive) no longer pipe into `grep -q` either. |
| 5 | `04_rcac.sql` post part on a new database: `ERROR in 04_rcac.sql: SQL0556N` from 4 `REVOKE SELECT ON NEEDLE.TERM_DF / CORPUS_STATS` statements (run 4). The SQL file says SQL0556N is expected on a new database, but `setup_db.sh` treated it as an error. | Accept SQL0556N (REVOKE of a privilege that is not held) as "already applied". |
| 6 | README quickstart marker said the steps were not proven on a clean host. | Replaced with the result of this run and a link to this file. |

Review item (vector index recreated by the post step): this was checked. In every run, `setup_db.sh --phase post`
on `01_schema.sql` returned `SQL0605W reported (treated as already applied)` for the second
`CREATE VECTOR INDEX`. SQL20393N was not seen. The post step exits 0 after fixes 3-5.

## Open problems (not fixed here)

1. Resolved after the final run: `tests/test_haystack_component.py` imports `haystack`, which was not in
   `requirements.txt`. `pytest -m "not db"` stopped with `ERROR collecting tests/test_haystack_component.py` /
   `ModuleNotFoundError: No module named 'haystack'` (exit 2). The owner added `haystack-ai==3.4.1`. The re-check
   below passed.
2. Not run here: the full-corpus steps 5-6 (OSV download, Ollama embedding of about 26k documents), the Streamlit
   app, the LLM memo and `eval/run_eval.py`. They need Ollama or the full data.
3. Beyond the quickstart, `pytest -m db` against the 2,000-row sample: 34 passed, 4 failed, 2 skipped. The
   failures come from full-corpus or Ollama assumptions, not from broken SQL: `test_rcac::test_p10_sees_only_its_buckets`
   (`assert 0.05 < (195 / 26210)`, hard-coded full-corpus size), two `test_triage_router` cases (at 2,000 rows the
   router picks `deep-exact`, the test expects `approx-index`), and `test_app_db::test_sign_in_binds_to_the_typed_identity`
   (no Ollama on this host: `Max retries exceeded with url: /api/embed`).

## Run history

| Run | UTC | Snapshot | Outcome |
|---|---|---|---|
| 1 (exploration) | 01:53-02:07 | 19:52 CST | Steps 1-4 OK (healthy 46 s, setup 79 s, pip 64 s); sample load 3 min 39 s under host load average about 30; found problem 3. Named volume. |
| 2 | 02:08 | 20:07 CST | Stopped before the database existed: switched to the `/tmp` bind mount to protect the root disk. |
| 2b | 02:10 | 20:07 CST | Bind mount without the ACL fix: `setup_db.sh` exit 127 (deviation 3). |
| 2c | 02:13-02:17 | 20:07 CST | All quickstart and sample steps exit 0 (207 s); pytest exit 2 (haystack). |
| 3 | 02:19-02:22 | 20:18 CST (newer SQL from other agents) | Problem 4: `03_triage_proc.sql` skipped, post step and queries exit 1. |
| 4 | 02:24-02:27 | 20:23 CST (fix 4) | Problem 5: SQL0556N, post step exit 1; queries ran. |
| **5 (final)** | **02:28-02:32** | **20:28 CST (fix 5)** | **All quickstart and sample steps exit 0 (197 s to the end of sample mode); pytest exit 2 (haystack).** |

Cleanup: after run 5, `docker compose -p needlejudge ... down -v` removed `db2judge` and its network, and
`/tmp/db2judge` and the run copies were deleted. `docker ps -a` then listed only `db2`.

## Db2-free tests after the requirements fix (2026-11-10 02:36-02:37 UTC)

A new fresh copy (packaged 20:35:49 CST, SHA-256 `cc0f4d619ce5c280200af3be1652b28e6d4500de378f13703c7c40dc2b91dd1c`,
same exclusions), a new venv with the system Python 3.14.2, then README step 4 and the Db2-free test command:

```text
fresh copy: no .env, no data/
haystack-ai==3.4.1
+ [02:36:07] pip install -q -r requirements.txt

real	0m49.210s
+ exit code 0
+ [02:36:56] export PYTHONPATH=src
+ [02:36:56] python -m pytest -q -m 'not db' tests -p no:warnings
.....s.................................................................. [ 53%]
......s........................................................          [100%]
133 passed, 2 skipped, 40 deselected in 2.91s

real	0m5.469s
+ exit code 0
```

## Full log of the final run (verbatim)

```text
=== judge run start 2026-11-10T02:28:48+00:00 on Linux 6.8.0-1064-azure x86_64, 4 cores, 15 GB RAM ===
+ disk check (before start): root free 7 GB; /tmp free 103G
drwxr-xr-x 2 codespace codespace 4096 Nov 10 02:28 /tmp/db2judge

##### fresh copy: top-level files (t+0 s, 02:28:48)
.
..
.env.example
.gitignore
.streamlit
LICENSE
README.md
architecture.md
docker-compose.yml
docs
eval
pytest.ini
requirements.txt
scripts
sql
src
submission.json
tests
README.md
corpus_stats.json
docs.jsonl.gz
emb.jsonl.gz
manifest.json
postings.jsonl.gz
queries.jsonl.gz
raw.jsonl.gz
.env absent (expected)
data/ absent (expected)
.venv absent (expected)

##### README step 1: configuration (t+0 s, 02:28:48)
+ [02:28:48] cp .env.example .env
+ .env edited: 7 password keys set to random values (not shown); DB2_PORT=50010 DB2_CONTAINER=db2judge 

##### README step 2: Db2 container (t+0 s, 02:28:48)
+ disk check (before docker compose up): root free 7 GB; /tmp free 103G
+ [02:28:48] docker compose -p needlejudge -f docker-compose.yml -f ../override.yml up -d
 Network needlejudge_default Creating 
 Network needlejudge_default Creating 
 Network needlejudge_default Created 
 Network needlejudge_default Created 
 Container db2judge Creating 
 Container db2judge Created 
 Container db2judge Starting 
 Container db2judge Started 
  [02:28:49] health=starting
  [02:29:04] health=starting
  [02:29:19] health=starting
  [02:29:34] health=healthy
+ [02:29:34] docker compose -p needlejudge -f docker-compose.yml -f ../override.yml ps
NAME       IMAGE                               COMMAND                  SERVICE   CREATED          STATUS                    PORTS
db2judge   icr.io/db2_community/db2:12.1.5.0   "/var/db2_setup/lib/…"   db2       45 seconds ago   Up 45 seconds (healthy)   22/tcp, 55000/tcp, 60006-60007/tcp, 127.0.0.1:50010->50000/tcp
+ [02:29:34] : README step 3
+ [02:29:34] bash scripts/setup_db.sh --with-users
[setup_db 02:29:34] Waiting for the Db2 image setup to finish (marker /database/config/.shared-data/setup_complete, up to 30 min)...
[setup_db 02:29:34] Db2 image setup is complete.
Informational tokens are "DB2 v12.1.5.0", "special_85816", 
[setup_db 02:29:36] Creating database VECDB with PAGESIZE 32 K (this can take several minutes)...
DB20000I  The CREATE DATABASE command completed successfully.
[setup_db 02:30:05] USERSPACE1 page size = 32768.
[setup_db 02:30:08] EXPLAIN tables present.
[setup_db 02:30:08] User ndl_senior ready (Db2 authorization ID NDL_SENIOR).
[setup_db 02:30:08] User ndl_junior ready (Db2 authorization ID NDL_JUNIOR).
[setup_db 02:30:09] User ndl_p10 ready (Db2 authorization ID NDL_P10).
[setup_db 02:30:09] User ndl_p25 ready (Db2 authorization ID NDL_P25).
[setup_db 02:30:09] User ndl_p50 ready (Db2 authorization ID NDL_P50).
[setup_db 02:30:09] User ndl_p75 ready (Db2 authorization ID NDL_P75).
[setup_db 02:30:09] Applying 01_schema.sql (pre) -> /tmp/judge/final5/needle/data/logs/setup_pre_01_schema_20261110_023009.log
[setup_db 02:30:12]   OK
[setup_db 02:30:12] Applying 02_bm25.sql (pre) -> /tmp/judge/final5/needle/data/logs/setup_pre_02_bm25_20261110_023012.log
[setup_db 02:30:14]   OK
[setup_db 02:30:14] Applying 03_triage_proc.sql (pre) -> /tmp/judge/final5/needle/data/logs/setup_pre_03_triage_proc_20261110_023014.log
[setup_db 02:30:16]   OK
[setup_db 02:30:16] Applying 04_rcac.sql (pre) -> /tmp/judge/final5/needle/data/logs/setup_pre_04_rcac_20261110_023016.log
[setup_db 02:30:18]   warning SQL0100W (see log).
[setup_db 02:30:18]   OK
[setup_db 02:30:18] Applying 05_sbom_temporal.sql (pre) -> /tmp/judge/final5/needle/data/logs/setup_pre_05_sbom_temporal_20261110_023018.log
[setup_db 02:30:21]   OK
[setup_db 02:30:21] Finished: database VECDB, mode pre, 5 file(s).

real	0m46.489s
user	0m0.617s
sys	0m0.639s
+ exit code 0
+ disk check (after setup_db.sh): root free 7 GB; /tmp free 103G
du: cannot read directory '/tmp/db2judge/config/db2fenc1': Permission denied
438M	/tmp/db2judge

##### README step 4: Python environment (t+93 s, 02:30:21)
+ [02:30:21] python3 --version
Python 3.14.2
+ [02:30:21] python3 -m venv .venv
+ [02:30:24] pip install -q -r requirements.txt

[notice] A new release of pip is available: 25.3 -> 26.3
[notice] To update, run: pip install --upgrade pip

real	0m39.130s
user	0m35.434s
sys	0m2.834s
+ exit code 0
+ [02:31:03] export PYTHONPATH=src
+ [02:31:03] PYTHONPATH=src
+ [02:31:03] pip list
+ [02:31:03] grep -iE '^(ibm.db|langchain-core|numpy|pandas|streamlit|pytest) '
ibm_db                    3.3.0
langchain-core            1.7.6
numpy                     2.5.4
pandas                    3.1.1
pytest                    9.2.0
streamlit                 1.67.0

##### README Sample mode (t+135 s, 02:31:03)
+ set -a; . ./.env; set +a   (environment loaded; values not shown)
+ [02:31:03] python scripts/load_in_codespace.py --sample
SAMPLE MODE: loading the frozen fixtures in /tmp/judge/final5/needle/eval/fixtures
[ddl] exists, skipped: CREATE SCHEMA NEEDLE
[ddl] exists, skipped: CREATE TABLE NEEDLE.ADV_RAW (
[ddl] exists, skipped: CREATE TABLE NEEDLE.ADV_DOC (
[ddl] exists, skipped: CREATE INDEX NEEDLE.ADV_DOC_CANON ON NEEDLE.ADV_DOC (CANON_ID)
[ddl] exists, skipped: CREATE TABLE NEEDLE.ADV_ALIAS (
[ddl] exists, skipped: CREATE INDEX NEEDLE.ADV_ALIAS_ALIAS ON NEEDLE.ADV_ALIAS (ALIAS)
[ddl] exists, skipped: CREATE TABLE NEEDLE.ADV_AFFECTED (
[ddl] exists, skipped: CREATE INDEX NEEDLE.ADV_AFFECTED_PV ON NEEDLE.ADV_AFFECTED (PACKAGE, VERSION)
LOADED NEEDLE.ADV_RAW: inserted=2000 skipped_existing_ids=0 time=1.1s total_rows=2000
LOADED NEEDLE.ADV_DOC: inserted=2000 skipped_existing_ids=0 time=1.9s total_rows=2000 non_withdrawn_without_embedding=0
LOADED NEEDLE.ADV_ALIAS: inserted=3944 skipped_existing_ids=0 time=0.1s total_rows=3944
[affected] 29165 rows 1s (35390 rows/s)
[affected] 63302 rows 2s (37534 rows/s)
[affected] 94170 rows 3s (37565 rows/s)
[affected] 124134 rows 3s (36822 rows/s)
[affected] 156664 rows 4s (36903 rows/s)
LOADED NEEDLE.ADV_AFFECTED: inserted=169390 skipped_existing_ids=0 time=4.6s total_rows=169390
[post] OK 3.8s: CREATE VECTOR INDEX NEEDLE.ADV_DOC_VIX ON NEEDLE.ADV_DOC (EMB) WITH DISTANCE COSINE
[post] OK 0.1s: CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE NEEDLE.ADV_DOC WITH DISTRIBUTION AND INDEXES ALL
[post] OK 0.0s: CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE NEEDLE.ADV_ALIAS WITH DISTRIBUTION AND INDEXES A
[post] OK 0.0s: CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE NEEDLE.ADV_AFFECTED WITH DISTRIBUTION AND INDEXE
[post] OK 0.0s: CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE NEEDLE.ADV_RAW')
POST_LOAD time=4.0s
ALL DONE 11.8s

real	0m13.657s
user	0m3.982s
sys	0m0.139s
+ exit code 0
+ [02:31:17] python scripts/load_postings_in_codespace.py --sample
SAMPLE MODE: loading the frozen fixtures in /tmp/judge/final5/needle/eval/fixtures
[ddl] exists/skipped: CREATE TABLE NEEDLE.POSTING ( TERM VARCHAR(128) NOT NULL, ADV_ID VARCHAR(64) NOT NULL, TF SMALLINT N (SQL0601N )
[ddl] exists/skipped: CREATE TABLE NEEDLE.TERM_DF ( TERM VARCHAR(128) NOT NULL PRIMARY KEY, DF INTEGER NOT NULL ) (SQL0601N )
[ddl] exists/skipped: CREATE TABLE NEEDLE.CORPUS_STATS ( ID SMALLINT NOT NULL PRIMARY KEY CHECK (ID = 1), N INTEGER NOT NU (SQL0601N )
[load] ADV_DOC rows=2000 with EMBARGO_UNTIL set=0
LOADED NEEDLE.POSTING rows=180282 skipped_not_in_adv_doc=0 time=3.6s
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

real	0m6.279s
user	0m2.618s
sys	0m0.044s
+ exit code 0
+ [02:31:23] python -m needle.sbom --load
services=20 components=306 deployed_now=91 seed=2026
{'SERVICE': 20, 'SBOM_COMPONENT': 306}

real	0m1.288s
user	0m0.132s
sys	0m0.026s
+ exit code 0
+ [02:31:24] bash scripts/setup_db.sh --phase post
[setup_db 02:31:24] Waiting for the Db2 image setup to finish (marker /database/config/.shared-data/setup_complete, up to 30 min)...
[setup_db 02:31:25] Db2 image setup is complete.
Informational tokens are "DB2 v12.1.5.0", "special_85816", 
[setup_db 02:31:26] Database VECDB already exists.
[setup_db 02:31:28] USERSPACE1 page size = 32768.
[setup_db 02:31:30] EXPLAIN tables present.
[setup_db 02:31:30] Applying 01_schema.sql (post) -> /tmp/judge/final5/needle/data/logs/setup_post_01_schema_20261110_023130.log
[setup_db 02:31:33]   SQL0605W reported (treated as already applied).
[setup_db 02:31:33]   OK
[setup_db 02:31:33] Applying 02_bm25.sql (post) -> /tmp/judge/final5/needle/data/logs/setup_post_02_bm25_20261110_023133.log
[setup_db 02:31:36]   warning SQL0100W (see log).
[setup_db 02:31:36]   SQL0605W reported (treated as already applied).
[setup_db 02:31:36]   SQL0623N reported (treated as already applied).
[setup_db 02:31:36]   SQL0624N reported (treated as already applied).
[setup_db 02:31:36]   OK
[setup_db 02:31:36] Applying 04_rcac.sql (post) -> /tmp/judge/final5/needle/data/logs/setup_post_04_rcac_20261110_023136.log
[setup_db 02:31:56]   SQL0556N reported (treated as already applied).
[setup_db 02:31:56]   OK
[setup_db 02:31:56] Applying 05_sbom_temporal.sql (post) -> /tmp/judge/final5/needle/data/logs/setup_post_05_sbom_temporal_20261110_023156.log
[setup_db 02:31:58]   OK
[setup_db 02:31:58] Finished: database VECDB, mode post, 4 file(s).

real	0m33.633s
user	0m0.299s
sys	0m0.346s
+ exit code 0
+ [02:31:58] python scripts/run_sample_queries.py
SAMPLE MODE: 9 queries from eval/fixtures/queries.jsonl.gz, precomputed with nomic-embed-text (no Ollama call); corpus sample = 2000 advisories
visible rows in NEEDLE.ADV_DOC per user (RCAC): DB2INST1=2000  NDL_SENIOR=2000  NDL_JUNIOR=1964  NDL_P10=195

[demo:app_sample] heads up from #platform-sec: someone says the yaml loader we use in a few python services can run arbitrary co...
  user=NDL_JUNIOR k=10 depth=50 terms=22 rows=10 db_call=191 ms
   1 PYSEC-2020-96          rrf=0.03252 kw_rank=1 vec_rank=2 packages=pyyaml
   2 PYSEC-2021-142         rrf=0.03227 kw_rank=3 vec_rank=1 packages=pyyaml
   3 GHSA-6757-jp84-gxfx    rrf=0.03151 kw_rank=2 vec_rank=5 packages=pyyaml
  exposure join on the top 10 ids: 42 rows, 4 AFFECTED, services ['SVC-16']
    SVC-16 pyyaml==5.1 GHSA-6757-jp84-gxfx exposed_since=2020-02-27
    SVC-16 pyyaml==5.1 GHSA-8q59-q68h-6hv4 exposed_since=2020-02-27
    SVC-16 pyyaml==5.1 PYSEC-2020-96 exposed_since=2020-02-27

[demo:pyyaml] pyyaml full_load arbitrary code execution
  user=NDL_JUNIOR k=10 depth=50 terms=7 rows=10 db_call=48 ms
   1 PYSEC-2020-96          rrf=0.03226 kw_rank=2 vec_rank=2 packages=pyyaml
   2 PYSEC-2021-142         rrf=0.03202 kw_rank=4 vec_rank=1 packages=pyyaml
   3 GHSA-6757-jp84-gxfx    rrf=0.03154 kw_rank=1 vec_rank=6 packages=pyyaml

[demo:django_sqli] django sql injection
  user=NDL_JUNIOR k=10 depth=50 terms=3 rows=10 db_call=45 ms
   1 GHSA-3gh2-xw74-jmcw    rrf=0.03252 kw_rank=2 vec_rank=1 packages=django
   2 GHSA-w24h-v9qh-8gxj    rrf=0.03202 kw_rank=1 vec_rank=4 packages=django
   3 GHSA-2gwj-7jmv-h26r    rrf=0.03037 kw_rank=3 vec_rank=9 packages=django

[demo:mal_discord] malicious package stealing discord tokens
  user=NDL_JUNIOR k=10 depth=50 terms=5 rows=10 db_call=42 ms
   1 MAL-2024-9968          rrf=0.03227 kw_rank=1 vec_rank=3 packages=discord-react
   2 MAL-2023-1789          rrf=0.03202 kw_rank=4 vec_rank=1 packages=discord-webhookk
   3 MAL-2023-1798          rrf=0.03151 kw_rank=5 vec_rank=2 packages=discord-yp

[demo:redirect_creds] http client leaks credentials when following redirects to another host
  user=NDL_JUNIOR k=10 depth=50 terms=8 rows=10 db_call=46 ms
   1 GHSA-3x9g-8vmp-wqvf    rrf=0.03252 kw_rank=1 vec_rank=2 packages=tornado
   2 PYSEC-2026-3387        rrf=0.03200 kw_rank=2 vec_rank=3 packages=tornado
   3 GHSA-966j-vmvw-g2g9    rrf=0.03178 kw_rank=5 vec_rank=1 packages=aiohttp

[named:GHSA-cvf4-f829-762v] pgAdmin is affected by an LDAP injection vulnerability
  user=NDL_JUNIOR k=10 depth=50 terms=5 rows=10 db_call=45 ms
   1 GHSA-cvf4-f829-762v    rrf=0.03279 kw_rank=1 vec_rank=1 packages=pgadmin4
   2 PYSEC-2026-1772        rrf=0.03226 kw_rank=2 vec_rank=2 packages=pgadmin4
   3 GHSA-g283-w6fp-c4fc    rrf=0.03175 kw_rank=3 vec_rank=3 packages=apache-airflow-providers-fab
  ground truth ['GHSA-cvf4-f829-762v', 'PYSEC-2026-1772']: in top 10 = yes, rank 1

[named:GHSA-vm8q-m57g-pff3] Regular expression denial-of-service in Django
  user=NDL_JUNIOR k=10 depth=50 terms=6 rows=10 db_call=49 ms
   1 GHSA-vm8q-m57g-pff3    rrf=0.03279 kw_rank=1 vec_rank=1 packages=django
   2 GHSA-mr82-8j83-vxmv    rrf=0.03077 kw_rank=5 vec_rank=5 packages=pydantic
   3 PYSEC-2026-1812        rrf=0.03030 kw_rank=6 vec_rank=6 packages=pydantic
  ground truth ['GHSA-vm8q-m57g-pff3', 'PYSEC-2024-47']: in top 10 = yes, rank 1

[paraphrase:GHSA-cvf4-f829-762v] We’re seeing weird behavior when users enter certain inputs during login—like the system starts processing mas...
  user=NDL_JUNIOR k=10 depth=50 terms=20 rows=10 db_call=37 ms
   1 GHSA-7q62-r88r-j5gw    rrf=0.03002 kw_rank=12 vec_rank=2 packages=ethyca-fides
   2 PYSEC-2026-1335        rrf=0.02957 kw_rank=13 vec_rank=3 packages=ethyca-fides
   3 PYSEC-2025-107         rrf=0.02742 kw_rank=15 vec_rank=11 packages=django
  ground truth ['GHSA-cvf4-f829-762v', 'PYSEC-2026-1772']: in top 10 = NO

[paraphrase:GHSA-vm8q-m57g-pff3] We found a weird crash when feeding a long string with special patterns into a text truncation feature. It see...
  user=NDL_JUNIOR k=10 depth=50 terms=19 rows=10 db_call=33 ms
   1 PYSEC-2023-227         rrf=0.03200 kw_rank=2 vec_rank=3 packages=pillow
   2 PYSEC-2025-13          rrf=0.02938 kw_rank=17 vec_rank=1 packages=django
   3 GHSA-p3fp-8748-vqfq    rrf=0.02788 kw_rank=20 vec_rank=5 packages=django
  ground truth ['GHSA-vm8q-m57g-pff3', 'PYSEC-2024-47']: in top 10 = yes, rank 7

vector leg access path at 2000 rows (EXPLAIN, FETCH APPROX FIRST 10, literal k): operators=['RETURN', 'TBSCAN', 'SORT', 'NLJOIN', 'FETCH', 'IXSCAN', 'FILTER', 'NLJOIN', 'FETCH', 'IXSCAN', 'TBSCAN'] objects=['NEEDLE.ADV_DOC', 'NEEDLE.USER_ACCESS', 'SYSIBM.ACV261110023111942033_P2_O5_I3', 'SYSIBM.AGT261110023111942033_P2_O5_I3', 'SYSIBM.AIJ261110023111942033_P2_O5_I3', 'SYSIBM.SQL261110023018120'] -> vector index NOT used (cost-based choice at this size)

SAMPLE MODE OK: 9 queries ran; ground-truth queries with a hit in the top 10: 3/4

real	0m7.111s
user	0m0.187s
sys	0m0.064s
+ exit code 0
+ disk check (after sample mode): root free 7 GB; /tmp free 102G
du: cannot read directory '/tmp/db2judge/config/db2fenc1': Permission denied
534M	/tmp/db2judge
852M	/tmp/judge/final5/needle/.venv

##### README Testing & Verification (Db2-free parts) (t+197 s, 02:32:05)
+ [02:32:05] python -m pytest -q -m 'not db' tests

==================================== ERRORS ====================================
______________ ERROR collecting tests/test_haystack_component.py _______________
ImportError while importing test module '/tmp/judge/final5/needle/tests/test_haystack_component.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/home/codespace/.python/current/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_haystack_component.py:4: in <module>
    from haystack import Pipeline
E   ModuleNotFoundError: No module named 'haystack'
=============================== warnings summary ===============================
.venv/lib/python3.14/site-packages/langsmith/_internal/_beta_decorator.py:92: 13 warnings
  /tmp/judge/final5/needle/.venv/lib/python3.14/site-packages/langsmith/_internal/_beta_decorator.py:92: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead
    if asyncio.iscoroutinefunction(func):

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
ERROR tests/test_haystack_component.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
40 deselected, 13 warnings, 1 error in 1.11s

real	0m2.982s
user	0m2.896s
sys	0m0.287s
+ exit code 2
+ [02:32:08] python eval/build_queries.py --verify
named: OK n=150 sha256=afe33c07bf506c5553763fb2a119cfaf376809483f681ac4fff277fdc83ee8fb
masked: OK n=150 sha256=412cf5e0630e37bd155d7156a218be054a06d51a15dfa7e589280a61623e610b
paraphrase: OK n=150 sha256=f6e25b109378809f0203d52e8824d4d6c7bae7a3d81443ee2e5478f4f811e3dc
+ exit code 0

##### done (t+200 s, 02:32:08)
=== judge run end 2026-11-10T02:32:08+00:00; total elapsed 200 s ===
```
