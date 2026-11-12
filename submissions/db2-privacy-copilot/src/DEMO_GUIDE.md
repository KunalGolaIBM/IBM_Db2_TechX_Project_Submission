# Db2 Privacy Copilot — Pitch and Demo Guide

## 30-second pitch

Privacy teams often cannot quickly see where personal information sits across
related database tables, how consent changed over time, or what a rights request
would affect. Db2 Privacy Copilot connects to IBM Db2 to map schemas, classify
likely PII, track temporal consent, and prepare reviewable erasure plans. AI can
help identify and plan; deterministic SQL guardrails and a human DPO approval
control sensitive execution, with the change and audit record committed as one
transaction.

## Five-minute live walkthrough

Use synthetic clinic records only. For a real Db2 demo, start the stack using
[QUICKSTART.md](QUICKSTART.md), bootstrap the schema, and seed the demo data.
Open <http://localhost:8501>.

### 1. Introduce the problem and solution (30 seconds)

On the landing page, say:

> “Privacy reviews are difficult when personal data is spread across related
> tables. This workspace helps a team discover the data, understand consent and
> retention context, and prepare accountable actions without handing execution
> to an AI agent.”

Point out the workflow from discovery through review and audit.

### 2. Show schema discovery (45 seconds)

Open **Discovery** and run a schema scan. Show the Db2 catalog-derived tables,
columns, and foreign-key relationships. Explain that relationships determine
the safe order for child records and the root subject record.

### 3. Run PII classification (45 seconds)

Open **Classification** and run it before creating an erasure request. Show a
few labels and confidence/review signals. Explain that deterministic value
checks and semantic column-name matching identify candidates; a label is a
review aid, not a legal determination.

### 4. Show consent history (40 seconds)

Open **Consents** and load consent for synthetic Patient ID `1`. If time allows,
grant a demo purpose and reload it. Explain that Db2 temporal tables preserve
business-time consent validity and system-time history.

### 5. Create and approve a rights request (90 seconds)

Open **Rights Requests** and sign in as **ANALYST** if needed. Create an
erasure-review request for synthetic Patient ID `1`. Show the dry-run steps,
estimated impact, retention notes, and plan hash. Explain that request creation
stores a pending plan; it does not change the patient data.

Sign out and sign in as **DPO**. Open **Review approvals**, inspect the request
and its plan, check the human-review confirmation, then choose **Approve and
execute**. Explain that the API regenerates the approved plan, checks its hash,
validates each statement through the deterministic guardrail, and performs the
approved changes in a Db2 transaction. If execution fails, the transaction
rolls back and the request returns to pending review.

### 6. Verify the audit trail (30 seconds)

Open **Audit Log** and verify the chain. Point out that the erasure event and
data changes commit together, and each event is linked to the prior event with
SHA-256 hashes.

### 7. Close (20 seconds)

> “Db2 is the system of record for the application data, temporal consent,
> privacy requests, taxonomy vectors, and audit history. Agents help prepare
> the work; people approve it, and deterministic controls govern execution.”

## If Db2 is unavailable on the presentation laptop

The fallback uses an in-memory mock database with synthetic sample records. It
can demonstrate the same UI and analyst-to-DPO workflow, but it is **not a real
Db2 integration demo**, and its changes disappear when the API process stops.
The UI/API can be run in two PowerShell terminals from the project directory:

```powershell
# Terminal 1: mock API
$env:DB_MOCK = "1"
$env:PYTHONUTF8 = "1"
.\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8001
```

```powershell
# Terminal 2: Streamlit UI
$env:DB_MOCK = "1"
$env:PYTHONUTF8 = "1"
$env:API_BASE_URL = "http://127.0.0.1:8001"
.\.venv\Scripts\python.exe -m streamlit run ui/app.py --server.port 8501 --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
```

Then open <http://localhost:8501>. State clearly that this is the fallback
environment. Do not present its mock health response as proof of a live Db2
connection.

## Questions you may get

**Does an AI agent execute erasure?** No. Agents can discover, classify, and
draft plans. A DPO approves, and deterministic code validates the plan and SQL
before execution.

**How does the app use Db2?** The connector reads Db2 catalog metadata and
persists clinic/demo records, consent history, requests, classification output,
and audit events. LangChain's DB2VS integration supports semantic lookup of PII
taxonomy labels with local embeddings.

**Does this certify legal compliance?** No. It is decision-support software for
a privacy workflow demonstration. Retention rules need review by qualified
privacy and legal stakeholders before operational use.

**Is the role picker production authentication?** No. It is a demo persona
selector. Deployment tokens can be configured through environment variables,
but a real deployment handling personal data requires an identity provider,
strong authentication, least-privilege database credentials, and an approved
security review.
