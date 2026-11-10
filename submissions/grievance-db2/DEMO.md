# 🎬 DEMO.md — Judge's Walkthrough Guide
## CPGRAMS AI Grievance Portal | IBM Db2Hack 2026 Submission by Falak Naaz

> **Quick Start**: `cd submissions/grievance-db2 && docker compose up --build -d`  
> Db2 takes ~3 min to initialize. Then access: **http://localhost:80**

---

## 🚀 5-Minute Judge Demo Script

### Step 1 — Verify IBM Db2 is Live

```bash
# Health check — confirms Db2 connection and seeded dataset
curl -s http://localhost:8000/api/health | python -m json.tool
```

**Expected output:**
```json
{
  "status": "healthy",
  "database": {
    "type": "IBM Db2",
    "database": "GRIEVDB",
    "status": "connected",
    "total_grievances": 75
  },
  "version": "2.0.0"
}
```

✅ **WOW MOMENT**: The IBM Db2 Live Badge in the header turns **green** automatically.

---

### Step 2 — Lodge a Critical Grievance with LangChain AI Triage

```bash
curl -X POST http://localhost:8000/api/grievances \
  -H "Content-Type: application/json" \
  -d '{
    "citizen_name": "Falak Naaz",
    "contact": "9999888877",
    "category": "electricity",
    "subject": "Live sparking wire outside primary school",
    "description": "Dangling 11kV high-voltage wire sparking continuously near entrance of government primary school. Children at immediate risk. Emergency hazard since morning.",
    "ward": "Ward 14 - Rohini East",
    "priority": "Medium"
  }'
```

**Expected:** AI triage **elevates** priority from `Medium` → **`Critical`** + Ward Hotspot Alert fires.

✅ **WOW MOMENT**: LangChain detected the life-safety emergency and overrode the citizen's priority selection.

**UI Demo**: Open `http://localhost:80/lodge-grievance.html` and type the description — watch the **live AI triage preview card** update in real time as you type.

---

### Step 3 — Native IBM Db2 Stored Procedure Execution

```bash
curl -X POST http://localhost:8000/api/escalate-overdue | python -m json.tool
```

**Expected:**
```json
{
  "success": true,
  "procedure": "SP_ESCALATE_OVERDUE",
  "escalated_count": 12,
  "total_sla_breach_count": 15,
  "execution_method": "db2_sql_date_arithmetic",
  "db2_query_used": "DAYS(CURRENT DATE) - DAYS(DATE(created_at)) > 15",
  "message": "IBM Db2 SP_ESCALATE_OVERDUE: Elevated 12 overdue docket(s)..."
}
```

✅ **WOW MOMENT**: Native IBM Db2 date arithmetic (`DAYS(CURRENT DATE)`) executing inside the Db2 engine.

**UI Demo**: Officer Console (`http://localhost:80/officer.html`) → Click **"Run SP_ESCALATE_OVERDUE"** red button → See escalated count animate in.

---

### Step 4 — LangChain "Ask the Data" NL-to-SQL

```bash
# Natural language to IBM Db2 SQL, executed live
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Show all grievances that have breached the 15 day SLA"}'
```

**Expected:** Generated SQL uses `DAYS(CURRENT DATE) - DAYS(DATE(created_at)) > 15` — **native Db2 syntax**. Returns real rows with `days_open` column.

**Security Test:**
```bash
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "DROP TABLE grievances;"}'
# Expected: 400 Bad Request — Security Violation
```

**UI Demo**: `http://localhost:80/ask-data.html` — Ask "Which ward has the most complaints?" → See the natural language summary + generated Db2 SQL + live results table.

---

### Step 5 — IBM Db2 SYSCAT Catalog Inspector

```bash
curl -s http://localhost:8000/api/db2/catalog | python -m json.tool
```

**Expected:** Shows live metadata from `SYSCAT.TABLES`, `SYSCAT.INDEXES`, `SYSCAT.TRIGGERS`, `SYSCAT.ROUTINES` — proves deep Db2 integration beyond basic CRUD.

