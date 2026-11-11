# AnnaSetu — Intelligent IBM Db2-Powered Food Rescue Network

> **One-Line Pitch:** AnnaSetu helps local food donors, NGOs, and volunteers rescue surplus food with evidence-based safety screening, time-aware logistics, verified handoffs, and a traceable IBM Db2 record.

## Table of Contents

- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [IBM Db2 Integration](#ibm-db2-integration)
- [AI / LLM Architecture (if applicable)](#ai--llm-architecture-if-applicable)
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

Good surplus food is often discarded because donors, receiving organizations, and volunteers coordinate through disconnected messages and spreadsheets. This makes it hard to decide whether a batch can be rescued in time, confirm an NGO has capacity, preserve food-safety evidence, and verify what actually reached recipients. AnnaSetu is built for local food donors, verified NGOs, volunteers, and network administrators.

## Solution Overview

AnnaSetu is an existing React dashboard backed by FastAPI and IBM Db2. Its five core innovations are:

1. **Food Safety Passport:** batch-level preparation, expiry, temperature, allergen, storage, human-review, and audit evidence. Deterministic screening returns `HOLD`, `FEASIBLE`, or `INFEASIBLE`; it is not an official food-safety certificate.
2. **Intelligent Rescue Feasibility:** compares remaining time with estimated pickup and delivery time, distance, and declared logistics constraints, and returns explicit rejection reasons.
3. **NGO Capacity Matching:** matches category, storage, verification status, distance, and available kilograms; a Db2 transaction can split a batch across multiple eligible NGOs without over-reserving capacity.
4. **Verified Handoffs:** donor pickup, volunteer delivery, and NGO distribution are role-checked, ordered, timestamped, and confirmed with one-time codes. Actual distributed kilograms are captured in the append-only audit history.
5. **AI Policy Copilot:** LangChain retrieves relevant policy passages from IBM Db2 vector search and returns source citations. Retrieved guidance does not override deterministic safety rules or human review.

The dashboard reports Db2 aggregates for donations, pickups, deliveries, distribution, capacity, and rescue status. Demo access uses generic role labels only. Signup validates email and password policy, hashes passwords, prevents duplicates, and persists role-specific profiles in Db2.

Forgot Password uses a local development-only administrator approval flow. A signed-in Admin verifies the requester and issues a five-minute code shown only in the Admin workspace. The code is stored as a keyed HMAC and can be used once. The MVP sends no email, SMS, or external verification request; it never claims otherwise.

## IBM Db2 Integration

- **Db2 Edition & Environment:** IBM Db2 Community Edition 12.1.5.0 in Docker for local development and demonstration.
- **Connector / Driver Used:** IBM `ibm_db` / `ibm_db_dbi`; `langchain-db2` `DB2VS` for vector retrieval.
- **Database Schema / Data Models:** Db2 stores users and role profiles, food batches, safety observations and human verifications, NGOs, volunteers, rescues, one-time tokens, policy documents and vectors, and hash-chained audit events. See [database schema](docs/DATABASE_SCHEMA.md).
- **Key Queries & Operations:** FastAPI reads and writes directly to Db2 using bound parameters. Allocation reserves receiver capacity and creates rescue rows in a transaction. Failed rescues release reservations. Constraints and triggers protect audit and evidence records. Dashboard totals are SQL aggregates. There is no SQLite or alternate operational database.

## AI / LLM Architecture (if applicable)

- **Framework:** LangChain `langchain-db2` vector-store integration.
- **Model Provider & Model:** No generative model is configured in this MVP. Embeddings are generated locally for the demonstration.
- **RAG / Tool Calling Workflow:** The API embeds the question, retrieves relevant passages from the Db2 `DB2VS` policy collection, and returns the passage and its source citation. The answer is retrieval-grounded; it does not fabricate policy text, certify food, or make allocation decisions.

## Tech Stack

- **Backend / Core:** Python 3.11/3.12, FastAPI, Pydantic, PyJWT, PBKDF2-SHA256.
- **Database:** IBM Db2 Community Edition, `ibm_db`, and `langchain-db2`.
- **Frontend / UI:** React 19 and Vite 7.
- **Libraries & Tools:** Docker Compose, pytest, local embedding model, PowerShell launcher.

## Prerequisites

- Windows 11, Docker Desktop with its Linux engine, and Docker Compose v2.
- Python 3.12 (64-bit) and Node.js 20.19+ or 22.12+ with npm.
- At least 8 GB of memory available to the Db2 container.
- A local Db2 password, a private demo password, and a unique JWT secret. Use placeholders in source-controlled files; keep real values in ignored `.env` files.

## Setup & Installation

Open PowerShell in `submissions\annasetu\src` after cloning the repository:

```powershell
Copy-Item .env.example .env
# Edit .env locally; provide DB2_PASSWORD, JWT_SECRET, and DEMO_PASSWORD.
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r api\requirements.txt
npm ci --prefix frontend
docker compose up -d db2
```

See [IBM Db2 setup](docs/DB2_SETUP.md) for environment details, Docker readiness, and isolated ANNATEST integration-test instructions.

## Configuration

Copy `.env.example` to `.env` and set `DB2_HOST`, `DB2_PORT`, `DB2_NAME`, `DB2_USER`, `DB2_PASSWORD`, `JWT_SECRET`, `ENVIRONMENT`, `SEED_DEMO_DATA`, `DEMO_PASSWORD`, and `CORS_ORIGINS`. Never commit `.env`, `.env.qa`, database passwords, or tokens. For tests, use an isolated `ANNATEST` database and its own private settings; do not point the integration suite at operational `ANNASETU`.

## Running the Project

From the `src` directory:

```powershell
.\start-annasetu.ps1
```

The launcher starts/reuses the Db2 container, FastAPI at `http://127.0.0.1:8010`, and React/Vite at `http://127.0.0.1:5175`. Check API health at `http://127.0.0.1:8010/api/health` and OpenAPI docs at `http://127.0.0.1:8010/docs`. Keep Docker and Db2 running while using AnnaSetu.

## Testing & Verification

From the `src` directory:

```powershell
.\.venv\Scripts\python.exe -m pytest -q api\tests
npm --prefix frontend run build
```

The verified final default backend run reported **58 passed, 0 failed, 8 skipped**; the skips are the opt-in live Db2 tests, not passes. The separate live integration run against `ANNATEST` reported **8 passed, 0 failed, 0 skipped**. Vite 7.3.7 production build passed. The tests cover authentication, signup, role authorization, reset-code expiry and use, Db2 transaction behavior, safety HOLD, feasibility, multi-NGO capacity, handoff/distribution, audit integrity and vector retrieval. Full evidence is in [the testing report](docs/TEST_REPORT.md).

During final verification the live API returned `ANNATEST` and `LangChain Db2 vector ready=true`; direct Db2 SQL reported engine service level `DB2 v12.1.5.0`. The frontend page, React entry, favicon, and 5175 CORS preflight returned successfully. A fresh interactive browser run was blocked because Computer Use was stopped by a physical Escape key; the test report identifies this limitation rather than claiming browser E2E completion.

## Screenshots & Demo

- **Live Demo Link:** No public deployment; run locally at `http://127.0.0.1:5175`.
- **Demo Video Link:** None supplied.
- **Demo walkthrough:** See [the five-minute demo guide](docs/DEMO_GUIDE.md) for role sequence, batch review, capacity allocation, handoffs, audit verification, and policy retrieval.

## Known Limitations & Future Roadmap

- Local password recovery requires a signed-in Admin to verify identity; a single locked-out Admin needs operator-assisted recovery. No email, SMS, SMTP, or production recovery provider is included.
- ETA is a distance-based estimate without live map, route, or traffic data.
- Safety screening is not official certification; required human verification remains part of allocation.
- Handoff codes are relayed manually. The policy copilot retrieves and cites Db2 passages but has no configured generative model.
- Db2 Community Edition is used for local MVP demonstration; production operations require deployment hardening and an appropriate Db2 service.

## Team Members & Credits

| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Rajat | [@rajatrajput2402](https://github.com/rajatrajput2402) | Project lead; full-stack implementation and IBM Db2 integration |

Food-safety source references and technical constraints are documented in the project architecture and demo guide.
