# dbt marts over the AsOf ledger

Three analytics tables built from the audit ledger with IBM's dbt adapter for Db2
([`ibm-dbt-db2`](https://github.com/IBM/db2-dbt)), plus tests that hold the ledger to the check's own rules.

| Model | What it holds |
|---|---|
| `stg_decisions`, `stg_claims` (views) | Decisions and claim verdicts, without any free text |
| `mart_decisions_daily` | Checks per day, document, channel and decision, with average latency |
| `mart_clause_version_outcomes` | Per clause **version**: claims checked against it, supported, contradicted, rule overrides |
| `mart_coverage_by_area` | Per document and area: how many claims no clause in force covered |

Tests (`dbt build` runs them): `unique`, `not_null`, `accepted_values` and `relationships` on the staging
models, and three audit checks in [tests/](tests/):

- `corrected_decisions_had_a_contradiction`: a CORRECTED decision with no contradicted claim is a ledger the
  check's rules cannot explain.
- `every_cited_clause_version_exists`: every `(CLAUSE_ID, CLAUSE_BUS_START)` a decision cited is still in
  `POLICY_CLAUSE` or its system-time history, after any later policy change.
- `marts_account_for_every_decision`: the daily mart adds up to the ledger.

## Run it

dbt gets its own virtualenv: `ibm-dbt-db2` 1.0.0 pins `ibm_db==3.2.8` and `dbt-core~=1.11`, while the app uses
`ibm_db` 3.3.0.

```bash
python3.12 -m venv .venv-dbt
.venv-dbt/bin/pip install -r dbt/requirements-dbt.txt
cd dbt
export DB2_PASSWORD=...            # the Db2 owner's password, as in AsOf's .env (DB2_USER defaults to db2inst1)
DBT_PROFILES_DIR=. ../.venv-dbt/bin/dbt build
```

The owner builds the marts into their own schema, `ASOF_MART` (`ASOF_MART_SCHEMA` changes it; `ASOF_SCHEMA`
points the sources at another AsOf schema). The models read decision and verdict columns only, so the
ledger's column masks never come into play.

## Verified

On 6 Nov 2026 against Db2 12.1.5 (the dev database with demo history for both domains): 5 models and 13 data
tests, `PASS=18`. To be sure the audit tests can fail, a scratch schema got one planted CORRECTED decision
whose only claim was supported: `corrected_decisions_had_a_contradiction` failed with exactly that row
(`Got 1 result`), and dbt skipped the models downstream of it. CI builds the project on IBM's stock image
on every push.
