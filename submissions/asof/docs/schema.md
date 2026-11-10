# Db2 schema and storage in full

Every AsOf object in Db2: storage, backup and restore, tables, indexes, routines, triggers, views, the key queries, users and column masks. The condensed version and the DDL as Db2 holds it are in [architecture.md](../architecture.md#ibm-db2-schema--storage-design). Back to [architecture.md](../architecture.md).

Db2 Community Edition 12.1.5.0, database `TESTDB`, schema `ASOF`. Full DDL: [00_storage.sql](../src/asof/sql/00_storage.sql), [01_tables.sql](../src/asof/sql/01_tables.sql), [02_ledger_rules.sql](../src/asof/sql/02_ledger_rules.sql), [03_procedures.sql](../src/asof/sql/03_procedures.sql), [04_views.sql](../src/asof/sql/04_views.sql), [05_masks.sql](../src/asof/sql/05_masks.sql), [90_grants.sql](../src/asof/sql/90_grants.sql).

## Storage

| Object | Definition | Why |
|---|---|---|
| Bufferpool `ASOF_BP32K` | `SIZE AUTOMATIC PAGESIZE 32K` | Matches the tablespace page size |
| Tablespace `ASOF_TS32K` | `PAGESIZE 32K MANAGED BY AUTOMATIC STORAGE` | Holds every AsOf table. A 384-dim vector index key needs more than a 4K page allows, and a ledger row fits in one page |
| `IX_CLAUSE_EMBEDDING` | `CREATE VECTOR INDEX ... ON POLICY_CLAUSE (EMBEDDING) WITH DISTANCE COSINE` (type `VANN`) | Approximate nearest-neighbour search at scale; the temporal query stays exact (see [vector benchmark](vector_benchmark.md)) |
| `ANSWER_LEDGER`, `CLAIM_CITATION` | `COMPRESS YES ADAPTIVE` | Append-only, repetitive rows |
| `ANSWER_LEDGER` partitions | `PARTITION BY RANGE (CREATED_AT)`: one partition per month of 2026 and 2027, plus open-ended partitions before and after | A month is the unit for partition elimination and per-partition `REORG` (measured: the month query was no faster than the unpartitioned index scan, [benchmark](ledger_benchmark.md)). The unique indexes and `IX_LEDGER_DECISION` are global; `IX_LEDGER_CREATED` and `IX_LEDGER_GROUP_CREATED` are partitioned |
| `MQT_DECISION_STATS`, `MQT_CLAIM_OUTCOMES` | `REFRESH IMMEDIATE ENABLE QUERY OPTIMIZATION` materialized query tables | The analytics views read one row per group instead of scanning the ledger; Db2 maintains them in every insert's transaction ([benchmark](ledger_benchmark.md)) |
| Statistics | `RUNSTATS ... WITH DISTRIBUTION AND SAMPLED DETAILED INDEXES ALL` in setup | Plans costed from real cardinalities; [access plans](explain/README.md) |

## Backup and restore

`python -m asof.backup drill` ([backup.py](../src/asof/backup.py)) is the recovery test, and CI runs it on IBM's stock image:

1. It takes an online backup (`BACKUP DATABASE ... ONLINE COMPRESS INCLUDE LOGS`) of a scratch database in archive-logging mode while the runtime user keeps appending.
2. It restores into a database that did not exist (`RESTORE ... INTO`), then runs `ROLLFORWARD ... TO END OF BACKUP AND STOP`.
3. It judges the copy with the ledger's own checks: `VERIFY_CHAIN`, the chain-head anchors up to the restored head (`anchor.verify(..., through=head)`), the head hash against the source, and the UPDATE trigger.

The restored copy is a point in time: the anchors written after its head are left out, but the log as a whole is still checked for tampering. Last run: 7 of 7 checks passed, 46 of the 47 rows restored (the 47th committed after the backup ended), 62 s under Rosetta ([report](backup/db2-x86_64-on-arm64__eff8e62.json)).

## Tables

```sql
-- Bitemporal policy clauses. BUSINESS_TIME: when a version applies to customers.
-- SYSTEM_TIME: when this database held the row (replay). Old rows go to POLICY_CLAUSE_HIST.
CREATE TABLE ASOF.POLICY_CLAUSE (
  CLAUSE_ID     VARCHAR(32)   NOT NULL,
  DOC_ID        VARCHAR(32)   NOT NULL,
  AREA          VARCHAR(40)   NOT NULL,
  TITLE         VARCHAR(200)  NOT NULL,
  VERSION_LABEL VARCHAR(20)   NOT NULL,
  CLAUSE_TEXT   VARCHAR(4000) NOT NULL,
  RULE_JSON     VARCHAR(2000) NOT NULL,
  EMBEDDING     VECTOR(384, FLOAT32) NOT NULL,
  CHANGE_NOTE   VARCHAR(400),
  CHANGED_BY    VARCHAR(128)  NOT NULL DEFAULT SESSION_USER,
  BUS_START     DATE          NOT NULL,
  BUS_END       DATE          NOT NULL,
  SYS_START     TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW BEGIN,
  SYS_END       TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW END,
  TRANS_ID      TIMESTAMP(12) GENERATED ALWAYS AS TRANSACTION START ID,
  PERIOD BUSINESS_TIME (BUS_START, BUS_END),
  PERIOD SYSTEM_TIME (SYS_START, SYS_END),
  CONSTRAINT PK_POLICY_CLAUSE PRIMARY KEY (CLAUSE_ID, BUSINESS_TIME WITHOUT OVERLAPS),
  CONSTRAINT FK_CLAUSE_DOC FOREIGN KEY (DOC_ID) REFERENCES ASOF.POLICY_DOC (DOC_ID),
  CONSTRAINT CK_CLAUSE_RULE_JSON CHECK (JSON_EXISTS(RULE_JSON, '$')),
  CONSTRAINT CK_CLAUSE_AREA CHECK (AREA IN ('bereavement', 'cancellation', 'change_fee', 'baggage',
                                            'refund', 'delay', 'travel_credit', 'pets', 'other',
                                            'overdraft', 'fee_refund', 'monthly_fee', 'foreign_transaction',
                                            'wire_transfer', 'atm', 'dispute', 'account_closure', 'checks')),
  CONSTRAINT CK_CLAUSE_VERSION CHECK (VERSION_LABEL LIKE 'v%')
) IN ASOF_TS32K;
CREATE TABLE ASOF.POLICY_CLAUSE_HIST LIKE ASOF.POLICY_CLAUSE IN ASOF_TS32K;
ALTER TABLE ASOF.POLICY_CLAUSE ADD VERSIONING USE HISTORY TABLE ASOF.POLICY_CLAUSE_HIST;
```

| Table | Purpose | Key constraints |
|---|---|---|
| `POLICY_DOC` | Policy documents | PK `DOC_ID` |
| `POLICY_CLAUSE` (+ `_HIST`) | Dated clause versions with embedding and rule parameters | `WITHOUT OVERLAPS` PK, FK to `POLICY_DOC`, JSON check, area enum |
| `ANSWER_LEDGER` | One row per decision (`PASS`, `CORRECTED`, `ESCALATED`, or a specialist's `REVIEWED` reply): redacted question and draft, final answer, decision, reason, model, prompt version, latency, verdict JSON, `PREV_HASH`, `ROW_HASH` | gapless `LEDGER_ID >= 1`, unique `REQUEST_ID` and `ROW_HASH`, decision and channel enums, JSON check |
| `CLAIM_CITATION` | One row per claim per check (`PASS_NO` 1 = draft, 2 = rewrite): verdict, judge verdict, rule check, clause ID, version, `BUS_START`, `SYS_START`, distance, quote | PK `(LEDGER_ID, PASS_NO, CLAIM_NO)`, FK to ledger, verdict enums, clause/date pairing check |
| `CHAIN_HEAD` | Single row: last ledger ID and hash; locked by every append | `HEAD_ID = 1` check |
| `PUBLISHED_ANSWER` | Help-centre answers with cited clause, version, `BUS_START` and the dates they cover | FK to `POLICY_DOC`, status enum, range check |
| `FAQ_KB` | Demo assistant's knowledge base, created and searched by `langchain-db2` `DB2VS` | created by `DB2VS` |
| `API_USER` | Per-user API access (`ASOF_AUTH=users`): user name, the SHA-256 of the personal token (never the token), role flags `CAN_CHECK`, `CAN_AUDIT`, `CAN_EDIT`, `CAN_REVIEW`, who created it and when it was disabled | unique token hash, lower-case hex check, 0/1 flags with at least one role; the runtime user may only `SELECT` it |
| `POLICY_DRAFT` | An uploaded policy document: the PDF as a `BLOB(4M)`, the SHA-256 Db2 computed over it, pages, extracted text (`CLOB`), the model that proposed the items, who uploaded and who decided | status enum, lower-case hex hash check, pages 1 to 50; identity without cache, so draft numbers have no gaps after a restart; written only through `ADD_POLICY_DRAFT` and `DECIDE_POLICY_DRAFT` |
| `POLICY_DRAFT_ITEM` | One proposed clause version: kind (CHANGE, NEW, UNCHANGED), clause, text, rule JSON, period, the quoted date sentence, the checks as JSON, whether a check failed, status, and the version it became | PK `(DRAFT_ID, ITEM_NO)`, FK to the draft, kind and status enums, JSON checks, `BUS_END > BUS_START`, and `STATUS <> 'APPLIED' OR (BLOCKED = 0 AND KIND <> 'UNCHANGED')` |
| `ESCALATION_REVIEW` | Which held decision a specialist answered and with which `REVIEWED` row: outcome (`SPECIALIST_CHECKED` or `SPECIALIST_JUDGMENT`), reviewer, note | PK on the held decision (answered once), unique reply row, both FKs to the ledger, a note required for a judgment, reply after the held row; append-only triggers; written only by `RESOLVE_ESCALATION` |
| `CORRECTION_NOTICE` | A correction for a customer whose answer went stale: the answer, clause, cited and current versions, customer date, the checked correction, the full notice, the check's decision and ledger row, the agent's trace, status and who decided | generated `OPEN_KEY` with unique index `UX_NOTICE_OPEN ... EXCLUDE NULL KEYS` (one open notice per answer and version), `SENT` needs a released check, FKs to the ledger; a trigger allows one change (from `PENDING`), none deleted; written only through `ADD_NOTICE` and `DECIDE_NOTICE` |
| `ANSWER_SUGGESTION` | Help-centre corrections drafted by the change-impact agent: the answer, clause, version and date it holds from, the check's decision and ledger entry, the agent's trace, and the editor's decision | status and decision enums, JSON check on the trace; written only through `ADD_SUGGESTION` and `DECIDE_SUGGESTION` |
| `DEMO_SPEND` | The public demo's live checks per UTC day ([public demo](public-demo.md)): checks admitted, the cap in force at the latest admission, model calls, input and output tokens | PK `SPEND_DAY`, non-negative counts, `CHECKS_USED <= DAILY_CAP`; the runtime user may only `SELECT` it; written only through `CLAIM_DEMO_CHECK` and `RECORD_DEMO_SPEND` |
| `BACKTEST_RUN`, `BACKTEST_ITEM`, `BACKTEST_COST` | A [backtest](backtest.md): one uploaded CSV of past answers (name, SHA-256, rows, model, deadline, status), each row's outcome derived from its ledger decision on channel `backtest`, and each contradicted claim's money difference read from the cited clause version's `RULE_JSON` | 500-row cap, outcome, channel and status enums, a ledger row for every checked outcome, one CSV row per ledger decision (`UX_BACKTEST_ITEM_LEDGER`), `DIFF_USD = STATED_USD - POLICY_USD`; items and costs append-only, a run changes only while it runs; written only through `START_BACKTEST`, `ADD_BACKTEST_ITEM`, `ADD_BACKTEST_COST` and `FINISH_BACKTEST` (11_backtest.sql) |

Indexes: the native vector index `IX_CLAUSE_EMBEDDING` (`VANN`, cosine, in `ASOF_TS32K`), `IX_CLAUSE_DOC_ASOF` on `POLICY_CLAUSE (DOC_ID, BUS_START, BUS_END)` for the as-of query (its start and stop keys are in [docs/explain/as_of_retrieval.txt](explain/as_of_retrieval.txt)), `ANSWER_SUGGESTION` by answer, `POLICY_CLAUSE_HIST (CLAUSE_ID, SYS_END)`, `ANSWER_LEDGER (CREATED_AT)`, `ANSWER_LEDGER (DECISION, LEDGER_ID)` (global), `ANSWER_LEDGER (CHANNEL, DECISION, REASON_CODE, CREATED_AT)` for `V_DECISION_STATS`, `CLAIM_CITATION (CLAUSE_ID, CLAUSE_BUS_START)`, `PUBLISHED_ANSWER (CITED_CLAUSE_ID, CITED_BUS_START)`.

## Routines, triggers and views

All routines are `LANGUAGE SQL`. They run inside the engine and execute with the owner's authority, so the runtime user needs only `EXECUTE`.

| Object | Kind | What it does |
|---|---|---|
| `APPEND_LEDGER_ROW` | SQL PL procedure, granted to no one | Locks `CHAIN_HEAD`, assigns the next gapless ID, computes the row hash in Db2, inserts the ledger row, shreds citations from the verdict JSON, moves the chain head. Rejects a ninth claim per check (SQLSTATE 75003). |
| `APPEND_LEDGER` | SQL PL procedure | The check's way in: refuses any decision but `PASS`, `CORRECTED` and `ESCALATED` (75004), then calls `APPEND_LEDGER_ROW`. |
| `RESOLVE_ESCALATION` | SQL PL procedure | A specialist's reply to a held decision: copies the question, channel and date from the held row, refuses an unknown (75050), unheld (75051) or answered (75052) decision, another document unless the route was uncertain (75053), self-review (75054), a contradiction, an unchecked detail or a failed check (75055), a missing note (75056), verdicts whose reason, date or held decision differ from what is recorded (75057) and a supported claim no longer in force for that date (75058); appends the `REVIEWED` row through `APPEND_LEDGER_ROW` and writes `ESCALATION_REVIEW`. |
| `ADD_NOTICE`, `DECIDE_NOTICE` | SQL PL procedures | Store a drafted correction notice after cross-checking the answer, the version in force, the check and that the correction is the text it released (75060 to 75062); approve or reject it once (75063), refusing a correction the check did not release (75064) or one whose policy changed again (75065). |
| `START_BACKTEST`, `ADD_BACKTEST_ITEM`, `ADD_BACKTEST_COST`, `FINISH_BACKTEST` | SQL PL procedures | A [backtest](backtest.md): open a run (a known document, 75071); record a row's outcome, derived from its ledger row after checking it is this run's check of this row (75072 to 75074); record a contradicted claim's money difference with `JSON_VALUE` on the exact clause row cited (75075 to 75077); close a run only when every row has an outcome (75078). `V_BACKTEST_RUNS` and `V_BACKTEST_CONTRADICTIONS` feed the exposure report. |
| `VERIFY_CHAIN` | SQL PL procedure | Reads the chain head first, then recomputes every hash up to it in order: consecutive IDs, each link, each row's content, the head itself, and that citations match the hashed JSON. A row past the head must be covered by the head when read again (an append that committed meanwhile); one written straight into the table is reported. So a verify running during appends never reports a false break. Returns OK or the first broken entry. A full scan, O(rows), for each call. Refuses (75030) a caller without `ASOF_TEXT_READER`, who would hash masked text. |
| `APPLY_POLICY_CHANGE` | SQL PL procedure | Validates (a version label may not repeat one in the current or the history table, 75012, since change impact tells versions apart by label), then `UPDATE ... FOR PORTION OF BUSINESS_TIME`, stamps `CHANGED_BY = SESSION_USER`, flags overlapping help-centre answers. |
| `CHANGE_IMPACT` | SQL PL procedure, dynamic result set | Stale and historically valid answers, help-centre answers to review. |
| `ADD_SUGGESTION` | SQL PL procedure | Stores a drafted help-centre correction; refuses one for an answer that does not cite the clause (75020) or a version not in force from that date (75021). The runtime user's only write path to `ANSWER_SUGGESTION`. |
| `DECIDE_SUGGESTION` | SQL PL procedure | The editor approves or rejects a suggestion. Claims it atomically (`UPDATE ... WHERE STATUS = 'PENDING'`, 75023 if already decided), refuses a draft the check did not release (75024), and publishes by splitting the help-centre answer at the change date instead of overwriting it. |
| `ADD_POLICY_DRAFT`, `ADD_POLICY_DRAFT_ITEM` | SQL PL procedures | Store an uploaded document (Db2 computes its SHA-256 and refuses a mismatch, 75040) and each proposed item (a CHANGE must name an existing clause, a NEW one an unused ID). Editor only. |
| `DECIDE_POLICY_DRAFT` | SQL PL procedure | Approves (with the accepted item numbers) or rejects a draft. Claims it atomically (75047 if already decided), refuses a blocked, unchanged or unknown item (75045) and, with API users, an approval by the uploader (75044). |
| `APPLY_DRAFT_ITEM` | SQL PL procedure | Puts one accepted item of an approved draft into force, once (75048 otherwise): `CALL APPLY_POLICY_CHANGE` for a changed clause, `INSERT` for a new one (embedded with `TO_EMBEDDING` when no vector is passed), with the version label Db2 picks and a change note naming the draft, item and file hash. |
| `CLAIM_DEMO_CHECK`, `RECORD_DEMO_SPEND` | SQL PL procedures, `EXECUTE` for the runtime user only | Admit one live check on the public demo against the day's cap, taking the UTC day from Db2's clock and the row's lock before reading the count, so sessions racing at the cap cannot both pass (75097 at the cap, 75098 for a cap out of range); add the check's model calls and tokens to its day, refusing impossible values (75098). |
| `LEDGER_ROW_HASH`, `SHA256_HEX` | SQL scalar functions | SHA-256 of the previous hash followed by the SHA-256 of every field (`HASH(..., 2)`). |
| `CLAIMS_FROM_JSON` | SQL table function | Up to 16 claims out of the verdict JSON with `JSON_TABLE`. |
| `*_NO_UPDATE`, `*_NO_DELETE` | Triggers (`SECURED` on the masked ledger) | Reject every UPDATE or DELETE on `ANSWER_LEDGER`, `CLAIM_CITATION` and `ESCALATION_REVIEW`, and DELETE on `CHAIN_HEAD` and `CORRECTION_NOTICE`, with SQLSTATE 75001; `CORRECTION_NOTICE_DECIDED_ONCE` lets a notice change only from `PENDING` to its decision. |
| `V_REVIEW_QUEUE` | View | Every held decision and, once answered, the reply's ledger row; no free text, so it is safe to count from. |
| `V_POLICY_TIMELINE` | View | Every version with key `RULE_JSON` parameters as columns, through `JSON_TABLE`. |
| `V_DECISION_STATS`, `V_CLAIM_OUTCOMES_BY_AREA`, `V_RULE_OVERRIDES` | Views | Analytics. The first two read the MQTs; `V_DECISION_STATS` takes each group's first and last time from the ends of `IX_LEDGER_GROUP_CREATED`. Same columns and values as the GROUP BY over the base tables they replaced (tested). |
| `MQT_DECISION_STATS`, `MQT_CLAIM_OUTCOMES` | Materialized query tables (`REFRESH IMMEDIATE`) | Counts and latency sums per channel, decision and reason; verdict counts per pass and area. Setup refreshes a new or pending one at once: until then Db2 refuses inserts into the base table. |
| `MQT_DOMAIN_DECISION_STATS`, `MQT_DOMAIN_CLAIM_OUTCOMES` | Materialized query tables (`REFRESH IMMEDIATE`) | The same two per policy document (`DOC_ID`), for domain-scoped readers; the claim outcomes join the ledger for it. The analytics views read these only for a reader who cannot see every domain. |
| `P_LEDGER_DOMAIN` and eight more | Row permissions (RCAC) | Each decision row is shown only to users who may see its policy domain ([row permissions](row-permissions.md)). Row access control on a base table also makes Db2 activate it on every MQT over it, with no permission: every row hidden. So each MQT has one: the two without `DOC_ID` go to the users that see every domain, the per-document two carry the domain rule. |
| `V_AUDIT_DECISIONS`, `V_AUDIT_CLAIMS` | Views | One row per decision (with claim counts) and one per checked claim with the clause version cited. With the views above, the only objects the analyst may read. |
| `M_LEDGER_QUESTION`, `M_LEDGER_DRAFT`, `M_LEDGER_FINAL`, `M_LEDGER_VERDICTS` | Column masks (RCAC) | `[masked]` for anyone without `ASOF_TEXT_READER`. Column access control is active on `ANSWER_LEDGER`. |

## Key queries

```sql
-- Clauses in force on the customer's date, ranked by meaning (retriever.py). Every value is a parameter.
SELECT c.CLAUSE_ID, c.AREA, c.TITLE, c.VERSION_LABEL, c.CLAUSE_TEXT, c.RULE_JSON, c.BUS_START, c.BUS_END, c.SYS_START,
       VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST
FROM POLICY_CLAUSE FOR BUSINESS_TIME AS OF ? AS c     -- the schema is bound with SET CURRENT SCHEMA = ?
WHERE c.DOC_ID = ?
ORDER BY DIST FETCH EXACT FIRST ? ROWS ONLY;

-- Replay: the same question against what the database held at an earlier moment.
SELECT ... FROM ASOF.POLICY_CLAUSE FOR SYSTEM_TIME AS OF ? FOR BUSINESS_TIME AS OF ? AS c WHERE ...;

-- Routing (router.py): each document's nearest three clauses in force on the date, in one statement.
SELECT R.DOC_ID, R.CLAUSE_ID, R.DIST FROM (
  SELECT D.*, ROW_NUMBER() OVER (PARTITION BY D.DOC_ID ORDER BY D.DIST) AS RN FROM (
    SELECT c.DOC_ID, c.CLAUSE_ID, VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST
    FROM POLICY_CLAUSE FOR BUSINESS_TIME AS OF ? AS c) D) R
WHERE R.RN <= ?;

-- Version diff (policy.py): two rows of one clause from anywhere in its history, side by side.
SELECT A.VERSION_LABEL, A.CLAUSE_TEXT, A.RULE_JSON, B.VERSION_LABEL, B.CLAUSE_TEXT, B.RULE_JSON,
       VECTOR_DISTANCE(A.EMBEDDING, B.EMBEDDING, COSINE)
FROM POLICY_CLAUSE FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30' AS A,
     POLICY_CLAUSE FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30' AS B
WHERE A.CLAUSE_ID = ? AND A.BUS_START = ? AND A.SYS_START = ?
  AND B.CLAUSE_ID = A.CLAUSE_ID AND B.BUS_START = ? AND B.SYS_START = ?;

-- Policy change (inside APPLY_POLICY_CHANGE): Db2 splits the row, history keeps the old one.
UPDATE ASOF.POLICY_CLAUSE FOR PORTION OF BUSINESS_TIME FROM P_FROM TO P_TO
   SET VERSION_LABEL = P_VERSION_LABEL, CLAUSE_TEXT = P_TEXT, RULE_JSON = P_RULE_JSON,
       EMBEDDING = VECTOR(P_EMBEDDING, 384, FLOAT32), CHANGE_NOTE = P_NOTE, CHANGED_BY = SESSION_USER
 WHERE CLAUSE_ID = P_CLAUSE_ID;
```

## Users and privileges

| Db2 user | Used by | Holds |
|---|---|---|
| `db2inst1` (owner) | `python -m asof.setup`, `python -m asof.db2check` | Everything; reads the ledger's text as `[masked]` like everyone but the runtime user and the reviewer |
| `asofapp` (runtime) | API, gate, UI, agents, inbox, eval | `CONNECT`; `SELECT` on the policy, ledger, help-centre, suggestion, policy-draft, FAQ, API-user, inbox and notice tables and five views; `EXECUTE` on `APPEND_LEDGER`, `VERIFY_CHAIN`, `CHANGE_IMPACT`, `ADD_SUGGESTION`, `ADD_NOTICE`; role `ASOF_TEXT_READER`. No `INSERT`, `UPDATE`, `DELETE` or DDL, no `EXECUTE` on `APPEND_LEDGER_ROW`, and none on the two procedures a person's decisions use. |
| `asofrev` (reviewer) | Sending a specialist's reply, approving or rejecting a correction notice | `CONNECT`; role `ASOF_TEXT_READER`; `EXECUTE` on `RESOLVE_ESCALATION` and `DECIDE_NOTICE`. No table privileges at all. |
| `asofedit` (policy editor) | `POST /api/policy/change`, approving drafted corrections, policy intake | `CONNECT`; `SELECT` on the policy, suggestion and policy-draft tables; `EXECUTE` on `APPLY_POLICY_CHANGE`, `CHANGE_IMPACT`, `DECIDE_SUGGESTION`, `ADD_POLICY_DRAFT`, `ADD_POLICY_DRAFT_ITEM`, `DECIDE_POLICY_DRAFT`, `APPLY_DRAFT_ITEM`; `USAGE` on the `EMBEDDER` model. No direct `INSERT`, `UPDATE` or `DELETE`. |
| `asofread` (analyst) | "Ask the ledger" | Role `ASOF_ANALYST`: `CONNECT` and `SELECT` on `V_AUDIT_DECISIONS`, `V_AUDIT_CLAIMS`, `V_POLICY_TIMELINE`, `V_DECISION_STATS`, `V_CLAIM_OUTCOMES_BY_AREA`, `V_RULE_OVERRIDES`. No tables, no procedures. |
| `asofmart` (dbt) | The optional dbt marts ([dbt/](../dbt/)) | `CONNECT`; `SELECT` on `ANSWER_LEDGER`, `CLAIM_CITATION`, `POLICY_CLAUSE`, `POLICY_CLAUSE_HIST`; `CREATETAB`; `CREATEIN`, `ALTERIN`, `DROPIN` on `ASOF_MART` only; `USE` of the 32K tablespace. Reads the ledger text as `[masked]`. |
| `PUBLIC` | | `CONNECT`, `CREATETAB`, `BINDADD`, `IMPLICIT_SCHEMA` revoked; `CREATEIN` on the AsOf schema revoked |

Column masks ([05_masks.sql](../src/asof/sql/05_masks.sql)) on `ANSWER_LEDGER.QUESTION_REDACTED`, `DRAFT_REDACTED`, `FINAL_ANSWER` and `VERDICTS_JSON` return the real value only to holders of the role `ASOF_TEXT_READER`, which setup grants to `asofapp` and `asofrev` (whose `RESOLVE_ESCALATION` call hashes the text). Everyone else reads `[masked]`, the owner included.
