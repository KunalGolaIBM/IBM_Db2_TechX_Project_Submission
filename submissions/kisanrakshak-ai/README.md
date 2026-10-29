# KisanRakshak AI

> One-line pitch: KisanRakshak AI helps farmers receive crop health, irrigation, and market recommendations using IBM Db2-backed analytics and AI-generated insights.

---

## Problem Statement

Indian farmers often face a combination of uncertainty and information gaps:
- crop disease outbreaks are detected late,
- irrigation and soil recommendations are inconsistent,
- weather risk is not translated into local, practical guidance,
- smallholders rarely get actionable, data-driven help in time.

This problem is especially acute in rural regions where access to agronomy experts and real-time information is limited. Traditional advisory methods are manual, fragmented, and often unavailable during critical crop stages.

---

## Solution Overview

KisanRakshak AI offers a multilingual, farmer-focused advisory dashboard that:
- stores field, weather, crop, and soil data in IBM Db2,
- analyzes trends and risk patterns using SQL and Python,
- generates AI-assisted recommendations using an LLM-friendly decision workflow,
- suggests disease alerts, irrigation timing, and crop planning actions.

The platform combines transactional data with lightweight AI prompts to provide practical guidance in a structured output format suitable for agronomy support.

---

## IBM Db2 Integration

- Data is stored in IBM Db2 Community Edition to model farms, crops, soil observations, weather signals, and advisory logs.
- Python connects to IBM Db2 using `ibm_db` and prepared SQL statements.
- Core tables include farmers, fields, crop_health_logs, weather_alerts, and recommendations.
- Sample operations include seasonal trend queries, risk scoring, and recommendation retrieval based on field conditions.

Example schema:

```sql
CREATE TABLE farmers (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    village VARCHAR(150),
    phone VARCHAR(20),
    language_pref VARCHAR(50) DEFAULT 'Hindi'
);

CREATE TABLE fields (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    farmer_id INTEGER NOT NULL,
    crop VARCHAR(100) NOT NULL,
    soil_type VARCHAR(100),
    acreage DECIMAL(10,2),
    district VARCHAR(100),
    irrigation_status VARCHAR(50),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE crop_health_logs (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    field_id INTEGER NOT NULL,
    disease_risk_score INTEGER,
    moisture_level DECIMAL(5,2),
    temperature DECIMAL(5,2),
    observed_issue VARCHAR(250),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE recommendations (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    field_id INTEGER NOT NULL,
    category VARCHAR(50) NOT NULL,
    recommendation_text CLOB NOT NULL,
    confidence_score DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## AI / LLM Architecture

- Framework: Python with LangChain-compatible orchestration.
- Model provider: OpenAI GPT-4o mini or a local fallback model for offline demonstration.
- Workflow: field records from Db2 are queried, summarized, and supplied as context to a prompt that recommends agronomic interventions.
- Example use case: given moisture, crop type, and disease risk, the AI recommends whether to irrigate, apply nutrient support, or flag disease risk for inspection.

---

## Tech Stack

- Backend: Python 3.11
- Database: IBM Db2
- AI Layer: LangChain-style prompt orchestration
- Frontend: Streamlit-based dashboard or CLI demo
- Libraries: `ibm_db`, `python-dotenv`, `pydantic`

---

## Prerequisites

- IBM Db2 Community Edition running locally or on a cloud instance
- Python 3.10+
- `pip`
- Optional: OpenAI API key for LLM-powered recommendations

---

## Setup & Installation

```bash
cd submissions/kisanrakshak-ai
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` and fill the credentials.

```bash
cp .env.example .env
```

> Security note: never commit real Db2 passwords or API keys.

---

## Running the Project

```bash
python src/main.py
```

Sample CLI flow:
- show active recommendations,
- insert a field observation,
- retrieve advisories for the field,
- print AI-generated guidance.

---

## Testing & Verification

```bash
python -m compileall src
python src/main.py
```

A successful run should:
- connect to IBM Db2 using environment variables,
- read sample field data,
- generate a recommendation summary,
- indicate whether the advisory model ran or fell back safely.

---

## Screenshots & Demo

- Demo output can be displayed in a terminal or dashboard.
- Sample screenshots can be placed under `docs/screenshots/`.

---

## Known Limitations & Future Roadmap

- Current version focuses on a proof-of-concept advisory flow.
- Future enhancements include multilingual support, weather API integration, and real disease-image detection.
- The system can later expand to marketplace pricing, fertilizer suggestions, and farmer alert automation.

---

## Team Members & Credits

| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Anas Khan | [@anaskhan688700-create](https://github.com/anaskhan688700-create) | Project lead, architecture, Db2 + AI logic |

