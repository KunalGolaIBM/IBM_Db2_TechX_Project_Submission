# SmartStock AI: AI-Powered Food Waste & Inventory Optimizer

> **One-Line Pitch:** An enterprise-grade food waste reduction and inventory optimization platform powered by **IBM Db2**, Machine Learning (**LightGBM**, **Gradient Boosting**, **Random Forest**), and autonomous **Multi-Agent AI** (CrewAI / LangChain architecture).

---

## Table of Contents
- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [IBM Db2 Integration](#ibm-db2-integration)
- [AI / LLM Architecture](#ai--llm-architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [Testing & Verification](#testing--verification)
- [Screenshots & Demo](#screenshots--demo)
- [Known Limitations & Future Roadmap](#known-limitations--future-roadmap)
- [Team Members & Credits](#team-members--credits)

---

## Problem Statement

- **The Challenge**: The commercial food service industry loses billions annually to avoidable spoilage and waste. Restaurants and cloud kitchens operate on razor-thin margins, frequently discarding ingredients due to lack of batch-level visibility into expiration timelines.
- **Target Audience**: Commercial kitchens, restaurant operators, head chefs, inventory managers, and food service chains.
- **Why Existing Tooling Is Insufficient**: Traditional inventory systems treat stock as static bulk aggregates without granular batch expiration tracking. Standard ERP solutions lack predictive intelligence to proactively foresee spoilage risks, align consumption to recipes utilizing near-expiry ingredients, or coordinate multi-agent AI assistants for automated restocking.

---

## Solution Overview

SmartStock AI transforms commercial kitchen operations through proactive AI and rigorous database-backed inventory governance:

1. **FEFO Inventory Allocation**: Direct transactional and batch-level tracking running on IBM Db2, strictly enforcing *First-Expired, First-Out* consumption to eliminate avoidable spoilage.
2. **AI Spoilage Prediction**: LightGBM classifiers and regressors forecast batch spoilage risk and excess volume prior to expiration dates.
3. **Multi-Horizon Demand Forecasting**: Machine learning models predicting ingredient consumption across 1-day, 3-day, and 7-day windows.
4. **Expiry-Prioritizing Recipe Engine**: Semantic recommendation engine prioritizing dishes (e.g. Creamy Tomato Soup, Palak Paneer, Mushroom Masala) that utilize ingredients approaching imminent expiration.
5. **Intelligent Purchasing Assistant**: Recommends replenishment purchase orders based on forecast shortages, supplier lead times, and Minimum Order Quantities (MOQs) with an explicit manager approval workflow.
6. **Natural Language Assistant (Text-to-SQL & RAG)**: Answers questions in plain English with regex-based read-only SQL execution guards and LLM explanations via local LM Studio (`liquid/lfm2.5-1.2b`) or watsonx.ai.
7. **Autonomous Multi-Agent Crew**: Coordinates 6 specialized agents: *Inventory Agent, Waste Prediction Agent, Demand Forecasting Agent, Recipe Agent, Purchasing Agent, and Reporting Agent*.
8. **What-If Simulation Engine**: Simulates demand surges (e.g. +30% next week) to stress-test supply chains and recalculate stockout risks.
9. **Role-Based Access Control**: Enterprise authentication with security questions and role isolation (*Administrator*, *Head Chef*, *Inventory Manager*, *Kitchen Staff*).

---

## IBM Db2 Integration

- **Db2 Edition & Environment**: IBM Db2 Community Edition running via Docker container (`db2server`).
- **Connector / Drivers Used**: Native `ibm_db` driver interface with Python container execution bridge, with local SQLite mirror synchronization for fast queries and offline resilience.
- **Relational Tables & Schema**:
  - `SUPPLIERS`: Vendor ratings, contact details, lead times, and minimum order quantities.
  - `INGREDIENTS`: Master ingredient catalog, storage temperatures, unit prices, reorder thresholds.
  - `INVENTORY`: Batch-level inventory tracking with `batch_number`, `purchase_date`, `expiry_date`, and `status`.
  - `CONSUMPTION`: Transactional log recording ingredients consumed per dish.
  - `STOCK_MOVEMENTS`: Immutable audit trail for all intake, consumption, waste disposal, and adjustment actions.
  - `RECIPES` & `RECIPE_INGREDIENTS`: Normalized culinary catalog with ingredient requirements.
  - `WASTE_RECORDS`: Spoilage records with quantity lost and monetary impact.
  - `PURCHASE_ORDERS`: Restock purchase orders with status lifecycle (`PENDING_APPROVAL`, `APPROVED`, `DELIVERED`).
  - `USERS`: Enterprise role-based access control with SHA-256 hashed credentials.
- **Key Operations & Queries**:
  - Batch FEFO sorting: `SELECT * FROM INVENTORY WHERE ingredient_id = ? AND quantity > 0 ORDER BY expiry_date ASC`
  - Financial loss rollups: Grouped aggregations across categories and date intervals.
  - Read-only SQL safety guards for Text-to-SQL chat interactions.

---

## AI / LLM Architecture

- **Multi-Agent Framework**: CrewAI / LangChain architecture coordinating 6 domain-specialized agents:
  1. *Inventory Agent*: Evaluates current stock volumes and batch shelf lives.
  2. *Waste Prediction Agent*: Identifies batches at immediate risk of expiration.
  3. *Demand Forecasting Agent*: Projects upcoming ingredient requirements.
  4. *Recipe Agent*: Selects recipes utilizing ingredients nearing expiration.
  5. *Purchasing Agent*: Formulates restock orders factoring supplier lead times and MOQs.
  6. *Reporting Agent*: Compiles comprehensive executive summaries and alerts.
- **LLM Provider & Model**: LM Studio local API (`liquid/lfm2.5-1.2b`) or IBM watsonx.ai Granite models via OpenAI-compatible API endpoint.
- **Machine Learning Inference**:
  - Spoilage Model: Pre-trained LightGBM classifier (`waste_classifier.joblib`) and regressor (`waste_regressor.joblib`).
  - Demand Forecaster: Pre-trained multi-horizon model (`demand_forecaster.joblib`).

---

## Tech Stack

- **Backend**: Python 3.11, FastAPI, Uvicorn, Pydantic
- **Database**: IBM Db2 Community Edition, `ibm_db`, SQLite
- **Machine Learning**: LightGBM, Scikit-Learn, Pandas, NumPy, Joblib
- **AI & Agents**: CrewAI, LangChain, LM Studio / watsonx.ai
- **Frontend**: Streamlit, Plotly, HTML5/CSS3 custom components

---

## Project Structure

```text
submissions/db2-smartstock-ai/
├── README.md               # Complete project overview, setup, and instructions
├── architecture.md        # Detailed system architecture & Db2 data flow
├── submission.json        # Structured project & team metadata
├── .env.example           # Environment template with dummy placeholders
├── requirements.txt       # Production Python dependencies
├── run.py                 # Convenience launcher delegating to src/run.py
│
├── docs/
│   └── screenshots/       # Application UI & dashboard screenshots
│
├── src/                   # Core application source code
│   ├── .streamlit/        # Streamlit theme configuration
│   ├── run.py             # Unified launcher (FastAPI + Streamlit)
│   ├── config.py          # Centralized configuration and path management
│   ├── requirements.txt   # Pinned dependencies
│   │
│   ├── agents/            # Autonomous AI Agents & Text-to-SQL Assistant
│   │   ├── chatbot.py
│   │   └── multi_agent_system.py
│   │
│   ├── backend/           # FastAPI REST API Backend
│   │   ├── main.py        # 25+ REST API routes
│   │   └── services/      # Modular domain services (inventory, waste, demand, etc.)
│   │
│   ├── data/              # Datasets for evaluation and training
│   │   ├── eval.parquet
│   │   └── food_waste_dataset.csv
│   │
│   ├── db/                # IBM Db2 Client & Schemas
│   │   ├── db2_client.py
│   │   ├── schema.py
│   │   └── seed_data.py
│   │
│   ├── frontend/          # Streamlit Multi-Page Web Portal
│   │   ├── app.py
│   │   └── components/
│   │
│   └── ml/                # Pre-trained models and training scripts
│       ├── predictor.py
│       └── models/
│
└── tests/
    └── test_smartstock.py # Comprehensive 10-suite end-to-end integration test
```

---

## Prerequisites

- **Python**: Version 3.10 or 3.11
- **Docker**: For running IBM Db2 Community Edition container (`db2server`)
- **LM Studio** *(Optional for local AI Chatbot)*: Running `liquid/lfm2.5-1.2b` or any OpenAI-compatible API on `http://127.0.0.1:1234/v1`

---

## Setup & Installation

```bash
# 1. Navigate to the project directory
cd submissions/db2-smartstock-ai

# 2. Create and activate a Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install required dependencies
pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` and adjust your IBM Db2 credentials:

```bash
cp .env.example .env
```

Default `.env` configuration:
```ini
# IBM Db2 Enterprise Configuration
DB2_CONTAINER=db2server
DB2_DATABASE=testdb
DB2_USER=db2inst1
DB2_PASSWORD=your_db2_password_here
DB2_HOST=localhost
DB2_PORT=50000

# Local LM Studio LLM Endpoint
LMSTUDIO_URL=http://127.0.0.1:1234/v1
LLM_MODEL=liquid/lfm2.5-1.2b
```

> **Security Warning:** Never commit `.env` or real database credentials to Git!

---

## Running the Project

### 1. Initialize Database Schema & Seed Data
```bash
python -m src.db.schema
python -m src.db.seed_data
```
*(Or from within `src/`: `cd src && python -m db.schema && python -m db.seed_data`)*

### 2. Launch the Application
Run the unified launcher to start both the FastAPI backend and Streamlit dashboard concurrently:

```bash
python run.py
```
*(Or: `cd src && python run.py`)*

- **Streamlit Web Portal**: [http://localhost:8501](http://localhost:8501)
- **FastAPI Interactive Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Testing & Verification

Execute the comprehensive 10-suite integration test verifying Db2 connectivity, FEFO logic, ML predictors, multi-agent crew, and chatbot:

```bash
# Direct test execution
python tests/test_smartstock.py

# Or via pytest
pytest tests/test_smartstock.py -v
```

### Validation of Submission Structure
To verify that this submission adheres to all summit requirements:
```bash
# From the repository root
python scripts/validate_submission.py submissions/db2-smartstock-ai
```

---

## Screenshots & Demo

- **FEFO Batch Inventory Tracking**: Real-time batch expiration visualizer ensuring earliest-expiring ingredients are consumed first.
- **AI Food Spoilage Risk Heatmap**: Pre-calculated risk tiers flagging at-risk batches before monetary loss occurs.
- **Autonomous Multi-Agent Crew Dashboard**: Automated coordination between 6 specialized agents synthesizing replenishment orders and executive action items.
- **Natural Language Assistant**: Conversational Text-to-SQL interface allowing chefs and managers to query inventory in plain English.

---

## Known Limitations & Future Roadmap

- **watsonx.data Lakehouse Federation**: Expand relational Db2 storage to watsonx.data Presto engine for federated multi-cloud analytics.
- **IoT Smart Scale Integration**: Connect IoT weighing scales and smart refrigeration sensors for real-time automatic consumption logging.
- **Mobile POS Barcode Scanner**: Progressive Web App (PWA) barcode/QR scanner for rapid kitchen intake and waste logging.

---

## Team Members & Credits

- **Ashfin Prem** — Developer
- **IBM Db2 TechX Summit 2026** — GL Bajaj Group of Institutions, Mathura in association with IBM, IIC, and NexaSphere.
