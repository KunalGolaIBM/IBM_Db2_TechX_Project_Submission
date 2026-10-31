# Db2 Python Integration Starter

> **One-Line Pitch:** A clean, production-ready Python starter kit demonstrating secure connectivity, schema verification, and transactional query execution against IBM Db2 using the native `ibm_db` driver.

---

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

---

## Problem Statement
- **Challenge:** Integrating enterprise relational databases like IBM Db2 into modern Python application stacks often presents setup hurdles, driver configuration issues, and credential management complexity for developers new to the Db2 ecosystem.
- **Target Audience:** Developers, database administrators, and students building Python backends, microservices, or data ingestion pipelines on IBM Db2.
- **Why Existing Tooling Is Insufficient:** Standard tutorials often rely on outdated client wrappers, omit secure TLS/SSL configuration parameters, or lack modular, reproducible boilerplates for enterprise environments.

---

## Solution Overview
- Provides a clean, isolated starter blueprint demonstrating secure SSL/TLS connection lifecycle management using IBM's official `ibm_db` driver.
- Implements core relational verification checks, parameterized querying, and robust exception handling for database runtime failures.
- Offers a structured foundation easily extensible into REST APIs (FastAPI/Flask) or larger agentic/data workflows.

---

## IBM Db2 Integration
- **Db2 Edition & Environment:** IBM Db2 on Cloud / Db2 Community Edition (Docker containerized instance).
- **Connector / Driver Used:** `ibm_db` (native C-based Python driver for IBM Db2).
- **Database Schema / Data Models:** Uses system catalog tables (`SYSIBM.SYSDUMMY1`) for baseline handshake verification, extensible to custom schema definitions.
- **Key Queries & Operations:** 
  - Parameterized DSN connection setup with SSL verification flags.
  - Active session ping via `SELECT 1 FROM SYSIBM.SYSDUMMY1`.
  - Transaction commit and safe connection teardown logic.

---

## AI / LLM Architecture (if applicable)
- *N/A (Core database connectivity & driver integration layer; can serve as the data persistence and retrieval layer for RAG pipelines or NL-to-SQL workflows).*

---

## Tech Stack
- **Backend / Core:** Python 3.11+
- **Database:** IBM Db2
- **Driver:** `ibm_db`
- **Development Tooling:** Visual Studio Code, IBM Db2 Developer Extension

---

## Prerequisites
- Python 3.10 or higher
- Access to an active IBM Db2 instance (IBM Cloud Db2 or local Db2 Docker container)
- Visual Studio Code with the **IBM Db2 Developer Extension** installed

---

## Setup & Installation

```bash
# 1. Navigate to the submission directory
cd submissions/db2-python-starter

# 2. Set up and activate a Python virtual environment
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

# 3. Install the IBM Db2 driver
pip install ibm_db