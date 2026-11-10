# What building this taught us about Db2 (measured)

Hardening an AI agent against Db2 surfaced behaviours of Db2 and its tooling that anyone putting an LLM on top of
Db2 will hit. Each one below was observed in this project, measured, fixed, and is pinned by a test or a check.
Environment: IBM Db2 Community Edition 12.1.5.0 (Docker, `icr.io/db2_community/db2`), `ibm_db` / `ibm_db_dbi`,
IBM `langchain-db2` (`DB2VS`).

---

## 1. IBM `langchain-db2` over `ibm_db_dbi` can hold a table lock for the life of the process

**What happened.** With the app running, `python src/setup_db.py --reset` hung for **10 minutes**.
`SYSIBMADM.MON_LOCKWAITS` showed the reset waiting on a lock on `POLICY_KB` held by the **app's agent connection**
(`OPSAGENT`), whose unit of work had been open since a policy search an hour earlier.

**Why.** `DB2VS` is given an `ibm_db_dbi` connection, and DBI connections do **not** autocommit. A plain
`similarity_search` therefore opens a unit of work that is never ended, so its read lock on the vector table stays until
the process exits. An explicit `commit()` after each search releases it (we also switch the connection to autocommit).

**Why it matters for AI apps.** Agents are long-running processes that call the vector store repeatedly. A silently
held lock blocks schema changes, reloads of the knowledge base, and can cause lock waits for other sessions.

**Fix:** `knowledge.search_policies` commits after every search. **Proof:** `test_policy_search_leaves_no_lock_behind`
takes an `EXCLUSIVE` lock on `POLICY_KB` from another session (3 s lock timeout) right after a search.

---

## 2. An `EXPLAIN` cost guard for AI-written SQL is only as good as the statistics: 177,163 vs 1,876 timerons

**What happened.** On a freshly built database, the cost guard refused an ordinary agent query
(`SELECT OCCUPANCY_PCT FROM V_DAILY_KPIS WHERE STAY_DATE = CURRENT DATE`): Db2 estimated **177,163 timerons**, far
above our 25,000 limit. Earlier the same query had cost a few thousand.

**Why.** New tables have no statistics (`SYSCAT.TABLES.CARD = -1`, `STATS_TIME` is null), so the optimizer falls back on
defaults. Db2's automatic statistics collection fixes this, but only after a delay.

| | Estimated cost |
|---|---|
| Fresh tables, no statistics | **177,163** timerons (refused) |
| After `RUNSTATS ... WITH DISTRIBUTION AND INDEXES ALL` | **1,876** timerons (allowed) |

**Why it matters for AI apps.** Using `EXPLAIN` to stop runaway AI-generated SQL is a strong pattern, but on a new or
freshly loaded database it will **refuse legitimate questions** (about a 94× overestimate here) unless statistics are
collected at load time.

**Fix:** `setup_db.collect_statistics` runs `RUNSTATS` on every table after loading. **Proof:** `verify.py` check 14 now
costs this exact KPI query and requires it to pass the guard.

---

## 3. `JSON_VALUE ... RETURNING VARCHAR(n)` raises an error on an over-long value

**What happened.** On its very first run, our guardrail fuzzer (random proposals against `SP_PROPOSE_ACTION`) crashed
the procedure with **`SQL0137N`** on `{"to_room_type_code": "PENTHOUSE"}`, a 9-character value read with
`RETURNING VARCHAR(8)`.

**Why.** An over-long value does not come back as NULL or a truncated string: the statement fails. In a guardrail
procedure, that means a malformed or malicious payload produces a raw database error instead of a clean `REJECTED`.
Db2 still failed closed (nothing was created), but the agent got an exception instead of a reason.

**Why it matters for AI apps.** LLMs produce surprising values. Validation procedures should read JSON into wide
variables and validate lengths and domains themselves.

**Fix:** `SP_PROPOSE_ACTION` reads fields as `VARCHAR(100)` and validates them. **Proof:**
`test_guardrail_rejects_over_long_fields_cleanly`, plus `python src/fuzz_guardrails.py` (**10,000 / 10,000** decisions
match an independent oracle).

---

## 4. The Db2 Community container can fail to restart: `DBI20187E` on `fencedid`

**What happened.** After WSL restarted overnight, the container went into a restart loop. `db2icrt` failed with
**`DBI20187E` "The fencedid file ... is not owned by root:db2iadm1"**.

**Why.** The image's setup script changes `sqllib/adm/fencedid` to `root:root` after a successful start
(`/var/db2_setup/include/db2_common_functions`), but on the next start `db2icrt -update-instance-if-exists` requires
`root:db2iadm1`. So every restart after the first fails. Data is not affected.

**Fix:** `scripts/fix_db2_restart.sh` stops the container, sets the owner to `root:db2iadm1` (gid 1000 in the image)
and starts it again.

---

## Smaller ones

- `FOR SYSTEM_TIME AS OF` does not accept a scalar subquery (`SQL0104N`); fetch the timestamp first and pass it as a
  parameter.
- `OFFSET` does not accept a subquery; use `ROW_NUMBER() OVER` with `COUNT(*) OVER ()` instead.
- `COMMENT ON TABLE` is limited to 254 bytes; long semantic-layer descriptions for text-to-SQL must be kept short or
  moved to column comments.
- `UPDATE ... FOR PORTION OF BUSINESS_TIME` splits a period automatically and keeps the original row in system-time
  history, which is exactly what made the "what was the guest quoted?" query a single statement.
