# Db2Ops AI — Intelligent Database Copilot

> **One-Line Pitch:** Ask business questions in natural language, review safe Db2 SQL, and explore the records and insights returned by IBM Db2.

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

## Problem Statement

Business users often need a developer or analyst to turn routine questions into database queries. This slows decisions and makes data access harder for teams that do not write SQL. Unrestricted natural-language-to-SQL systems create another problem: generated statements can be incorrect, expensive, or unsafe.

Db2Ops AI is for business analysts, operators, and developers who need accessible answers while retaining a clear SQL review and read-only boundary.

## Solution Overview

The Streamlit application accepts a natural-language question, retrieves live column metadata for the five allow-listed application tables, and uses LangChain with a configurable OpenAI chat model to propose Db2 SQL. SQLGlot parses the generated statement using IBM's Db2 dialect plugin. Only one SELECT over the five application tables can pass. The query runs through `ibm_db`; the app caps returned rows, displays a Pandas table and CSV download, and asks LangChain to explain only the retrieved rows.

The dashboard shows live Db2 metrics and recent orders. Data Explorer previews application tables; Analytics provides Plotly views of revenue, orders, products, customers, cities, categories, and payments with a date-range filter. Session-only Query History records SQL, status, timestamp, and duration. When Db2 is unavailable, the app clearly reports disconnection and does not display fabricated metrics.

## IBM Db2 Integration

- **Edition & environment:** IBM Db2 Community Edition. A local native instance or the IBM Db2 Developer Extension's Community Edition workflow can be used.
- **Connector:** IBM's `ibm_db` Python driver.
- **Database:** `DB2OPS`; defaults are configurable through `.env`.
- **Tables:** `CUSTOMERS`, `PRODUCTS`, `ORDERS`, `ORDER_ITEMS`, and `PAYMENTS` with primary keys, foreign keys, checks, unique email, and supporting indexes.
- **Data:** the initializer inserts 24 Indian customers, 15 products, 60 orders, 120 order items, and 60 related payments. It uses key-based Db2 `MERGE` statements, so rerunning setup does not duplicate those seed IDs.
- **Verification:** `scripts/test_connection.py` runs `SELECT 1 AS CONNECTED FROM SYSIBM.SYSDUMMY1` against the configured Db2 server.

## AI / LLM Architecture

- **Framework:** LangChain prompt templates and runnable chains (`langchain-core`, `langchain-openai`).
- **Provider/model:** OpenAI, configurable with `OPENAI_MODEL` (default `gpt-4o-mini`).
- **Workflow:** schema context + question → SQL-generation chain → SQLGlot Db2 parsing and policy checks → bounded `ibm_db` execution → result table → result-grounded LangChain explanation.
- **Secrets:** the API key and database password are loaded from environment variables. They are not included in the prompts or application logs.
- **`langchain-db2`:** its maintained package exposes a Db2 vector store integration. This application uses relational SQL and does not perform embedding or vector retrieval, so adding that package would not contribute to this workflow.

## Tech Stack

- **Core:** Python 3.10+. IBM's Db2 SQLGlot dialect plugin is tested on Python 3.10–3.12; Python 3.12 is the recommended interpreter for the project.
- **Database:** IBM Db2 Community Edition and `ibm_db`
- **UI:** Streamlit, custom CSS, Plotly
- **AI:** LangChain, langchain-core, langchain-openai, OpenAI API
- **Safety/data:** SQLGlot, Pydantic Settings, Pandas, python-dotenv
- **Tests:** pytest

## Prerequisites

- Python 3.11 or newer and `pip`
- IBM Db2 Community Edition reachable from this machine; the container route needs WSL 2, Docker Desktop/engine, virtualization, and sufficient disk/RAM
- OpenAI API key for AI SQL and AI summaries; dashboard, explorer, and analytics use Db2 without the key

## Setup & Installation

