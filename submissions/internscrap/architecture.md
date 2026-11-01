# Architecture: InternScrap on IBM Db2

## 1. Idea & Motivation
Internship applicants face hundreds of scattered job postings, varying application deadlines, and fragmented tracking tools. **InternScrap** addresses this by automating internship aggregation from public tech feeds (RemoteOK, community-maintained GitHub repositories, and curated sources), normalizing listings into a structured **IBM Db2** relational database, and managing candidate application lifecycles through performant Db2 views and indexes.

---

## 2. System Components

| Component | Location | Role |
| :--- | :--- | :--- |
| **Db2 Relational Schema** | `sql/01_schema.sql` | DDL creating normalized tables (`COMPANIES`, `INTERNSHIPS`, `SKILLS`, `INTERNSHIP_SKILLS`, `APPLICATIONS`) with foreign key constraints, cascading deletes, and unique constraints. |
| **Db2 Views Engine** | `sql/02_views.sql` | Reusable SQL views for active opportunities, in-demand technical skills, upcoming application deadlines, and application pipeline funnel stages. |
| **Db2 Extension Queries** | `sql/04_analytics_queries.sql` | Multi-table joins and aggregations optimized for execution and query plan inspection in the official IBM Db2 Developer Extension. |
| **Connection & Repository Layer** | `src/internscrap/db/` | Connects natively to IBM Db2 using the official `ibm_db` driver with parameterized queries and fallback simulation. |
| **Scraper & Ingestion Pipeline** | `src/internscrap/scrapers/` | Fetches, parses, and standardizes internship postings from web and API endpoints. |
| **CLI & Application Tracker** | `src/internscrap/cli.py` | Interactive CLI interface for scraping, searching, application tracking, viewing metrics, and data export. |
| **Containerized Database** | `docker-compose.yml` | Provisions local IBM Db2 Community Edition (`icr.io/db2_community/db2`) with persistent storage. |

---

## 3. Data Flow

```text
[ Job Sources: RemoteOK / GitHub / Curated ]
                     │
                     ▼
       [ Scraper & Parser Engine ]
  (Extracts title, company, stipend, skills, deadline)
                     │
                     ▼
          [ Repository Layer ]
     (Upserts company, skills, listing)
                     │
                     ▼
         ┌───────────────────────┐
         │     IBM Db2 LUW       │
         │───────────────────────│
         │ - COMPANIES           │
         │ - INTERNSHIPS         │◄──── [ User CLI Actions: track, list ]
         │ - SKILLS              │
         │ - INTERNSHIP_SKILLS   │
         │ - APPLICATIONS        │
         └───────────┬───────────┘
                     │
                     ▼
           [ Analytical Views ]
      - V_ACTIVE_INTERNSHIPS
      - V_TOP_IN_DEMAND_SKILLS
      - V_APPLICATION_FUNNEL
      - V_UPCOMING_DEADLINES
                     │
                     ▼
   [ CLI Dashboard / IBM Db2 Dev Extension ]
```

---

## 4. IBM Db2 Schema Design

### Core Tables & Integrity

1. **`COMPANIES`**: Centralized employer entities with tier classification (`Startup`, `Mid`, `Enterprise`, `FAANG`).
2. **`INTERNSHIPS`**: Primary listings with composite uniqueness on `(SOURCE, EXTERNAL_ID)` enabling idempotent web crawling.
3. **`SKILLS` & `INTERNSHIP_SKILLS`**: Many-to-many bridge mapping roles to normalized technical competencies.
4. **`APPLICATIONS`**: Candidate application lifecycle stages (`WISHLIST`, `APPLIED`, `ONLINE_ASSESSMENT`, `INTERVIEWING`, `OFFER`, `REJECTED`) linked via foreign key to `INTERNSHIPS` with `ON DELETE CASCADE`.

### Performance Indexes

To optimize filtered retrieval across large listing sets:
```sql
CREATE INDEX IX_INT_COMPANY   ON INTERNSHIPS (COMPANY_ID);
CREATE INDEX IX_INT_DEADLINE  ON INTERNSHIPS (DEADLINE);
CREATE INDEX IX_INT_REMOTE    ON INTERNSHIPS (IS_REMOTE);
CREATE INDEX IX_INT_STATUS    ON INTERNSHIPS (STATUS);
CREATE INDEX IX_APP_STATUS    ON APPLICATIONS (STATUS);
CREATE INDEX IX_APP_FOLLOWUP  ON APPLICATIONS (FOLLOW_UP_DATE);
```

---

## 5. IBM Db2 Views & Analytics

### `V_TOP_IN_DEMAND_SKILLS`
Calculates skill frequency and market percentage across active postings:
```sql
CREATE OR REPLACE VIEW V_TOP_IN_DEMAND_SKILLS AS
SELECT 
    s.NAME AS SKILL_NAME,
    s.CATEGORY AS SKILL_CATEGORY,
    COUNT(isk.INTERNSHIP_ID) AS LISTING_COUNT,
    ROUND(CAST(COUNT(isk.INTERNSHIP_ID) AS DOUBLE) * 100.0 / 
          NULLIF((SELECT COUNT(*) FROM INTERNSHIPS WHERE STATUS = 'ACTIVE'), 0), 2) AS DEMAND_PERCENTAGE
FROM SKILLS s
JOIN INTERNSHIP_SKILLS isk ON s.ID = isk.SKILL_ID
JOIN INTERNSHIPS i ON isk.INTERNSHIP_ID = i.ID
WHERE i.STATUS = 'ACTIVE'
GROUP BY s.NAME, s.CATEGORY;
```

### `V_APPLICATION_FUNNEL`
Aggregates candidate conversion stages:
```sql
CREATE OR REPLACE VIEW V_APPLICATION_FUNNEL AS
SELECT 
    a.STATUS AS STAGE,
    COUNT(a.ID) AS TOTAL_COUNT,
    MIN(a.APPLIED_DATE) AS EARLIEST_APPLICATION,
    MAX(a.APPLIED_DATE) AS LATEST_APPLICATION
FROM APPLICATIONS a
GROUP BY a.STATUS;
```

---

## 6. IBM Db2 Developer Extension Integration

All SQL DDL, views, seed data, and analytical queries in the `sql/` folder are formatted for direct execution in the **IBM Db2 Developer Extension** (`IBM.db2-for-luw`) in VS Code or Antigravity:
- Connection profile: `localhost:50000` / database `testdb`.
- Developers can inspect execution plans (`EXPLAIN`), view returned result sets, and run queries interactively with `Ctrl+E, Ctrl+E`.
