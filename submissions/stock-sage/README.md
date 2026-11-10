# StockSage — Agentic AI Inventory Intelligence Assistant for Small Grocery and Dairy Retailers

> **One-Line Pitch:** An Agentic AI inventory co-pilot powered by IBM Db2 and LangGraph that helps small grocery and dairy retailers eliminate stockouts, prevent perishable expiry losses, and automate smart reordering.

---

## Table of Contents
- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [IBM Db2 Integration](#ibm-db2-integration)
- [AI / LLM Architecture](#ai--llm-architecture)
- [Tech Stack](#tech-stack)
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
Small grocery and dairy retailers (kirana stores) operate on razor-thin margins and manage hundreds of fast-moving products with diverse shelf-lives:
- **Perishable Risk:** Fresh milk, paneer, curd, and bakery items spoil within 2 to 5 days, resulting in direct revenue write-offs.
- **Stockout Losses:** High-turnover essentials (milk, bread, staples) frequently run out without advance notice, leading to lost sales and disappointed neighbourhood customers.
- **Manual Guesswork:** Shop owners lack enterprise ERP systems and rely on manual memory or messy paper notebooks to estimate reorders and expiry dates.

StockSage delivers an automated, enterprise-grade inventory intelligence solution accessible through a simple web dashboard and natural language conversational AI.

---

## Solution Overview
StockSage combines the robust relational power of **IBM Db2** with a deterministic **LangGraph** agent workflow and **Google Gemini LLM**:
1. **Low Stock & Stockout Alerts:** Real-time monitoring of inventory levels against reorder thresholds.
2. **Short-Term Stockout Forecasting:** Uses 7-day sales velocity to forecast exactly how many days of inventory remain and flags items at critical risk ($\le 3$ days).
3. **Batch-Level Expiry Intelligence:** Granular tracking of inventory batches with countdown timers to proactively discount or front-face near-expiry dairy and bakery goods.
4. **Smart Reorder Planner:** Computes safety-stock-aware purchase quantities based on lead times and average daily demand.
5. **Conversational Assistant:** Allows shopkeepers to ask natural questions like *"Which products are running low?"*, *"What should I reorder today?"*, or *"Which batches expire this week?"*.

---

## IBM Db2 Integration
- **Db2 Edition & Environment:** IBM Db2 Community Edition (running via Docker on port `50000`).
- **Connector / Driver Used:** Official native Python connector **`ibm_db`**.
- **Database Schema & Design:**
  - `PRODUCTS`: Master product catalog, pricing, category, and reorder levels.
  - `SUPPLIERS`: Vendor registry, contact details, and fulfillment lead times (days).
  - `INVENTORY_BATCHES`: Batch-level stock records with received dates and expiry dates.
  - `SALES`: Transactional records linking sold quantities, sale dates, and revenue.
- **Indexing & Performance:** B-tree indexes on `INVENTORY_BATCHES(expiry_date)` and `SALES(sale_date)` for instant countdown and velocity calculations.
- **Security & Integrity:** Parameterized query execution protecting against SQL injection, foreign key constraints, and zero hardcoded credentials.

---

## AI / LLM Architecture
- **Framework:** **LangGraph** (StateGraph architecture).
- **Model Provider & Model:** **Google Gemini 3.5 Flash Lite** via `langchain-google-genai`.
- **Deterministic Decoupling:**
  - The LLM **never** performs arithmetic or invents stock quantities.
  - User questions are classified into specialized intents (`low_stock`, `stockout_risk`, `expiry_risk`, `fast_slow_moving`, `reorder_advice`, `overview`).
  - Python and IBM Db2 execute verified deterministic formulas.
  - Gemini receives verified data in prompt context and formats a conversational, shopkeeper-friendly explanation.
  - Operates reliably even offline through built-in deterministic fallback templates.

---

## Tech Stack
- **Backend & Core:** Python 3.10+
- **Database:** IBM Db2 Community Edition (Docker) / `ibm_db`
- **Agent Orchestration:** LangGraph & LangChain Core
- **LLM:** Google Gemini 3.5 Flash Lite
- **Frontend / UI:** Streamlit & Plotly
- **Data Engineering:** Pandas & NumPy
- **Testing:** PyTest

---

## Prerequisites
- **Python 3.10+** (Tested on Python 3.13 and 3.14)
- **Docker Desktop** (or access to an IBM Db2 database instance)
- **Git**

---

## Setup & Installation

```bash
# 1. Clone repository and navigate to the project directory
cd submissions/stock-sage

# 2. Start the IBM Db2 Docker Container
docker run -d --name db2server \
  --restart always \
  -p 50000:50000 \
  -e LICENSE=accept \
  -e DB2INST1_PASSWORD=Password123! \
  -e DBNAME=testdb \
  -v db2_data:/database \
  icr.io/db2_community/db2:latest

# 3. Install Python dependencies
pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```ini
DB2_HOST=localhost
DB2_PORT=50000
DB2_DATABASE=testdb
DB2_USER=db2inst1
DB2_PASSWORD=Password123!
DB2_SECURITY=false

# Optional: Add your Gemini API Key for natural language explanations
GEMINI_API_KEY=your_gemini_api_key_here
```

---

## Running the Project

```bash
# 1. Initialize schema and seed grocery/dairy sample data
python src/database_setup.py

# 2. Launch the Streamlit application
streamlit run src/app.py
```

Open your browser at `http://localhost:8501`.

---

## Testing & Verification

Run the full automated test suite (11 comprehensive unit & integration tests):

```bash
python -m pytest tests -v
```

Validate repository hackathon compliance:

```bash
python ../../scripts/validate_submission.py submissions/stock-sage
```

---

## Screenshots & Demo
- **Demo Walkthrough Video:** *(To be added)*
- Screenshots stored in `docs/screenshots/`:
  - *Main Dashboard & Inventory Health KPIs*
  - *Conversational AI Assistant*
  - *Perishable Batch Expiry Countdown Chart*
  - *Smart Reorder Recommendations Plan*

---

## Known Limitations & Future Roadmap
- **Current Limitations:** Batch expiry dates assume standard room/refrigerated storage without temperature sensor telemetry.
- **Future Roadmap:**
  - Automated WhatsApp/SMS supplier purchase order dispatch.
  - Barcode and QR code scanner integration for fast stock receiving.
  - Multi-location warehouse support with inter-store transfers.

---

## Team Members & Credits
| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| **Mahima Sahu** | [@mahima04sahu-lgtm](https://github.com/mahima04sahu-lgtm) | Full Stack Development, IBM Db2 Integration & LangGraph Agent |
