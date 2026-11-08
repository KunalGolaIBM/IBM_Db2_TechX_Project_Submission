# Local automated test and smoke-test record

Executed on 8 November 2026 in the prepared project environment (Python 3.13.5).

- Source compilation: **passed** (`python -m compileall -q src tests`).
- Automated unit/API/adapter tests: **36 passed, 0 failed, 0 skipped** (`pytest -q`).
- API + persistence smoke test: **6/6 checks passed** using a fresh local SQLite database: `/health`, telemetry ingestion, telemetry history, device status and event-list endpoints returned HTTP 200; the invalid-input case returned the expected HTTP 422.
- Demo seed: **31 synthetic telemetry rows** written; one synthetic anomaly event was generated. The replay reported higher current and apparent power against the synthetic appliance baseline and emitted a cautious diagnosis.
- Official Db2Hack submission folder validator: **not independently executed in this environment**. The official repository could be inspected through its public web page, but a Git clone failed because outbound DNS/network access to `github.com` was unavailable. Run the validator from a fresh clone before opening the PR.

## Validation boundary

The verified test suite on this review pass is **36 passed, 0 failed, 0 skipped**. It also tests deterministic hashing embeddings and the Hugging Face embedding factory wiring with a stub (not an actual model download). The local automated checks include Db2 DB-API adapter tests with a fake driver; they do **not** prove a live IBM Db2 connection. A live Db2 connection, Db2 vector-store operation, remote LLM call, physical ESP32 HTTP test, sensor calibration, and mains-safety validation were **not executed** in this environment. Run `DB_BACKEND=db2 python -m src.verify_db2` after configuring a real Db2 instance in `.env`. Capture genuine screenshots from that environment; no simulated screenshots are provided as evidence. The demo output in `round2_demo_output.json` is explicitly synthetic/SQLite evidence.
