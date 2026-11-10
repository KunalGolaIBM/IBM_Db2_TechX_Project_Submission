# Changelog

All work done inside the IBM Db2Hack 2026 submission window (6–10 Nov 2026, IST). New project; nothing reused from earlier hackathons.

## 2026-11-08
- Repo created. OpenAQ public-archive fetcher for 35 Delhi CAAQMS stations (`scripts/fetch_openaq.py`, no API key).
- Downloaded Sep–Dec 2025 hourly data (140 station-months). First check: Oct 2025 missing PM2.5 hours for Chandni Chowk / Punjabi Bagh / Najafgarh = 200 / 138 / 78 (ThePrint reported 224 / 123 / 100).
- Db2 Community Edition 12.1.5 running in Docker; VECTOR + VECTOR_DISTANCE smoke-tested.
- Db2 schema (`sql/01_schema.sql`): READING is a system-period temporal table, range-partitioned by month; STATION_FACT business-time table; VERDICT/EVIDENCE ledger locked by triggers; RULE_TEXT with VECTOR(384).
- CPCB breakpoints, plausibility limits and audit settings (`sql/02_reference.sql`).
- Normaliser (`src/prepare.py`) and idempotent MERGE (`sql/03_merge.sql`): 3,273,888 15-minute readings (35 stations, Sep–Dec 2025) loaded in 28 s.
- Hourly layer and audit (`sql/04_audit.sql`): BUILD_HOURLY (data capture, stuck-sensor runs, impossible jumps via window functions), SUB_INDEX function, COMPUTE_AQI_AUDITED (16-hour rule, 8-hour O3/CO, 3-pollutant rule, refusal), AUDIT_RANGE. Full Sep–Dec audit of 4,392 station-days runs in 2 min 40 s.
- First results: 34 CAAQMS stations, 698 NOT_COMPUTABLE station-days in total (121 of them the US Embassy PM2.5-only monitor). OpenAQ data is 15-minute, which changes how "missing hours" is counted; ThePrint's numbers are not reproduced exactly.
- Fix: the OpenAQ copy stores each hourly CPCB value as four 15-minute rows stamped hh:00–hh:45. Readings are now bucketed by the hour they start in, and an hour counts as valid with one plausible row. Earlier counts (508 refused station-days) were inflated by the old end-of-hour bucketing; corrected count: 247 NOT_COMPUTABLE, 190 of them still given a number by a plain average (67 of those in the Very Poor/Severe range).
- Fault-injection eval (`eval/fault_injection.py`, results in `eval/fault_injection_results.md`): 198 simulated faults planted into real clean days; AQI Truth flags 187 (94%), a min/max threshold rule 75 (38%), a plain average 0. Eval schema AQE is built from the same SQL files.
- `src/db.py` helper; tablespace creation split into `sql/00_tablespace.sql`.
- AI layer: IBM Granite 4.0 micro + granite-embedding-278m-multilingual run locally in Ollama (GGUF from Docker Hub `ai/` models; `ollama/` Modelfiles). Rule paragraphs (CPCB AQI method, CAG findings, our checks) embedded into Db2 `VECTOR(768)` (`src/rules.py`, `data/rules.json`).
- `src/explain.py`: Granite explains a verdict from the evidence ledger only; Db2 VECTOR_DISTANCE retrieval must agree with the rule the procedure cited; output rejected (template used) if it adds numbers, gives advice/predictions, or names the wrong CPCB category. Stored append-only in AQ.EXPLANATION.
- `src/ask.py` + `sql/05_views.sql`: natural-language questions → one SELECT checked by sqlglot (single SELECT, only AQ.V_DAY/AQ.V_CHECK, row cap) → run as Db2 user AQREADER that can read only those views. Out-of-scope questions (forecasts, health advice, blame) are refused.

## 2026-11-08 (later)
- Added FastAPI app (`src/app.py`): station picker, verdict card, 24-hour evidence grid, ledger, calendar, guarded question box.
- Added web UI (`web/`) with a static snapshot mode so the site works on free static hosting without Db2 running.
- Added `scripts/export_snapshot.py`; snapshot covers 1,154 station-days exported from the real Db2 audit run.

