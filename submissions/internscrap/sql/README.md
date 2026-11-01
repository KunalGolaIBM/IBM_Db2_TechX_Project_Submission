# IBM Db2 Developer Extension Setup & Usage Guide

This directory contains the SQL DDL, views, seed data, and analytical queries designed for **InternScrap** and tested with the official **IBM Db2 Developer Extension**.

Official Documentation: [IBM Db2 Developer Extension About](https://ibm.github.io/db2developerextension-about/)

---

## 1. Installation

1. Open **Visual Studio Code** or **Antigravity**.
2. Go to the Extensions marketplace (`Ctrl+Shift+X` or `Cmd+Shift+X`).
3. Search for:
   ```text
   IBM Db2 Developer Extension
   ```
4. Click **Install**.

---

## 2. Connect to Your IBM Db2 Database

### A. Local Docker Container (Recommended)
If running IBM Db2 locally via the root `docker-compose.yml`:
- **Connection Type**: Db2 for Linux, UNIX, and Windows (LUW)
- **Host**: `localhost`
- **Port**: `50000`
- **Database**: `testdb`
- **User**: `db2inst1`
- **Password**: `password`

### B. IBM Cloud Db2 on Cloud
If connecting to an IBM Cloud managed Db2 instance:
- **Host**: `<your-instance>.databases.appdomain.cloud`
- **Port**: `32459` (or specified SSL port)
- **Database**: `bludb`
- **Security**: SSL (`true`)
- **User & Password**: Provided in your IBM Cloud service credentials

---

## 3. Running Scripts in the Extension

Execute the scripts in order:

1. **`01_schema.sql`**: Right-click inside the file editor and select **Run SQL** or press `Ctrl+E, Ctrl+E` to execute. This creates `COMPANIES`, `INTERNSHIPS`, `SKILLS`, `INTERNSHIP_SKILLS`, `APPLICATIONS`, and performance indexes.
2. **`02_views.sql`**: Execute to create analytical views (`V_ACTIVE_INTERNSHIPS`, `V_TOP_IN_DEMAND_SKILLS`, `V_APPLICATION_FUNNEL`, `V_UPCOMING_DEADLINES`).
3. **`03_sample_data.sql`**: Run to seed initial companies and tech internships.
4. **`04_analytics_queries.sql`**: Run the queries interactively to test query plans and view returned result sets directly inside the IDE.
