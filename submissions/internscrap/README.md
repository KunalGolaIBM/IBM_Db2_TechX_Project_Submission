# 🎓 InternScrap: IBM Db2-Powered Internship Aggregator & Lifecycle Tracker

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Database-IBM_Db2-052FAD](https://img.shields.io/badge/Database-IBM%20Db2-052FAD.svg?logo=ibm&logoColor=white)](https://www.ibm.com/products/db2)
[![License-Apache_2.0-green.svg](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)

> **Submitted for the IBM Db2 TechX Summit 2026 Hackathon**  
> *Demonstrating enterprise relational data modeling, indexing, analytical views, and IDE workflows with IBM Db2 and the official IBM Db2 Developer Extension.*

---

## 📌 Problem Statement & Solution

Finding and tracking technical internships is cumbersome. Postings are scattered across dozens of platforms, deadlines are missed, and candidates struggle to organize their application pipelines. 

**InternScrap** solves this by:
1. **Automating Aggregation**: Scraping postings from major tech job boards (RemoteOK, community-maintained GitHub repositories, and curated sources).
2. **Enterprise Persistence on IBM Db2**: Storing structured opportunities, companies, and skills with ACID compliance, relational integrity, and performance indexing.
3. **Application Lifecycle Management**: Enabling applicants to track their progress from discovery to interview to offer.
4. **Actionable Analytics**: Exposing Db2 views for top in-demand skills, upcoming deadlines, and application conversion rates.

---

## 🚀 Meaningful Use of IBM Db2

InternScrap demonstrates deep integration with IBM Db2 capabilities:

1. **Relational Data Modeling & Integrity**:
   - `COMPANIES`: Employers categorized by tier (`Startup`, `Mid`, `Enterprise`, `FAANG`).
   - `INTERNSHIPS`: Structured listing data with composite unique keys on `(SOURCE, EXTERNAL_ID)` for idempotent crawler updates.
   - `SKILLS` & `INTERNSHIP_SKILLS`: Many-to-many bridge mapping roles to normalized technical competencies.
   - `APPLICATIONS`: Tracks applicant stages (`WISHLIST`, `APPLIED`, `ONLINE_ASSESSMENT`, `INTERVIEWING`, `OFFER`, `REJECTED`) with cascading deletes.
2. **Performance Indexing**:
   - Indexes on `DEADLINE`, `IS_REMOTE`, and `STATUS` to accelerate filtered dashboard queries.
   - Indexes on application pipeline stages and follow-up dates.
3. **Advanced Db2 Views**:
   - `V_ACTIVE_INTERNSHIPS`: Filters out expired postings and enriches listings with company metadata.
   - `V_TOP_IN_DEMAND_SKILLS`: Aggregated frequency view computing market demand percentage across active postings.
   - `V_APPLICATION_FUNNEL`: Aggregation of candidate conversion stages.
   - `V_UPCOMING_DEADLINES`: Proactive alerts for opportunities closing within 14 days.
4. **Official `ibm_db` Driver with Resilient Fallback**:
   - Uses parameterized SQL execution with `ibm_db.prepare` and `ibm_db.execute`.
   - Includes transparent fallback mode (`internscrap_dev.sqlite3`) for offline development before Docker is started.

---

## 📁 Repository Structure

```text
submissions/internscrap/
├── README.md               # Project documentation and quickstart
├── architecture.md        # Technical architecture, data flow & Db2 design
├── submission.json        # Hackathon metadata
├── .env.example           # Environment variable template
├── docker-compose.yml     # Local IBM Db2 Community Edition container
├── requirements.txt       # Python dependencies
├── sql/                   # IBM Db2 Developer Extension SQL scripts
│   ├── 01_schema.sql      # Tables, constraints, and indexes
│   ├── 02_views.sql       # Analytical views
│   ├── 03_sample_data.sql # Curated seed data
│   ├── 04_analytics_queries.sql # Analytical queries for extension testing
│   └── README.md          # Extension configuration instructions
├── src/
│   └── internscrap/       # Core Python application
│       ├── cli.py         # Interactive CLI
│       ├── config.py      # Connection configuration
│       ├── db/            # Connection manager & Db2 repository
│       └── scrapers/      # Scraper engine (RemoteOK, GitHub, Curated)
├── tests/                 # Unit and integration test suite
└── docs/
    └── screenshots/       # Documentation assets
```

---

## 💻 IBM Db2 Developer Extension Setup (Step 3)

The project includes SQL scripts in [`sql/`](sql/) designed for the [IBM Db2 Developer Extension](https://ibm.github.io/db2developerextension-about/):

1. **Install the Extension**:
   - In VS Code or Antigravity, search for `IBM Db2 Developer Extension` (`IBM.db2-for-luw`) in the Extensions tab.
2. **Connect**:
   - Connect to your local Db2 container (`localhost:50000`, database `testdb`, user `db2inst1`, password `password`) or IBM Cloud Db2.
3. **Execute**:
   - Run `sql/01_schema.sql` to deploy tables and indexes.
   - Run `sql/02_views.sql` to create views.
   - Run `sql/03_sample_data.sql` to populate sample data.
   - Run `sql/04_analytics_queries.sql` to test query plans.

---

## ⚡ Quickstart

### 1. Install Dependencies
```bash
pip install -r requirements.txt
cp .env.example .env
```

### 2. (Optional) Start Local IBM Db2 Community Edition
```bash
docker-compose up -d db2
```
*Wait ~60 seconds for initialization.*

### 3. Initialize Database Schema
```bash
python -m src.internscrap init-db
```

### 4. Scrape Internships
```bash
python -m src.internscrap scrape --source sample
# Or scrape live public feeds:
# python -m src.internscrap scrape --source all
```

### 5. Explore & Search
```bash
# List all active postings
python -m src.internscrap list

# Search by keyword and filter by remote
python -m src.internscrap list --remote --keyword "Python"

# Inspect detailed view for a single internship
python -m src.internscrap show 1
```

### 6. Track Applications & View Funnel Metrics
```bash
# Record an application
python -m src.internscrap track 1 --status APPLIED --notes "Applied with referral"

# Advance application stage
python -m src.internscrap track 1 --status INTERVIEWING --follow-up 2026-11-20

# View application status board
python -m src.internscrap applications

# View analytics computed by Db2 views
python -m src.internscrap stats

# Export to CSV or JSON
python -m src.internscrap export --format csv
```

---

## 🧪 Automated Testing

Run the test suite:
```bash
pytest submissions/internscrap/tests/
```
