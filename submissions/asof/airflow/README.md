# Nightly audit DAG (Apache Airflow, IBM Db2 provider)

[dags/asof_nightly_audit.py](dags/asof_nightly_audit.py) runs once a day as the least-privilege runtime user:

```
verify_chain  ->  recently_changed_clauses  ->  impact_of_change (one mapped task per clause)  ->  report
```

- **verify_chain** calls `VERIFY_CHAIN` and **fails the run** if any ledger row, link or citation does not
  verify, so a broken chain pages someone instead of waiting for a dispute.
- **recently_changed_clauses** finds clause versions recorded in the last `lookback_hours` (a DAG param,
  default 24) through system time, leaving out the initial load.
- **impact_of_change** runs `CHANGE_IMPACT` per changed clause: past answers now stale for their date, and
  help-centre answers that need review.
- **report** runs even on a night with no changes, and logs the counts.

It uses the provider's `Db2Hook` (`apache-airflow-providers-ibm-db2`) through a small subclass: the provider's
0.1.0 `get_conn` puts the password into the connection string as `PWD=...` (a `;` in a password breaks it),
and AsOf passes credentials to the driver as arguments instead.

## Run it

Airflow gets its own virtualenv ([requirements-airflow.txt](requirements-airflow.txt)). The connection is the
runtime user, given as an environment variable so it never lands in a file:

```bash
python3.12 -m venv .venv-airflow && .venv-airflow/bin/pip install -r airflow/requirements-airflow.txt
export AIRFLOW_HOME=$(mktemp -d) AIRFLOW__CORE__LOAD_EXAMPLES=False AIRFLOW__CORE__DAGS_FOLDER=$PWD/airflow/dags
export AIRFLOW_CONN_ASOF_DB2_APP='{"conn_type": "ibmdb2", "host": "localhost", "port": 50000, "schema": "testdb", "login": "asofapp", "password": "<ASOF_APP_PASSWORD from .env>"}'
.venv-airflow/bin/airflow db migrate
.venv-airflow/bin/airflow dags test asof_nightly_audit
.venv-airflow/bin/pytest airflow/tests          # DAG import and behaviour tests
```

## Verified

On 6 Nov 2026 with Airflow 3.4.0 and provider 0.1.0 against Db2 12.1.5, after the pet fee change from the
demo: `VERIFY_CHAIN` OK over 10 rows, one changed clause (`PET-001`), and its impact `HISTORICALLY_VALID 1,
STALE 1, NEEDS_REVIEW 1`; run state `success` in 2.6 s. With `-c '{"lookback_hours": 0}'` (a quiet night) the
report still ran, with zero changes. The tests check that the folder imports cleanly, the task order, retries
and timeouts, that credentials stay out of the DSN, and that a broken chain fails the run. CI runs the tests
and a real `airflow dags test` on IBM's stock image.
