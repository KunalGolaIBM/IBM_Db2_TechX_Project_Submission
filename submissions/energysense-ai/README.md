# EnergySense AI

> **One-line pitch:** EnergySense AI turns appliance sensor readings into an appliance-specific operating baseline, explainable anomaly alerts and traceable maintenance guidance, with IBM Db2 as the history store and a LangChain tool-calling assistant for natural-language investigation.

---

## Problem statement

Appliance monitoring projects often display instantaneous values or apply fixed thresholds, but they do not explain how a device is behaving compared with its own historical operating pattern. Gradual changes in motor current, temperature, vibration or runtime can therefore be missed or be difficult to investigate. The intended users are students, facility teams and maintenance technicians monitoring small motors, pumps and similar electrical loads.

EnergySense AI extends the user's ESP32/Wokwi appliance-runtime prototype with database-backed history and explainable anomaly investigation. It does not replace electrical protection or a qualified technician.

## Solution overview

1. **Telemetry ingestion:** A FastAPI endpoint accepts RMS voltage/current, apparent power, runtime, temperature, vibration, relay-state metadata and source provenance.
2. **Appliance-specific baseline:** Historical readings for the selected appliance are used to calculate per-feature mean, spread and z-score.
3. **Two-layer anomaly analysis:** Feature-level z-scores explain high- or low-side deviations. Isolation Forest checks a multivariate feature window when at least 20 complete historical samples are available.
4. **Traceable advisory:** The deterministic workflow produces a cautious diagnostic hypothesis, a recommended inspection and a workflow trace. An anomaly event is saved for audit and dashboard review.
5. **Db2 knowledge retrieval:** The optional `langchain-db2` `DB2VS` integration stores/retrieves maintenance notes in Db2 vector search.
6. **LangChain assistant:** An optional read-only tool-calling agent can retrieve recent readings, analyse the latest appliance window, search Db2 maintenance notes and read previous events.
7. **Dashboard:** Streamlit shows data-source provenance, voltage/current/temperature trends, reported runtime and explainable anomaly history.

The core telemetry and anomaly workflow runs without an LLM API key. The natural-language tool-calling agent is optional and requires `OPENAI_API_KEY` in the local `.env` file.

## IBM Db2 integration

**Primary target:** IBM Db2 for LUW. Record the exact server edition and version used for your live demo in your final submission notes.

**Relational connector:** `ibm-db` / `ibm_db_dbi` connects to Db2. The application creates and uses:

| Table | Purpose |
|---|---|
| `ESAI_EQUIPMENT` | Equipment and appliance names |
| `ESAI_TELEMETRY` | Time-stamped telemetry and source provenance |
| `ESAI_EVENTS` | Severity, anomaly score, baseline values, explanation and recommended action |

Indexed history queries are ordered by appliance ID and record time. Values are passed through bound parameters. The application creates the relational tables and indexes at startup when they are missing.

**Vector connector:** `langchain-db2` exposes the `DB2VS` LangChain vector store. `ESAI_KNOWLEDGE` stores maintenance guidance for similarity retrieval. IBM's current connector reference requires a Db2 instance with vector-search support (Db2 12.1.2+). The live-demo configuration uses `langchain-huggingface` with `sentence-transformers/all-MiniLM-L6-v2` for semantic embeddings. A deterministic 384-dimensional HashingVectorizer is also retained as a lightweight offline/test backend (`DB2_EMBEDDING_PROVIDER=hash`). Keep the embedding model consistent when seeding and querying a vector table; rebuild the knowledge table if you change models.

The SQLite adapter is for automated tests and offline smoke testing only. It is not evidence of IBM Db2 integration. The device-status endpoint reports the most recently stored record; it does not infer that a device is currently online. The actual Db2 demonstration must be run against your own configured instance.

## AI / LangChain architecture