1. Install IBM Db2 Community Edition. This Windows machine has the IBM Db2 Developer Extension but did not have Docker or a Db2 service at project setup. To use the automated extension flow, open VS Code in a configured WSL 2 Ubuntu workspace, enable Docker Desktop's WSL integration, open the **Db2 Connections** panel, select **Create Db2 instance**, and enter database `DB2OPS`, user `db2inst1`, and a strong local password. The extension's Windows workflow prerequisites include WSL 2, a supported Linux distribution, Docker Desktop integration, virtualization, and administrator access. Review IBM's current [instance creation instructions](https://ibm.github.io/db2developerextension-about/docs/the-basics/creating-db2-instance.html) before starting.
2. From the cloned repository root, create a virtual environment outside the submission folder (the official validator scans every file under the submission, including ignored virtual environments) and install project packages:

   ```powershell
   py -3.14 -m venv .venv-db2ops-ai
   .\.venv-db2ops-ai\Scripts\Activate.ps1
   cd submissions/db2ops-ai
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

   Python 3.12 is recommended; use another installed Python 3.10+ interpreter by changing the launcher version.
3. Copy the safe example settings and edit local values:

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

4. Initialize tables and seed records, then verify the real server:

   ```powershell
   python scripts/setup_db.py
   python scripts/test_connection.py
   ```

The app does not bundle an embedded database and does not switch to a different database if Db2 is unavailable.

## Configuration

Set the keys in `.env` (never commit that file):

| Variable | Purpose | Default |
|---|---|---|
| `DB2_DATABASE` | Db2 database name | `DB2OPS` |
| `DB2_HOSTNAME` | Db2 server host | `localhost` |
| `DB2_PORT` | TCP port | `50000` |
| `DB2_PROTOCOL` | IBM driver protocol | `TCPIP` |
| `DB2_UID` | Db2 user | `db2inst1` |
| `DB2_PWD` | Db2 password | blank |
| `DB2_SCHEMA` | Application schema | `DB2INST1` |
| `DB2_MAX_ROWS` | Maximum fetched rows | `500` |
| `OPENAI_API_KEY` | OpenAI key for LangChain | blank |
| `OPENAI_MODEL` | OpenAI chat model | `gpt-4o-mini` |

For normal interactive use, grant the application user SELECT only on the five application tables. Run schema setup separately using an authorized setup account if that user cannot create tables. The SQL validator is a second application-layer guard, not a replacement for Db2 grants. The current driver integration caps fetched rows but does not claim a server-enforced query timeout.

## Running the Project

From `submissions/db2ops-ai` with the virtual environment active:

```powershell
streamlit run src/app.py
```

Open the local URL Streamlit prints. To test connection details from the UI, choose **Database Connection** and select **Test Db2 connection**.

## Testing & Verification

```powershell
   python -m compileall -q src scripts tests
   $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
   pytest -q
python scripts/test_connection.py
python -m streamlit run src/app.py --server.headless true
```

The connection check needs a running Db2 instance. Unit tests mock database and LLM failures; they do not substitute SQLite or claim live Db2 integration.

## Screenshots & Demo

No Db2 screenshot is included until the application has been run against the local database. This prevents a disconnected UI or mock data from being presented as a live Db2 result. Save genuine captures under `docs/screenshots/` after completing setup.

The six-slide round-one proposal is available at [`docs/proposal/Db2Ops_AI_Round_1_Proposal_v2.pptx`](docs/proposal/Db2Ops_AI_Round_1_Proposal_v2.pptx). It marks local Db2 setup and live verification as pending.

## Known Limitations & Future Roadmap

- Db2 is not installed or running on the development machine at handoff, so live data initialization, database integration, and connected screenshots remain pending.
- Windows Application Control blocked the downloaded native `ibm_db` and Pandas extension modules in the local virtual environment. The packaged Streamlit disconnect state runs, but live Db2 and DataFrame paths need an environment where these signed native modules are allowed by device policy.
- An OpenAI API key is needed to run LangChain generation and explanations.
- The interactive SQL user should have SELECT-only grants; the app additionally parses statements and restricts table access.
- `langchain-db2` vector search is not used because this project has no embedding or semantic retrieval requirement.
- Query history is session-only. The IBM driver path enforces a maximum fetched row count but currently has no server-side query timeout.
- Next steps: create a least-privilege Db2 role, add server-side execution controls where supported, add date filters and structured output, and capture a verified connected demo.

## Team Members & Credits

Individual participant: **Gireesh Patgar** (name from the local Git configuration). GitHub handle and public contact details were not available in the workspace and are not guessed. The project owner should add verified profile details before publication.