## 2026-11-08 (night)
- pytest suite against real Db2 (`tests/`): sub-index, golden-path refusal, append-only triggers, AQREADER denied base tables, temporal history, explanation guard, SQL guard. 21 passing.
- One-command setup: `src/load.py` (schema + load + MERGE + audit + rule embeddings), `docker-compose.yml` (Db2, Ollama with Granite, setup job, app), `Dockerfile`, `.env.example`, `scripts/pull_models.py`, gzipped 3-station October 2025 sample in `data/sample/`. Tested from scratch in an isolated Compose project; sample results match the full run on 91/93 station-days (the 2 differences are 31 Oct month-edge hours).
- Removed the unused business-time table AQ.STATION_FACT.
- `src/ask.py`: Db2 errors raised while fetching rows now return a refusal instead of a crash.
- Question-box eval (`eval/ask_eval.py`): 20 gold questions + 8 attack prompts.
- README rewritten in the official template's layout; `architecture.md` and `submission.json` added; README screenshots.
- Question box hardened: short station names are matched with LIKE, SQL comments stripped, wider out-of-scope filter (safety, children, blame), prompt hints on NULL AQI and failed checks. Eval: 12/20 before, 17/20 after (development score on the same set); 8/8 attack prompts held.
- GitHub Pages live: https://debi910.github.io/aqi-truth/
- Live site fixes after review on GitHub Pages: the question box no longer hangs in snapshot mode; it offers 9 real answers recorded from the live Db2 + Granite run (`scripts/export_asks.py`, `web/data/asks.json`), including 3 refusals. Duplicate station names (Lodhi Road, Pusa) now show their operator. Zero values in the ledger display as 0.00.
- `AQ.V_DAY` now leaves out the US Embassy PM2.5-only monitor (OpenAQ 8118), so the question box returns the same counts as the headline (190). The reading count shown is now for the 34 audited stations (3,271,122).
- Live engine for the public site: the UI can call a hosted API (`web/config.js`), shows a green "Live" banner when Db2 + Granite answer, and labels the fallback clearly when the server is offline. API: CORS for GitHub Pages, one Db2 connection per thread, one Granite call at a time, per-visitor rate limit, `/api/health`.
- `docker compose --profile public` adds Caddy for HTTPS; `deploy/vm_setup.sh` sets up a hosted demo on a fresh Ubuntu VM in one command.
- Question box: AQI rankings now use `DESC NULLS LAST` so refused (NULL) days never rank first. 23 tests pass.
- Question-box eval rerun after the view and ranking fixes: 18/20, 8/8 attacks held, no rows changed.
- GitHub Codespaces option (`.devcontainer/`, `deploy/codespace_start.sh`): full stack with a public HTTPS port, no card needed. `load.py --if-empty` so the setup job never wipes a loaded database on restart.
- `deploy/keepalive.sh`: Codespace terminal heartbeat for the judging window.
- Scheduled GitHub Actions workflow `keep-demo-alive` restarts and pings the demo Codespace every 20 minutes during the judging window (needs a CODESPACE_TOKEN secret); sshd added to the devcontainer.
- Fix: the full load in the Codespace stopped with SQL0964C (transaction log full) because one MERGE moved 3.27M rows. `load.py` now runs the same MERGE one station at a time with a commit after each, audits one month per commit, and raises LOGSECOND online. Tested on the sample: same 46/34/13 verdicts as before.
- Keep-alive job now probes `/api/ask` locally and through the public port (CORS preflight returns 200; a question takes about 55 s) and prints the start log.
- Full 34-station load finished in the live Codespace: 247 NOT_COMPUTABLE / 893 SUSPECT / 3,008 VALID, the same as the development run. README and snapshot now give the reading count the live database actually holds (1,872,155 pollutant readings; the old 3,271,122 also counted weather channels, which never enter the AQI).
- Question box speed (measured on 4 vCPUs: prompt reading ~16 s, SQL writing ~6 s, Db2 <1 s): Granite pinned in memory (`OLLAMA_KEEP_ALIVE=-1`, warmed at startup), generation stops at the end of the statement, SQL streams to the page (`/api/ask/stream`, NDJSON). A shorter prompt was tried and rejected: accuracy fell from 18/20 to 10/20.
- New append-only Db2 table `AQ.ASK_LOG` (`sql/06_asklog.sql`): every question with its SQL, outcome and timings. An identical earlier question reuses its checked SQL and Db2 runs it live (~0.1 s), labelled on the page with an "Ask Granite fresh" button. Sample questions are answered by Granite once at startup. 26 tests pass.
- New UI: Delhi map of the monitors (DataMeet outline, station coordinates from Db2), per-station day strip, tabs for explanation / hours / ledger, a staged progress view with a timer while Granite works, and a sliding Live / Recorded switch. Explanations load after the verdict instead of blocking it.
- Second public route (approved by Debi): a Cloudflare quick tunnel from the Codespace, address published by the keep-alive workflow on the `endpoint` branch; the Pages site uses whichever route answers first.
- Keep-alive job now stops the Codespace outside the judging window once nobody has woken it by hand for 60 minutes (it had kept running for hours after a test), and has a manual "stop" input. SQL box readable in dark mode.
- Keep-alive rebuilt (`deploy/keepalive_runner.sh`): GitHub's 20-minute cron fired only once in 3 hours, so the judging window is now covered by a chain of ~5.5-hour runs that hand over to each other, with the cron as a backup. A manual wake stops the Codespace when its time is up; outside the window anything left running is stopped.

