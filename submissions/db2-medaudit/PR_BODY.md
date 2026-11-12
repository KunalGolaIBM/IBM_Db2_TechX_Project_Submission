# IBM Db2 TechX Summit 2026 — Project Submission

> **PR Title Format (required):** `[Submission] db2-medaudit: DB2 MedAudit — AI Clinical Test Verification & Lab Kickback Detection`
>
> **Folder Format (required):** `submissions/db2-medaudit/`
>
> **Mandatory Next Step:** After opening this PR, submit the PR URL through the official Google Form: **[GOOGLE_FORM_LINK_TO_BE_ADDED]**.

---

## 1. Project Overview

- **Project Title:** DB2 MedAudit — AI Clinical Test Verification & Lab Kickback Detection
- **Project Slug (must match folder name):** `submissions/db2-medaudit/`
- **Short Description (1–3 sentences):** An intelligent medical prescription audit platform powered by IBM Db2 and LangChain/Gemini. It detects unnecessary diagnostic tests prescribed by doctors who hold active commission contracts with diagnostic labs, protecting patients from financial exploitation and medical overtreatment. The system cross-references prescriptions against NICE, WHO, and ICMR clinical guidelines stored in Db2, and flags suspicious doctor–lab kickback agreements.
- **Problem Solved & Target Audience:** Diagnostic lab kickbacks cause patients to be prescribed costly and unwarranted tests (MRIs, CT scans, full blood panels) by doctors earning commissions of 25–40%. Target audience: hospital compliance officers, health insurance auditors, and patient advocacy groups.

---

## 2. Team Information

- **Team Name:** MedAudit

| Full Name | GitHub Username | Email / Role |
|---|---|---|
| Aradhya Awasthi | @aradhyaawasthi2006-hue | Full-Stack Developer / IBM Db2 Integration / AI Agent |

---

## 3. IBM Db2 Integration Summary

- **IBM Db2 Edition / Environment:** IBM Db2 Community Edition 11.5.8 on Docker (`ibmcom/db2:11.5.8.0`); also compatible with Db2 on IBM Cloud.
- **How IBM Db2 is Used in the Solution:** Db2 is the authoritative backend storing all clinical intelligence data — evidence-based diagnostic guidelines (NICE/WHO/ICMR), physician profiles with suspicion scores, lab commission contracts (kickback data), test pricing benchmarks, and patient encounter audit logs. Every audit run queries Db2 for context and writes results back.
- **Db2 Connector / Driver / Framework Integration Used:** `ibm_db >= 3.2.0` (native Python driver), `ibm_db_sa >= 0.4.0` (SQLAlchemy dialect), and LangChain's `SQLDatabase` / `SQLDatabaseToolkit` for the AI agent to introspect and query the Db2 schema autonomously.
- **Schema & Data Stored / Processed:** `CLINICAL_INTELLIGENCE` schema with 6 tables: `CLINICAL_GUIDELINES`, `DIAGNOSTIC_LABS`, `DOCTORS`, `LAB_COMMISSION_CONTRACTS`, `TEST_CATALOG`, and `AUDIT_LOGS`. Stored in custom tablespace `TS_MEDAUDIT` with DESC indexes optimised for suspicion-score and savings queries.
- **Steps to Verify Db2 Integration:**
  1. Start the Db2 Docker container and load `src/scripts/schema_ibm_db2.sql`.
  2. Set environment variables from `.env.example`.
  3. Run `python src/scripts/medaudit_langchain_agent.py` — it will connect to Db2, query guidelines and commission tables, and print an audit report.
  4. Alternatively, open the web app and use **DB2 Studio** tab to run live SQL queries against the schema.

---

## 4. Technology Stack & AI / LLM Usage

- **Programming Languages:** TypeScript, Python 3.10+, SQL (Db2 LUW DDL)
- **Frameworks & Libraries:** React 19, Vite, TailwindCSS 4, Express, LangChain, SQLAlchemy, `ibm_db`, `ibm_db_sa`, `python-dotenv`, `motion`, Lucide React
- **AI / LLM Framework:** LangChain (`create_sql_agent` + `SQLDatabaseToolkit`)
- **Model Provider & Model Name:** Google Gemini `gemini-1.5-pro` via `langchain-google-genai`
- **Where AI/LLM is Applied in the Workflow:** The LangChain SQL agent autonomously generates and executes Db2 SQL queries to retrieve clinical guidelines, doctor suspicion data, and active kickback contracts. Gemini then synthesises this structured context into a natural-language audit report: flagging each unwarranted test with clinical rationale, estimating patient savings, and assigning a risk alert level (Low / Medium / High / Critical).

---

## 5. Demonstration & Links

- **Live Demo URL (if hosted):** *(not hosted — run locally via `npm run dev`)*
- **Demo Video (YouTube / Loom / Drive):** *(not recorded yet)*
- **External Source Repo (if hosted separately):** https://github.com/aradhyaawasthi2006-hue/MedAudit
- **Presentation / Slides URL (optional):** *(N/A)*

---

## 6. Submission Verification Checklist

- [x] **Folder Structure:** My submission is placed in a single new directory under `submissions/db2-medaudit/` copied from `submissions/_template/`.
- [x] **Naming Conventions:** The `db2-medaudit` slug uses lowercase letters, numbers, and hyphens only, matching the branch name `submission/db2-medaudit` and this PR title.
- [x] **Complete Documentation:** Both `submissions/db2-medaudit/README.md` and `submissions/db2-medaudit/architecture.md` are completely filled out without unfilled placeholder markers.
- [x] **Metadata File:** `submissions/db2-medaudit/submission.json` is completed and valid JSON.
- [x] **No Secrets or Credentials:** No API keys, passwords, or real connection strings are committed. `.env.example` contains placeholder values only.
- [x] **Tested Setup Instructions:** Setup and run instructions have been verified and are reproducible from a fresh environment.
- [x] **License Declared:** Project is open-source; source code is publicly available at the linked GitHub repository.
- [x] **Code of Conduct:** All team members agree to adhere to the repository Code of Conduct.
- [x] **Scope Isolation:** This PR only adds files inside `submissions/db2-medaudit/` and does not touch root files or other submissions.
- [ ] **Google Form Submission:** I understand that opening this PR is step 1, and I will submit this PR URL into the official Google Form (**[GOOGLE_FORM_LINK_TO_BE_ADDED]**).

---

## 7. Additional Notes for Reviewers & Judges

**Architecture Highlights:**

The project has two independently runnable components:

1. **React Web App** (`npm run dev`): A fully functional interactive dashboard with three views:
   - **Audit Workspace** — enter a prescription and see instant AI-generated audit results
   - **DB2 Studio** — a live SQL query runner connected to the Db2 backend
   - **Kickback Matrix** — a leaderboard of doctors ranked by suspicion score, visualising commission contract data

2. **Python LangChain Agent** (`medaudit_langchain_agent.py`): A standalone AI agent that uses `create_sql_agent` with the Db2 schema as tools. The agent autonomously decides which SQL queries to issue against Db2 to build the full audit context before prompting Gemini.

**IBM Db2 Design Decision:** The `CLINICAL_INTELLIGENCE` schema uses a custom 8K-page buffer pool and tablespace for optimised I/O on large CLOB guideline text. DESC indexes on `SUSPICION_SCORE` and `POTENTIAL_SAVINGS` enable fast leaderboard queries without full table scans.

**Validation:** The submission was validated with `python scripts/validate_submission.py submissions/db2-medaudit` — all checks passed.