- **Always-available analytics:** Python baseline calculations and scikit-learn Isolation Forest produce deterministic, explainable anomaly results. The stages are monitoring, detection, diagnosis, recommendation and event supervision; they are not presented as five independent LLM agents.
- **Optional Agentic AI:** LangChain `create_agent` coordinates read-only tools for latest readings, appliance analysis, Db2 maintenance-note retrieval and saved events. The model is configurable through `OPENAI_MODEL`.
- **Grounding and safety:** The assistant is instructed to use the tools, distinguish measured values from hypotheses, and never send relay commands. Relay control remains inside the local ESP32 firmware.

## Tech stack

- Python 3.10+
- FastAPI + Pydantic
- IBM Db2 for LUW, `ibm-db` / `ibm_db_dbi`
- LangChain + `langchain-db2` `DB2VS` + `langchain-huggingface` sentence-transformer embeddings + optional `langchain-openai`
- scikit-learn Isolation Forest and HashingVectorizer
- Streamlit + Requests
- ESP32 / Wokwi project as the telemetry source prototype

## Prerequisites

- Python 3.10 or newer (the author's local runs used Python 3.13.5; no CI workflow is included).
- IBM Db2 for LUW connection for the required live Db2 demonstration.
- Db2 12.1.2+ with vector-search support for the optional `DB2VS` maintenance knowledge store.
- VS Code with the IBM Db2 Developer Extension if using the event's local Db2 workflow.
- An OpenAI API key only if using the optional natural-language assistant.

## Setup and installation

```bash
cd submissions/energysense-ai
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` locally. Never commit `.env` or real credentials.

## Run locally with SQLite (automated/offline smoke-test mode)

Keep `DB_BACKEND=sqlite` in `.env` for the offline demo:

```bash
python -m src.seed_demo
uvicorn src.api:app --reload
```

In a second terminal:

```bash
streamlit run src/dashboard.py
```

Open `http://127.0.0.1:8000/docs` for the API and `http://localhost:8501` for the dashboard.

### Sample telemetry request

```bash
curl -X POST http://127.0.0.1:8000/api/v1/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "equipment_id": "ES-01",
    "appliance_id": "pump-01",
    "appliance_name": "Pump 01",
    "vrms_v": 230.0,
    "irms_a": 1.6,
    "apparent_power_va": 368.0,
    "runtime_s": 3600,
    "temperature_c": 41.0,
    "vibration_rms": 0.20,
    "relay_state": "ON",
    "source": "synthetic"
  }'
```

Supported source labels are `synthetic`, `wokwi_simulated` and `esp32`. Use the source label honestly so simulation and physical readings are never mixed up.

## Run against IBM Db2 for the hackathon demo

1. Start or connect to your IBM Db2 for LUW instance and confirm its database, host, port and user.
2. Set `DB_BACKEND=db2` and the actual `DB2_HOST`, `DB2_PORT`, `DB2_DATABASE`, `DB2_USERNAME` and `DB2_PASSWORD` in `.env`.
3. Restart the API process so the cached storage adapter reads the new settings.
4. Run a real relational Db2 write/read smoke test:

   ```bash
   python -m src.verify_db2
   ```

   This deliberately inserts one synthetic telemetry row and one INFO event into your Db2 database, then reads both back. The output identifies the test appliance ID; remove those two test rows after the verification if desired.

5. Load the maintenance knowledge collection (requires Db2 vector-search support):

   ```bash
   python -m src.seed_knowledge
   ```

6. Start FastAPI and Streamlit again. Post a new reading with `source: "wokwi_simulated"` or `source: "esp32"`, then verify the new rows in Db2 using the VS Code SQL editor.
7. Capture real screenshots of the connected Db2 instance, the three relational tables, a successful API response, the dashboard and the vector retrieval result. Do not use mock or generated screenshots as proof of a live Db2 connection.

### Optional LangChain assistant

Set `OPENAI_API_KEY` and `OPENAI_MODEL` in `.env` after the relational Db2 path and vector store are ready. Ask a question through the Streamlit dashboard or:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/assistant \
  -H "Content-Type: application/json" \
  -d '{"question":"Why is pump-01 drawing more current than its baseline?"}'
```

The LangChain tools are read-only. The optional assistant is not required for local API tests and cannot control the relay.

## ESP32 telemetry bridge

`examples/esp32_http_sender.ino` contains a small HTTP sender that can be adapted to the user's firmware. It accepts already-calculated RMS values from the existing sensor routines; it does **not** invent calibration constants or replace ZMPT101B/ACS712 calibration. The example is not claimed as a tested physical-hardware integration. Use it only on a trusted local network and preserve the existing local relay cutoff path if Wi-Fi or the API fails.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Backend and telemetry/event counts |
| `POST` | `/api/v1/telemetry` | Validate, store and analyse a reading |
| `GET` | `/api/v1/devices/{appliance_id}/status` | Return latest recorded readings and reported relay/source metadata (does not infer online connectivity) |
| `GET` | `/api/v1/telemetry/{appliance_id}` | Read time-ordered history |
| `GET` | `/api/v1/events?appliance_id=pump-01` | Read persisted anomaly events |
| `POST` | `/api/v1/assistant` | Optional LangChain tool-calling assistant |

## Testing and verification

Install the lightweight test dependencies and run tests without a Db2 server:

```bash
pip install -r requirements-test.txt
python -m compileall -q src tests
pytest -q
```

The suite covers anomaly scoring in both directions, incomplete/non-finite history, SQLite CRUD and ordering, API validation and ingestion, device-status reporting, workflow event persistence, the Isolation-Forest-only event path, Db2 adapter SQL parameter binding via a fake DB-API driver, configuration validation, LangChain agent tool registration using test stubs, and deterministic n-gram embedding behaviour. The verified local run completed with 36 passed and no skipped tests; live Db2 and remote-model verification remain separate steps.

These tests do not replace a live Db2 connection test. Run `python -m src.verify_db2` with `DB_BACKEND=db2` on your own machine and retain the genuine output/screenshots for the hackathon demonstration.

## Screenshots and demo

Place genuine evidence under `docs/screenshots/`. The folder currently contains instructions only; no live Db2 or physical-hardware screenshots are included. `docs/architecture.png` and `docs/data_flow.png` are architecture/data-flow diagrams, not application screenshots or proof of a live integration. Suggested captures: Db2 extension connection, `ESAI_EQUIPMENT` / `ESAI_TELEMETRY` / `ESAI_EVENTS`, the Db2 vector knowledge table/search, API response, dashboard alert and optional assistant response.

## Known limitations and future roadmap

- This prepared package has not been connected to the participant's Db2 instance in this environment. The live Db2 test is provided but still needs to be run with participant credentials.
- The original Wokwi design uses potentiometers to emulate sensor inputs. Physical ZMPT101B/ACS712 calibration, ADC conditioning and relay testing have not been performed here.
- The new ESP32 HTTP sender example needs adapting to the existing firmware variable names and testing on the user's local network.
- The lightweight hash embedding backend is lexical. The configured live-demo option uses a local sentence-transformer model; first use downloads the model and requires sufficient disk space and memory.
- The optional LangChain assistant requires an API key and working Db2 vector retrieval; no external model call was executed during the local test run.
- The project records apparent power in VA. It does not report billing-grade real power or kWh because power factor and calibrated real-power measurement are not in scope.
- The AI layer is advisory. Do not perform exposed-mains testing. Physical evaluation requires qualified supervision, verified isolation, appropriate fusing/enclosures and properly rated components.

## Team members and credits

**Individual participant:** Manuneethi Cholan D  
**Institution:** University College of Engineering, Arni  
**Department:** Electronics and Communication Engineering  

IBM Db2, LangChain, FastAPI, Streamlit and scikit-learn are credited as the technologies used. The participant's GitHub handle (`ModMonish`) is listed in `submission.json`; no email address or other contact details are included.

## Official hackathon resources

- [Db2Hack submission guide](https://ibmdb2techxsummit.glbajajgroup.ac.in/submit)
- [Official submission repository](https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission)
- [IBM Db2 Python connection documentation](https://www.ibm.com/docs/en/db2/12.1.x?topic=db-connecting-database-server)
- [LangChain Db2 `DB2VS` reference](https://reference.langchain.com/python/langchain-db2/db2vs/DB2VS)
