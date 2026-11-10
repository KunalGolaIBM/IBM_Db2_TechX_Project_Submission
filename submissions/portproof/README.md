# PortProof

> **One-Line Pitch:** PortProof migrates PostgreSQL and MySQL SQL to Db2 and then makes Db2 itself *prove* the result — first that it compiles, then that it returns the same answers — so a migration is finished when the engine says so, not when a language model says so.

**AI proposes. Db2 proves.**

---

## Table of Contents
- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [What we measured](#what-we-measured)
- [IBM Db2 Integration](#ibm-db2-integration)
- [AI / LLM Architecture](#ai--llm-architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [Testing & Verification](#testing--verification)
- [Security](#security)
- [Screenshots & Demo](#screenshots--demo)
- [Known Limitations & Future Roadmap](#known-limitations--future-roadmap)
- [Team Members & Credits](#team-members--credits)

---

## Problem Statement

Every Db2 migration starts with a translator. IBM ships a good one —
[`db2-sqlglot-dialect`](https://pypi.org/project/db2-sqlglot-dialect/), built on
sqlglot. The trouble is not that translators are bad. It is **how they fail.**

Run the 32 real-world PostgreSQL and MySQL statements in `src/corpus.py` through
IBM's own dialect and it raises an error for **zero** of them. Hand those same
32 statements to Db2 and Db2 rejects **13**.

That gap is the problem. A loud failure is cheap: you see the exception and fix
it. A **silent** failure produces confident, clean-looking SQL that no linter
flags, no reviewer questions, and no test catches until it reaches the database —
or worse, until it runs and quietly returns different numbers.

There is a second, nastier layer. `SELECT 7 / 2` compiles everywhere. On MySQL
it is `3.5`; on Db2 and PostgreSQL it is `3`. Translating it is not an error.
*Compiling* it is not an error. It is simply wrong, and no amount of static
checking will tell you, because the SQL is valid in both dialects.

**Target users:** DBAs and platform engineers moving a workload onto Db2, and
developers who must prove to a reviewer that the migrated SQL is safe to deploy.

**Why existing tooling is insufficient:** translators (sqlglot, AWS SCT, ora2pg)
report only what they themselves could not parse. LLM-based converters add
fluency and *subtract* accountability — they will happily emit
`GROUP_CONCAT` for Db2 and sound certain doing it. Neither class of tool ever
asks the target engine whether the output is valid, and neither runs the two
statements to see if they agree.

---

## Solution Overview

PortProof treats translation as a **claim** and Db2 as the **oracle** that
judges it. Nothing is reported as migrated until the engine has said so twice.

For every statement:

1. **Translate** with IBM's `db2-sqlglot-dialect`.
2. **Prove it compiles.** Db2 `PREPARE`, server-side. Not a regex, not a parser —
   the real compiler, with a real SQLCODE.
3. **Repair, if Db2 refused.** A bounded LangGraph state machine proposes a fix,
   grounded in past repairs recalled from a Db2 `VECTOR` store, and then
   **re-submits it to Db2**. The loop has no exit that does not pass through the
   engine; an unfixable statement is reported unresolved rather than shipped.
4. **Prove the meaning.** The source statement and the Db2 statement are executed
   on both engines over **six adversarial datasets** built to break translation
   (mixed case, NULLs and empty strings, ties, integer division, empty groups).
   Rows are canonicalised and compared as a multiset — or in order, when the
   statement has `ORDER BY`.
5. **Record the verdict** through SQL PL procedures, with a SHA-256 certificate
   **computed inside Db2** over the verdict's own fields. The application never
   chooses the certificate, and the runtime identity cannot write the table.
6. **Learn — but only from proof.** A repair is embedded into the fix memory
   only if Db2 accepted it *and* the semantic proof came back EQUIVALENT. A
   repair that merely compiles teaches PortProof nothing.

The difference from an LLM SQL converter is the direction of authority. Here the
model is the *least* trusted component in the system: it proposes strings, and
Db2 decides.

---

## What we measured

Full run on Db2 Community Edition 12.1.5.0 (`python -m src.main --physical`):

```
  statements migrated       : 32
  translator reported errors : 0
  SILENT failures (clean translate, rejected by Db2): 13
  repaired and re-verified  : 13
  still failing to compile  : 0
  proven equivalent         : 24  (on 6 adversarial datasets vs duckdb(postgres-compatible))
  PROVEN DIFFERENT          : 2
  inconclusive              : 6
```

**13 silent failures out of 32.** Every one translated without complaint. Db2's
SQLCODEs: `-104`, `-182`, `-204`, `-206`, `-390`, `-440`, `-20521`.

**All 13 were repaired, and all 13 re-verified by Db2.**

**Two statements compiled on Db2 and still changed the answer** — these are the
ones only a differential proof can find:

| case | source | Db2 | source result | Db2 result |
|---|---|---|---|---|
| `postgres/int_division` | `SELECT 7 / 2 AS q` | *identical SQL* | `3.5` | `3` |
| `postgres/array_agg` | `array_agg(id)` | `LISTAGG(CAST(id AS VARCHAR(200)), ',')` | `[10, 11]` | `10,11` |

The second one is the honest part: **PortProof's own repair caused it.**
Replacing `array_agg` with `LISTAGG` makes the statement compile, and changes an
array into a delimited string. The compile oracle is satisfied; the semantic
proof is not. PortProof reports its own repair as PROVEN DIFFERENT rather than
counting it as a success — which is exactly why step 4 exists.

**Six inconclusive**, reported as inconclusive rather than as passes. The
differential source engine is DuckDB in its PostgreSQL-compatible mode, so
MySQL-only constructs (`GROUP_CONCAT`, `DATE_FORMAT`, `LIMIT a, b`) cannot be
executed on the source side. PortProof says so instead of guessing.

**The fix memory holds 9, not 13.** Learning requires `repaired AND
PROVEN_EQUIVALENT`; the four repairs that were only ever *inconclusive* are not
treated as precedent.

**Physical design, measured rather than guessed:**

```
PD_COMPRESSED: COMPRESS YES ADAPTIVE -- 63.4% fewer pages measured
(101 -> 37 pages for the same 4000 rows); Db2's own estimator agrees at 63%
and puts the ceiling at 74%, avg row 26B
```

Two independent Db2 sources — `SYSCAT.TABLES.NPAGES` after `RUNSTATS`, and
`ADMIN_GET_TAB_COMPRESS_INFO` — agreeing to within 0.4 points.

---

## IBM Db2 Integration

- **Db2 Edition & Environment:** Db2 Community Edition **12.1.5.0** in Docker
  (`icr.io/db2_community/db2`). Free, no account, no API key, no cloud
  dependency.
- **Connectors:** `ibm_db` (the compile oracle and all SQL PL calls),
  `ibm_db_dbi` (DB-API wrapper for the vector store), `langchain-db2`
  (`DB2VS`, IBM's official LangChain integration).

### The one setting that makes any of this valid

```python
# src/config.py
"DeferredPrepare=0;"
```

By default the Db2 CLI **defers `PREPARE` to execution**. `ibm_db.prepare()`
returns success on the client for SQL the server would reject — we measured it
returning "compiles" for `LIMIT 10 OFFSET 5` against a table that does not
exist. Without `DeferredPrepare=0` the compile oracle is not an oracle, and
every verdict PortProof prints is meaningless. There is a regression test that
fails if this ever changes (`test_prepare_is_a_real_server_side_compile`).

### Db2 features used, and why each one earns its place

| Feature | Where | Why Db2 specifically |
|---|---|---|
| `PREPARE` as a compile oracle | `src/db.py::compile_check` | The judgement is the engine's, not a parser's |
| `VECTOR(384, FLOAT32)` + `VECTOR_DISTANCE(..., COSINE)` | `src/fixmemory.py` | Fix recall ranked by Db2 |
| **Hybrid** vector + relational in one statement | `recall_sql` | Semantic ranking and a `JSON_VALUE` predicate evaluated together, in the engine |
| `JSON_VALUE(... RETURNING ...)` | `src/fixmemory.py` | Typed extraction from the stored metadata |
| SQL PL procedures (cursor + `CONTINUE HANDLER`) | `sql/02_procedures.sql` | The only write path into the ledger |
| `HASH(..., 2)` SHA-256 | `RECORD_VERDICT` | The certificate is computed by the engine, not chosen by the app |
| System-versioned temporal tables | `sql/01_schema.sql` | `FOR SYSTEM_TIME AS OF` — the ledger as it stood at any past instant |
| MQT `REFRESH IMMEDIATE` | `MQT_FAILURE_BY_CODE` | Failure rollup maintained by Db2 inside the same transaction |
| Expression-based index | `IX_STMT_CASEFOLD` | `UPPER(CASE_NAME)` lookups |
| `COLLATION_KEY_BIT('UCA500R1_S1')` | `src/corpus.py` | Locale-aware case-insensitive matching |
| WLM service class + thresholds | `sql/04_wlm_leash.sql` | A leash on the prover's own queries |
| `ADMIN_GET_TAB_COMPRESS_INFO`, `SYSCAT.TABLES` | `src/physical.py` | Compression measured, not estimated by a model |
| `ORGANIZE BY COLUMN` (BLU) | `src/physical.py` | Columnar availability checked on the live instance |
| `MON_GET_PKG_CACHE_STMT` | `src/physical.py` | Post-migration cost from real executions |
| Two-identity privilege split | `sql/03_grants.sql` | Enforced by Db2, not by application code |

Three of these were corrected against the live server rather than taken from
documentation, and each correction is recorded as a comment next to the code:

- `COLLATION_KEY_BIT` **works in a predicate but is rejected as an index key
  expression** (SQL0356N reason 23), so the indexable form is `UPPER(...)`.
- The compression column is **not** called `PCTPAGESSAVED`, which is what most
  documentation says. On 12.1 it is `PCTPAGESSAVED_CURRENT` /
  `PCTPAGESSAVED_ADAPTIVE`. Selecting the documented name gets SQLCODE `-206`.
- `ADMIN_GET_TAB_COMPRESS_INFO_V10` is a **specific** name, not a routine name:
  calling it directly is SQLCODE `-440`, and `GRANT EXECUTE` needs
  `ON SPECIFIC FUNCTION` or it fails with SQL0476N.

---

## AI / LLM Architecture

- **Framework:** LangChain + **LangGraph**. The repair loop is a `StateGraph`
  with nodes `prove → recall → repair → prove` and a router that can only exit
  on a Db2 `PREPARE` success or on exhausting its attempt budget.
- **Retrieval:** `langchain-db2`'s `DB2VS` over a Db2 `VECTOR(384, FLOAT32)`
  column, with `sentence-transformers/all-MiniLM-L6-v2` running locally on CPU.
  No API key, no network, nothing to pay for.
- **Model provider:** pluggable. The default is `LLM_PROVIDER=mock` — a
  **deterministic rule engine** of 14 rewrite rules (`src/llm.py`) so a judge can
  reproduce every number in this README offline with no credentials. Set
  `LLM_PROVIDER=http` with any OpenAI-compatible endpoint to use a real model;
  the loop around it is unchanged, because the loop never trusts it either way.

**Prompt-injection posture.** Model output is never executed as given. It is
stripped of prose and code fences (`clean_sql`), checked by
`src/safety.py::check_read_only`, and then handed to Db2 `PREPARE` — which
compiles but does not execute. A model that emitted `DROP TABLE` would get as
far as a rejected string. Retrieved fix-memory rows go into the prompt as
context only; they are never concatenated into SQL.

---

## Tech Stack

- **Core:** Python 3.12
- **Database:** IBM Db2 Community Edition 12.1.5.0 (Docker)
- **UI:** Streamlit (3 tabs) + a CLI (`python -m src.main`)
- **AI:** LangChain, LangGraph, langchain-db2, sentence-transformers
- **Translation:** sqlglot + `db2-sqlglot-dialect` (IBM's own)
- **Differential engine:** DuckDB (PostgreSQL-compatible source side)
- **Testing:** pytest — 106 tests

---

## Prerequisites

- Docker (for the Db2 container)
- Python >= 3.10
- ~2 GB disk for the Db2 image, ~90 MB for the local embedding model

---

## Setup & Installation

```bash
# 1. Db2 Community Edition in Docker (free, no account needed)
#    This is the image the measurements in this README were taken on.
docker run -d --name db2spike --privileged=true \
  -p 50000:50000 \
  -e LICENSE=accept -e DB2INST1_PASSWORD=<choose-one> -e DBNAME=testdb \
  icr.io/db2_community/db2:latest

# First start takes several minutes. Wait for "Setup has completed":
docker logs -f db2spike

# 2. This project
cd submissions/portproof
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Create PortProof's two least-privilege Db2 identities
bash scripts/create_db2_users.sh db2spike testdb

# 4. Build the schema, procedures, grants, MQT, WLM and vector table
python -m src.setup_db
```

`src/setup_db.py` prints every object it created and is safe to re-run.

---

## Configuration

```bash
cp .env.example .env    # then fill in the passwords you chose above
```

`.env.example` contains placeholders only. **No real credential appears anywhere
in this repository**, and `.env` is covered by the repository's `.gitignore`.

Defaults need no secrets at all: `LLM_PROVIDER=mock` uses the deterministic rule
engine and the embedding model runs locally.

---

## Running the Project

```bash
python -m src.main                  # migrate the corpus and prove it
python -m src.main --dialect mysql  # one source dialect
python -m src.main --no-prove       # compile proof only (fast)
python -m src.main --physical       # measured physical-design advice
python -m src.main --ledger         # read the Db2 ledger back

streamlit run src/app.py            # the UI
```

---

## Testing & Verification

```bash
pytest                 # 106 tests
pytest -m "not db2"    # the subset that needs no database
```

```
106 passed in 23.27s
```

The suite is in three layers, and the integration layer **skips itself cleanly**
when no database is reachable, so `pytest` passes on a laptop with no container:

- **`tests/test_unit.py`** — value canonicalisation, every repair rule, the
  read-only guard, translation of the whole corpus. No database, no network.
- **`tests/test_integration.py`** — marked `db2`. Asserts the things that would
  silently invalidate the project: that `PREPARE` is a real server-side compile,
  that it does not execute, that the runtime user gets `-551` on a direct
  `INSERT`, that the certificate is 64 hex characters from the engine, that
  system-versioning preserves history, that the MQT is refreshed by Db2, that
  the compression estimate agrees with the catalog.
- **`tests/test_ui.py`** — runs `src/app.py` through Streamlit's own `AppTest`
  harness, so "the UI works" is an assertion rather than a screenshot.

Several tests exist specifically because they *caught* a bug during development,
and each says so in its docstring. Among them:

- `test_prepare_is_a_real_server_side_compile` — the deferred-prepare trap.
- `test_canon_value_never_uses_exponent_form` — `Decimal.normalize()` renders
  `50.00` as `5E+1`, which produced **four false PROVEN DIFFERENT verdicts**
  before it was fixed. A prover that cries wolf is worth nothing.
- `test_ensure_fixture_schema_is_enough_to_resolve_unqualified_names` — the
  oracle's name-resolution context used to depend on an unrelated constructor's
  side effect, which turned valid SQL into a fake "silent failure".
- `test_failure_rollup_mqt_counts_only_failures` — `LAST_SQLCODE IS NOT NULL`
  also matches `0`, so the failure rollup was counting successes.

---

## Security

- **No secrets in code.** Only `.env.example`, placeholders only. `.env` is
  gitignored.
- **Two Db2 identities, enforced by the database.** `PPOWN` owns the schema
  (`CREATETAB`, `IMPLICIT_SCHEMA` — deliberately *not* DBADM). `PPAPP` is what
  the application runs as: `SELECT` on four objects and `EXECUTE` on three
  procedures. It cannot `INSERT`, `UPDATE` or `DELETE` any table, and it cannot
  create anything. A test asserts the `-551`.
- **Parameterised SQL everywhere it is possible.** Every value PortProof stores —
  including the SQL text under test — is bound as a parameter marker.
- **Input validation where it is not.** The statement under test *is* the input
  and cannot be parameterised, so `src/safety.py` requires a single read-only
  statement, rejects multi-statement payloads and DDL/DML keywords, and strips
  comments and string literals before checking so nothing can be smuggled past.
- **The compile oracle never executes.** `compile_check` only `PREPARE`s, and a
  test asserts that a `DELETE` which "compiles" did not delete a row.
- **Blast radius.** Semantic proofs run against the throwaway `PPTEST` schema.
- **A WLM leash** (`sql/04_wlm_leash.sql`) stops any query from the prover that
  would return more than 5 000 rows or exceed an estimated cost of 500 000.

---

## Screenshots & Demo

All captured from the running application against live Db2 12.1.5.0.

**1 — The silent failure.** The translator reports no problem; Db2 rejects it
with SQLCODE `-440`.

![Silent failure](docs/screenshots/01-silent-failure.png)

**2 — The repair loop.** Grounded in verified repairs recalled from Db2's vector
store, each attempt re-submitted to Db2, and the fix accepted only because the
engine accepted it.

![Repair loop](docs/screenshots/02-repair-loop.png)

**3 — The counterexample.** Identical SQL on both sides, both compile, and the
answers differ: `3.5` versus `3`. The verdict comes with the dataset and the two
result sets, so it can be checked rather than believed.

![Semantic counterexample](docs/screenshots/03-semantic-counterexample.png)

**4 — The ledger.** Every verdict, with a SHA-256 certificate computed inside
Db2 by `HASH(..., 2)`.

![Ledger](docs/screenshots/04-ledger.png)

**5 — MQT rollup and time travel.** The failure rollup is maintained by the
engine (`REFRESH IMMEDIATE`); the ledger can be read as it stood N seconds ago
via `FOR SYSTEM_TIME AS OF`.

![MQT and time travel](docs/screenshots/05-mqt-and-time-travel.png)

**6 — Vector recall inside Db2.** `VECTOR_DISTANCE` ranking and a `JSON_VALUE`
dialect filter in one statement.

![Vector recall](docs/screenshots/06-vector-recall.png)

**7 — Physical design, measured.** Compression cross-checked between the catalog
and Db2's own estimator; package-cache hotspots from real executions.

![Physical advice](docs/screenshots/07-physical-advice.png)

---

## Known Limitations & Future Roadmap

**Current limitations, stated plainly:**

- **The semantic proof is testing, not verification.** Six adversarial datasets
  can demonstrate difference but cannot *prove* equivalence; "PROVEN EQUIVALENT"
  means "agreed on every instance we ran", and the UI says so.
- **Six of 32 are inconclusive** because the source engine is DuckDB in
  PostgreSQL-compatible mode and cannot execute MySQL-only syntax. A real MySQL
  container would close this.
- **Without `ORDER BY`, row order is not asserted** — rows are compared as a
  multiset. This is correct, and it is reported as a note on every such verdict.
- **The default repair "model" is a deterministic rule engine**, chosen so the
  results reproduce offline with no key. It fixed 13 of 13 here; a real model
  would generalise further, and the loop is unchanged either way.
- `ADMIN_GET_TAB_COMPRESS_INFO` column names vary by Db2 version; PortProof
  tries both shapes and degrades to the catalog-measured figure.

**Next steps:** a MySQL source container to remove the inconclusive six;
`EXPLAIN` plan diffing alongside the result diff; widening the corpus to Oracle
and T-SQL; replaying a customer's real `MON_GET_PKG_CACHE_STMT` workload as the
corpus instead of a curated one.

---

## Team Members & Credits

| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Vishnu | [@ZENODIUM](https://github.com/ZENODIUM) | Everything: Db2 schema and SQL PL, compile oracle, differential prover, LangGraph repair loop, UI, tests |

**Third-party licences:** sqlglot (MIT), `db2-sqlglot-dialect` (Apache-2.0, IBM),
LangChain / LangGraph / langchain-db2 (MIT), DuckDB (MIT), Streamlit (Apache-2.0),
sentence-transformers (Apache-2.0), `ibm_db` (Apache-2.0). The
`all-MiniLM-L6-v2` model is Apache-2.0.

Built solo for the IBM Db2 TechX Summit 2026 hackathon.
