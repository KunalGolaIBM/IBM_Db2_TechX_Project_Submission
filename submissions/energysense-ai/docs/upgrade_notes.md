# EnergySense AI — Round 2 upgrade notes

Prepared on 8 November 2026 from the existing EnergySense AI project.

## What changed

- Reworked the submission metadata to match the official Db2Hack nested `project`, `team` and `ibm_db2` structure.
- Expanded the test suite from the original three starter tests to 36 checks across baseline analysis, API validation, SQLite persistence, workflow event recording, Db2 DB-API parameter binding, configuration, LangChain tool registration and embedding-provider configuration.
- Fixed the Isolation-Forest-only event path so a multivariate anomaly cannot cause an empty-feature indexing failure.
- Added low-side as well as high-side baseline deviation detection, finite-number validation, bounded API inputs and consistent UTC timestamps.
- Made database transactions commit/rollback and close reliably; added appliance/time indexes and cached the configured store for the API process.
- Added a real Db2 relational write/read verification command (`python -m src.verify_db2`) that records clearly labelled synthetic test data.
- Added a LangChain `create_agent` assistant with read-only tools for telemetry, appliance analysis, Db2 maintenance retrieval and event history. No tool controls the relay.
- Added Db2 vector search via `langchain-db2` `DB2VS`, with a sentence-transformer semantic-embedding option and a lightweight offline hash-embedding option.
- Added a Streamlit monitoring dashboard, an ESP32 HTTP sender example, DB2 SQL schema/index script, architecture diagram, dedicated data-flow diagram and demo output generated from synthetic data.
- Added a device-status API endpoint that reports the latest stored telemetry and source/relay metadata without falsely inferring that a device is online.

## Verification completed here

- `python -m compileall -q src tests`: passed.
- `pytest -q`: 36 passed, 0 failed, 0 skipped (review pass).
- Local SQLite smoke test: 31 synthetic readings stored, 1 anomaly event persisted, API health/history/events routes verified.
- Official Db2Hack submission-folder validator: not independently executed during this review because GitHub clone access was blocked by unavailable outbound DNS; run it from the official repository checkout before PR creation.

## Still required on the participant's machine

1. Configure a real IBM Db2 for LUW instance and run `python -m src.verify_db2`.
2. With Db2 vector-search support (12.1.2+) install the full requirements, seed `ESAI_KNOWLEDGE` and test an actual similarity search.
3. Configure an LLM key and test the optional LangChain tool-calling agent.
4. Adapt the HTTP sender to the existing ESP32 firmware, then verify physical readings and calibration under appropriate supervision.
5. Capture genuine screenshots, update public repository/team metadata, fork the official submission repository, create a pull request and submit its URL in the official form.

No live Db2 connection, remote LLM call, physical sensor calibration or mains test is claimed by this package. The current local demo output is explicitly synthetic and uses SQLite.
