# Box Office Inc - AI-Powered Movie Studio Simulator

> One-line pitch: Box Office Inc is a movie studio management simulation that blends gameplay, analytics, and AI-driven recommendations to help a studio optimize talent, production, and marketing decisions.

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
Running a film studio is a continuous balancing act between creative ambition, financial discipline, audience demand, and marketing efficiency. Many aspiring producers and strategy-game players do not have a structured, interactive environment to model these decisions in real time.

This project solves that by simulating a movie studio as a strategy and management game. Players can decide which talent to hire, which scripts to produce, how much to spend on marketing, and when to release a film. The system then provides scenario-based analytics and AI guidance to improve future decisions.

---

## Solution Overview
Box Office Inc provides a full-stack management simulation for building and operating a movie studio. The experience includes:

- studio creation and financial tracking
- talent hiring and creative staffing
- script acquisition and production pipeline management
- marketing campaign planning and release decisions
- weekly simulation of revenue, fanbase, and reputation changes
- AI-assisted insights for better decision-making

The app is built as a hybrid architecture:
- MongoDB handles operational game-state data
- IBM Db2 provides the analytics and intelligence layer for structured reporting and recommendation storage
- AI workflows use LangChain/CrewAI-style orchestration patterns to recommend strategy improvements

---

## IBM Db2 Integration
- **Db2 Edition & Environment:** IBM Db2 analytics layer with `ibm_db` connectivity pattern for reports and recommendation storage
- **Connector / Driver Used:** `ibm_db`
- **Database Schema / Data Models:** Studio performance tables, recommendation logs, and market insight snapshots; key fields include studio name, revenue, expenses, reputation, fanbase, active movies, marketing budget, market trend, and recommendation text
- **Key Queries & Operations:** Query connection validation, create historical insight tables, insert recommendation records, and read reporting metrics for strategic analysis

The implementation is designed to support a realistic IBM Db2 usage pattern without forcing the live gameplay state into the transactional database. This keeps the app game-friendly while giving the hackathon a real, meaningful Db2 analytics layer.

---

## AI / LLM Architecture
- **Framework:** LangChain + CrewAI-inspired orchestration patterns
- **Model Provider & Model:** OpenAI-compatible LLM via environment configuration, or local fallback heuristics when no model is configured
- **RAG / Tool Calling Workflow:** Studio metrics are passed into an AI strategy engine, which evaluates revenue, fanbase, reputation, and trend signals to produce recommendations such as scaling a high-performing release or increasing marketing spend for underserved audiences

This is implemented in the project source under `src/strategy_engine.py` and `src/db2_client.py`.

---

## Tech Stack
- **Backend / Core:** Python 3.12+
- **Database:** IBM Db2 + MongoDB
- **Frontend / UI:** React + Vite + Redux Toolkit (existing game client)
- **Libraries & Tools:** `ibm_db`, `python-dotenv`, LangChain, CrewAI, Haystack-compatible patterns

---

## Prerequisites
- Python 3.10+
- pip
- Access to a local or cloud IBM Db2 instance, or a configured DSN
- Optional: OpenAI API key for LLM-based recommendations

---

## Setup & Installation

```bash
cd submissions/box-office-inc
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your local values:

```bash
cp .env.example .env
```

Example environment fields include:
- `DB2_HOST`
- `DB2_PORT`
- `DB2_DATABASE`
- `DB2_USER`
- `DB2_PASSWORD`
- `DB2_DSN`
- `OPENAI_API_KEY`

> Security Warning: Never commit real .env credentials or secret values to GitHub.

---

## Running the Project

From the project directory:

```bash
python src/main.py
```

This produces a studio strategy analysis using:
- a local deterministic fallback strategy when no model or Db2 is configured
- optional IBM Db2 connection checks
- optional AI recommendation generation when a provider is configured

---

## Testing & Verification

Run the included verification flow:

```bash
python src/main.py
python src/verify_setup.py
```

The scripts print a JSON result including:
- studio metrics
- Db2 connection status
- environment readiness
- dependency availability
- fallback or live recommendation output
- insert status for a Db2 insight table when a live connection exists

### Validation status in this repo
This repository currently validates successfully in fallback/demo mode when no real IBM Db2 server is configured. A fully live IBM Db2 round-trip requires the user to provide valid `DB2_*` environment variables and a reachable Db2 hostname or DSN.

---

## Screenshots & Demo
- **Live Demo Link:** Add your hosted demo link here
- **Demo Video Link:** Add your video URL here
- Screenshots can be placed under `docs/screenshots/` and referenced here when available

---

## Known Limitations & Future Roadmap
- **Current Limitations:** Live Db2 connectivity depends on credentials and environment configuration; the system gracefully falls back to a local recommendation engine if no external integrations are configured. This is intentional for local testing but not a substitute for a real production Db2 deployment.
- **Next Steps:** Add full user authentication, real-time dashboard widgets, richer Db2 schema, and deeper AI recommendation workflows with a dedicated vector-search layer and a live managed Db2 environment.

---

## Team Members & Credits
| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Your Name | [@yourusername](https://github.com/yourusername) | Project lead / architecture / IBM Db2 integration |
| Team Member 2 | [@member2](https://github.com/member2) | Backend & simulation logic |
| Team Member 3 | [@member3](https://github.com/member3) | AI workflow & analytics |
