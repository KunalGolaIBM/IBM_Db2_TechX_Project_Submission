# GL Bajaj Campus Intelligence & Placement Analytics

> One-line pitch: A Db2-powered analytics platform for GL Bajaj institutions to monitor student performance, placement readiness, and academic resource utilization in real time.

---

## Table of Contents
- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [IBM Db2 Integration](#ibm-db2-integration)
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

Educational institutions deal with fragmented data across attendance, assignments, lab utilization, and placement records. At GL Bajaj, this makes it difficult for faculty and administrators to quickly identify at-risk students, understand placement readiness, and monitor academic performance trends.

The current process depends largely on manual spreadsheets and delayed reports, which limits early intervention and data-driven decisions. This project addresses that gap by building a centralized intelligence layer that turns institutional data into actionable insights.

---

## Solution Overview

This project provides a Db2-powered analytics dashboard for GL Bajaj institutions. It consolidates academic and career data into a unified model and offers a simple interface to:

- View student performance trends by department, section, and semester
- Predict low-engagement or at-risk students using score and attendance patterns
- Track placement readiness metrics such as aptitude, technical skills, and mock interview performance
- Monitor department-wise resource usage, lab attendance, and event participation
- Generate summary reports for faculty coordinators and administrators

The solution consists of a Python backend connected to IBM Db2, a dashboard layer for visualization, and a lightweight analytics workflow for key institutional KPIs.

---

## IBM Db2 Integration

- Db2 Edition & Environment: IBM Db2 Community Edition running via Docker
- Connector / Driver Used: Python `ibm_db` driver
- Database Schema / Data Models: The system uses tables such as `students`, `courses`, `attendance`, `assignments`, `placements`, `skills`, and `department_summary`
- Key Queries & Operations: Aggregations for semester averages, placement readiness scoring, attendance anomalies, and department resource summaries

Example Db2 operations included in the backend:

- Query aggregated performance by department and semester
- Join student records with attendance and placement metrics
- Compute readiness scores and anomaly alerts
- Generate institutional summary reports through SQL views and aggregate queries

---

## Tech Stack

- Backend / Core: Python 3.11, FastAPI
- Database: IBM Db2 Community Edition
- Frontend / UI: Streamlit dashboard
- Libraries & Tools: `ibm_db`, `pandas`, `plotly`, `python-dotenv`

---

## Prerequisites

Before starting, make sure you have:

- Docker installed for Db2 container setup
- Python 3.10+ installed
- Access to a running Db2 instance or local Db2 Community Edition container
- `pip` or `venv` for dependency installation

---

## Setup & Installation

```bash
# 1. Clone the repository
cd submissions/gl-bajaj-db2-campus-insights

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` and set your local Db2 credentials:

```bash
cp .env.example .env
```

Example environment variables:

```env
DB2_HOST=localhost
DB2_PORT=50000
DB2_DATABASE=SAMPLE
DB2_USER=db2inst1
DB2_PASSWORD=your-password
DB2_SCHEMA=GLBAJAJ
```

> Security Warning: Do not commit `.env` or real credentials to GitHub.

---

## Running the Project

```bash
# Run the dashboard or backend entrypoint
python src/main.py
```

The application will connect to Db2, load aggregated metrics, and print or render the institutional analytics summary.

---

## Testing & Verification

```bash
# Basic validation for schema and database connection
python src/main.py
```

Suggested verification steps:

- Confirm Db2 connection succeeds
- Ensure sample queries return expected records
- Validate summary metrics for department and placement dashboards

---

## Screenshots & Demo

- Live Demo Link: [Add URL if hosted]
- Demo Video Link: [Add YouTube or Loom link]
- Dashboard screenshots can be placed in `docs/screenshots/`

---

## Known Limitations & Future Roadmap

- Current version assumes a local or test Db2 environment
- Real-time alerts and ML-based predictions can be extended in a future release
- Additional modules may include scholarship tracking, attendance heatmaps, and student engagement forecasting

---

## Team Members & Credits

| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Ashfaq Khan | [@ashpaqkhan068-hub](https://github.com/ashpaqkhan068-hub) | Project lead, Db2 integration, backend logic |
| Team Member 2 | [@username](https://github.com/username) | Dashboard / analytics / documentation |
| Team Member 3 | [@username](https://github.com/username) | UI and testing |