## 2026-11-09
Fixes from three independent reviews (an IBM Db2 engineer, a fact-checker against ThePrint, a judge audit), plus additions.
- Tests now run with autocommit off, so their rollbacks really discard writes (the temporal test had been adding +1 to one real reading on every run).
- Reloads keep history: `src/load.py --append` MERGEs into the existing schema and re-audits only the station-days whose readings changed (`--reaudit` for all); `--if-empty` applies schema migrations to a loaded database. `SYSTOOLSPACE` is created when missing, so `ADMIN_DROP_SCHEMA` works on a fresh database.
- Least privilege: the web app connects as its own Db2 ID `AQAPP` (SELECT, INSERT on the two logs only), so it cannot `TRUNCATE` the ledgers, which triggers would not stop. New `VERDICT_NO_DELETE` and `EXPLANATION_NO_DELETE` triggers.
- Question box: Db2 query timeout (10 s, `SQL_ATTR_QUERY_TIMEOUT`), joins without a join condition refused, row cap clamped to 50.
- Row access control: a row permission on `AQ.VERDICT` hides the out-of-scope US Embassy monitor from IDs without the `AQAUDITOR` role.
- Indexes `VERDICT_DAY` and `READING_HIST_IX`; `RUNSTATS` through `ADMIN_CMD` after each load. `BUILD_HOURLY` rewritten as one window-function pass without a self-join.
- Method fixes (headline numbers changed): an hour is valid when 75% of its expected readings are plausible (3 of 4 at 15-minute cadence; copies of one hourly value count once), replacing "one reading is enough", which rested on the false premise that every 15-minute row repeats the hourly value; the last hour of the last day is no longer dropped; PM2.5/PM10 caps raised to 3,000/5,000 µg/m³ so real Diwali-night readings (up to ~2,200) are not discarded; SUSPECT now counts only pollutants that feed the AQI; ties for the prominent pollutant break in a fixed order; the reason text says jumps are flagged, not excluded. Result: 395 no-AQI station-days (247 under the old rule), 338 of them still shown by a plain average (147 as Very Poor or Severe), 708 SUSPECT. Fault-injection: 190/198 caught, 0 false alarms.
- Verifiable AQI receipts (`sql/08_receipt.sql`): each verdict gets a SHA-256 receipt from a trigger, hash-chained to the previous one; `AQ.VERIFY_RECEIPT` replays the inputs `FOR SYSTEM_TIME AS OF` the issue time; `AQ.TAMPER_TEST` shows a changed reading being caught and rolled back. New Receipt tab on the site.
- `scripts/db2_evidence.py` proves the Db2 claims against the live database and writes `docs/DB2_VERIFICATION.md`.
- README: judging-criterion table, corrected wording (hourly capture, jumps, catalog visibility, Diwali, fault-injection limits). MIT LICENSE. Removed a stray screenshot.
- Second period: 1 Oct to 5 Nov 2026 appended (`--append`, schema and history kept): 1,224 station-days, 289 no-AQI, 167 shown anyway (58 Very Poor/Severe), 81 SUSPECT. `--append` now also audits station-days with no verdict yet. `/api/stats` takes `start`/`end`; the site has a period switch; the question box knows both date ranges; `deploy/codespace_start.sh` loads the period once and, from 10 Nov, re-fetches the same days to record real CPCB revisions.

## 2026-11-10
- Add-only Db2 features (`sql/09_mqt_mask.sql`, undo in `sql/09_undo.sql`, both tested on a throwaway Db2 first): a REFRESH DEFERRED materialized query table `AQ.MQT_READING_DAY` (readings per station, pollutant and day). EXPLAIN shows the optimizer reads it instead of `AQ.READING` for a station-day count, at cost 95 versus 74,104 timerons; the loader refreshes it after each load. A column mask on `AQ.ASK_LOG.QUESTION` (`ACTIVATE COLUMN ACCESS CONTROL`) redacts e-mail addresses and phone numbers that visitors type into the question box for every ID except the auditor role, so the public "recent questions" list never shows them. Both are new checks in `scripts/db2_evidence.py` (27 of 27 pass in the sandbox).
- Real revisions, checked: the 10 Nov re-fetch of 1 Oct to 6 Nov 2026 (`data/raw/2026b`) was compared with the 8–9 Nov fetch (`data/raw/2026a`). Of 963,043 readings present in both, **0 changed value**; the only difference is 32,537 new readings for 6 Nov. The `--append` MERGE agrees: no new row in `READING_HIST`. So no receipt reports DATA_CHANGED from a real revision in this window. The tamper demo (`AQ.TAMPER_TEST`) stays a clearly labelled injected edit.
- Live-server safety (`deploy/codespace_start.sh`): an offline `db2 backup` (verified with `db2ckbkp` in the sandbox, ~10 s) runs once before any 10 Nov change. The changes are skipped if the backup fails, and no load or migration runs on the live database after 05:30 UTC on 10 Nov.