**UI Demo**: Dashboard (`http://localhost:80/dashboard.html`) → Scroll to **"IBM Db2 System Catalog Inspector (SYSCAT)"** panel — see live schema metadata rendered in a dark terminal-style table.

---

### Step 6 — Agentic Sahayak Tool-Calling Assistant

```bash
curl -X POST http://localhost:8000/api/sahayak/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the status of complaint GRV-2026-1028?"}'
```

**Expected:** Autonomous `tool_track_docket` invocation — queries GRIEVDB, computes `days_open` with Db2 date arithmetic, returns SLA breach status.

```bash
curl -X POST http://localhost:8000/api/sahayak/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Are there active complaints in Rohini?"}'
```

**Expected:** Autonomous `tool_ward_status` — aggregates open cases, critical count, SLA breaches for the matched ward.

---

### Step 7 — Export Grievances as CSV (Backend-Powered)

```bash
# Download all SLA-breached grievances as CSV
curl -s "http://localhost:8000/api/export/csv?sla_breached=true" -o sla_breaches.csv
head sla_breaches.csv
```

---

### Step 8 — Run All 20 Tests

```bash
docker exec grievance-api pytest -v --tb=short
# Expected: 20 passed in ~6 seconds
```

---

## 🌟 Top 3 "Wow Moments" for Judges

| # | Feature | Judges Can See This In |
|---|---|---|
| 1 | **LangChain AI elevates priority** from Medium → Critical based on description semantics | Lodge Grievance page — real-time triage preview card |
| 2 | **Native IBM Db2 Stored Procedure** `SP_ESCALATE_OVERDUE` with Db2 date arithmetic | Officer Console → Red "Run SP" button |
| 3 | **NL-to-SQL → Db2 execution → results** in one round-trip, with security guardrails | Ask the Data page — type "Show SLA breaches" |

---

## 🗄️ Direct IBM Db2 CLI Verification

```bash
# Connect to Db2 and verify data
echo "connect to GRIEVDB; SELECT COUNT(*) FROM grievances; SELECT COUNT(*) FROM grievance_updates; terminate;" | \
  docker exec -i grievance-db2 su - db2inst1 -c "db2 -tv"

# Verify the kernel trigger exists
echo "connect to GRIEVDB; SELECT TRIGNAME, TRIGEVENT FROM SYSCAT.TRIGGERS WHERE TABSCHEMA=CURRENT SCHEMA; terminate;" | \
  docker exec -i grievance-db2 su - db2inst1 -c "db2 -tv"

# Verify the stored procedure exists
echo "connect to GRIEVDB; SELECT ROUTINENAME FROM SYSCAT.ROUTINES WHERE ROUTINESCHEMA=CURRENT SCHEMA; terminate;" | \
  docker exec -i grievance-db2 su - db2inst1 -c "db2 -tv"
```

---

## 📱 All Frontend Pages

| Page | URL | Key IBM Db2 Feature Demonstrated |
|---|---|---|
| Home | `localhost:80` | Db2 Live Badge, real-time health check |
| Lodge Grievance | `localhost:80/lodge-grievance.html` | AI Triage → stores to Db2 |
| Track Status | `localhost:80/track-status.html` | SLA countdown using Db2 `DAYS()` |
| Officer Console | `localhost:80/officer.html` | SP_ESCALATE_OVERDUE · LangChain Action Drafter |
| Analytics Dashboard | `localhost:80/dashboard.html` | SYSCAT Explorer · GIS Map · Charts |
| Ask the Data | `localhost:80/ask-data.html` | LangChain NL→Db2 SQL |
| API Docs | `localhost:8000/docs` | Full OpenAPI spec |

---

## 🔧 Troubleshooting

**Db2 not ready yet?**
```bash
docker logs grievance-db2 | tail -20
# Look for: "Setup has completed" or "SQL1063N DB2START processing was successful"
```

**API health shows degraded?**
```bash
docker logs grievance-api | tail -20
# Restart if needed: docker compose restart grievance-api
```

**Full reset:**
```bash
docker compose down -v && docker compose up --build -d
```
