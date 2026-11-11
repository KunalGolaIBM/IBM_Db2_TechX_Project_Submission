# ShipSafe AI: Pre-PR Production-Readiness Gate on IBM Db2

> **One-line pitch:** ShipSafe AI checks a repository before the pull request is opened (secrets, SQL injection, risky code, vulnerable dependencies, failing tests), returns a deterministic `PASS` / `PASS_WITH_WARNINGS` / `BLOCKED` decision, stores every assessment in **IBM Db2**, and attaches the governing engineering policy to each finding using **LangChain + Db2 vector search**.

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
- Code is now written faster than it can be reviewed. AI assistants and tight deadlines produce pull requests that compile and pass a quick test but still contain a hardcoded key, an f-string SQL query or a dependency with a known CVE.
- **Who feels it:** developers who want a fast "is this safe to open?" answer, reviewers and tech leads who must enforce team policy, and platform/DBA teams that own Db2 security rules (parameterized SQL, no credentials in code).
- **Why current tooling falls short:** scanners such as Bandit, Gitleaks and pip-audit each print their own output and keep no history. Nothing ties a finding to *your* written policy, nothing remembers whether the same issue was flagged last week, and nothing gives a single, explainable merge decision.

## Solution Overview
ShipSafe AI is a local-first assessment engine with a CLI and an MCP server:

1. **Discover** the workspace: languages, manifests, test suites, Git branch and changed files.
2. **Scan** with deterministic, explainable rules: secrets, SAST (SQL built with f-strings / `%` / concatenation, `shell=True`, `eval`/`exec`, `pickle`), dependency CVEs, syntax and bare `except:`, and the project's own test suite.
3. **Normalize** every result into one finding contract with a stable SHA-256 fingerprint, so the same issue keeps the same identity across runs.
4. **Gate** with a deterministic policy: any critical/high finding or failing test gives `BLOCKED`. No model can override this decision.
5. **Persist** project, assessment, tool runs, findings and dependency inventory to **IBM Db2**.
6. **Explain** each finding by retrieving the matching team policy from a **Db2 vector store** through **LangChain** (`langchain-db2`), quoting the policy text and section verbatim.
7. **Track** history, regressions (new / resolved / unchanged findings) and a risk trend computed in Db2 with window functions.

The same capabilities are exposed as **7 MCP tools**, so IBM Bob or any MCP client can run an assessment from inside the IDE.

## IBM Db2 Integration
- **Db2 edition & environment:** IBM Db2 Community Edition **12.1.5** in Docker (`icr.io/db2_community/db2`). Also works with Db2 on Cloud (`DB2_SECURITY=SSL`). Native `VECTOR` support needs 12.1.2 or later.
- **Connectors / drivers:** `ibm_db` / `ibm_db_dbi` (DB-API 2.0) for all relational work; `langchain-db2` (`DB2VS`) for the vector store, sharing the same connection.
- **Schema (schema `SHIPSAFE`, created automatically, full DDL in [`docs/db2-schema.sql`](docs/db2-schema.sql)):**

  | Object | Purpose |
  |---|---|
  | `PROJECTS` | One row per scanned repository (hashed root path, branch) |
  | `ASSESSMENTS` | One row per run: profile, gate status, reason, severity counts, timings |
  | `TOOL_RUNS` | Provenance for each check: tool, version, exit code, duration, `passed`/`failed`/`skipped` |
  | `FINDINGS` | Normalized findings: fingerprint, rule, severity, file/line, redacted evidence (`CLOB` JSON), remediation |
  | `DEPENDENCIES` | Dependency inventory (SBOM-style) per project |
  | `KNOWLEDGE_DOCS` | Source policy documents and version |
  | `POLICY_VECTORS` | Policy chunks with `VECTOR(384, FLOAT32)` embeddings, managed by `langchain-db2` |
  | `ASSESSMENT_DIFFS` | Regression results between two assessments |
  | `V_RISK_TREND` (view) | Risk score per run plus `LAG()` delta and `ROW_NUMBER()` recency rank |

  Foreign keys use `ON DELETE CASCADE`. Five secondary indexes cover project/time, severity and fingerprint lookups.
- **Key queries & operations:**
  - `MERGE INTO PROJECTS ... USING (VALUES (...))` to upsert projects.
  - Batched parameterized `INSERT`s for assessments, tool runs and findings; every value is bound through `?` markers.
  - `VECTOR_DISTANCE(EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE)` to rank policy chunks inside Db2.
  - `LAG(...) OVER (PARTITION BY PROJECT_ID ORDER BY STARTED_AT)` for the risk trend, and `GROUP BY CATEGORY, SEVERITY` with `COUNT(DISTINCT FINGERPRINT)` for analytics.
  - Idempotent DDL using `SYSCAT.TABLES` / `SYSCAT.INDEXES` checks; `doctor` reads `SYSIBMADM.ENV_INST_INFO` to report the real server level.

## AI / LLM Architecture
- **Framework:** **LangChain**. `MarkdownHeaderTextSplitter` and `RecursiveCharacterTextSplitter` chunk the policies, and `langchain_db2.DB2VS` is the vector store.
- **Embeddings:** an offline, deterministic feature-hashing embedder (`HashingEmbeddings`, a LangChain `Embeddings` implementation over word unigrams, bigrams and character trigrams, 384 dimensions, L2-normalized). It needs no model download and gives reproducible results. Set `SHIPSAFE_EMBEDDINGS=huggingface` to use `sentence-transformers/all-MiniLM-L6-v2` instead.
- **Retrieval workflow:** for every finding, the title and description become a query → Db2 returns the nearest policy chunk by cosine distance → the policy ID, version, section and verbatim text are attached to the finding and written into the report.
- **Design rule: evidence before AI.** Findings come only from deterministic scanners. Retrieval adds context and citations but never creates findings or changes the gate decision.

## Tech Stack
- **Core:** Python 3.10+ (tested on 3.14), standard-library CLI (`argparse`), JSON-RPC 2.0 MCP server over stdio
- **Database:** IBM Db2 Community Edition 12.1.5 (`ibm_db`, `ibm_db_dbi`)
- **AI / retrieval:** LangChain (`langchain-core`, `langchain-community`, `langchain-text-splitters`), `langchain-db2`
- **Tooling:** Docker / Docker Compose, `unittest`; optionally uses `git` when present

## Prerequisites
- Docker Desktop (for Db2 Community Edition), or access to a Db2 12.1.2+ instance
- Python **3.10+** and `pip`
- About 8 GB free disk for the Db2 image

## Setup & Installation

```bash
# 1. Go to the submission folder
cd submissions/shipsafe-ai

# 2. Configure credentials
cp .env.example .env          # then set DB2_PASSWORD

# 3. Start IBM Db2 Community Edition (first start takes ~5-10 minutes)
docker compose --env-file .env up -d
docker compose logs -f db2    # wait for "Setup has completed"

# 4. Install ShipSafe AI
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e .              # or: pip install -r requirements.txt
```

## Configuration
All settings are environment variables (read from `.env` in the working directory). See [`.env.example`](.env.example).

| Variable | Default | Meaning |
|---|---|---|
| `DB2_HOST` / `DB2_PORT` / `DB2_DATABASE` | `localhost` / `50000` / `SAMPLE` | Db2 location |
| `DB2_USERNAME` / `DB2_PASSWORD` | `db2inst1` / *(required)* | Credentials. Never hardcoded |
| `DB2_SECURITY` | `NONE` | `SSL` for Db2 on Cloud |
| `DB2_SCHEMA` | `SHIPSAFE` | Schema for all ShipSafe objects |
| `SHIPSAFE_DB_BACKEND` | `db2` | `sqlite` is used only by the offline unit tests |
| `SHIPSAFE_EMBEDDINGS` | `hashing` | `huggingface` for sentence-transformers |

> **Security:** never commit `.env`, real keys or passwords. The secret scanner in this project flags them too.

## Running the Project

```bash
shipsafe doctor                                         # Db2 version, schema, vector store status
shipsafe ingest                                         # (re)load policies/*.md into the Db2 vector store
shipsafe scan --target fixtures/vulnerable_project      # -> BLOCKED, exit code 1
shipsafe scan --target fixtures/clean_project           # -> PASS_WITH_WARNINGS (no IaC check applicable)
shipsafe scan --target . --output report.md             # Markdown report (or --format json)
shipsafe history                                        # risk trend from Db2 view V_RISK_TREND
shipsafe assessment compare <previous_id> <current_id>  # regression diff, stored in ASSESSMENT_DIFFS
shipsafe knowledge query "how should I store the Db2 password?"
```
Without installing, use `PYTHONPATH=src python -m shipsafe.cli <command>`.

**Example: vulnerable fixture (real output from Db2 12.1.5):**
```text
Release gate : BLOCKED
Findings: 6  (critical 4, high 1, medium 1, low 0)
  1. [CRITICAL] AWS Access Key ID Detected  (src/api.py:7)
     policy: POL-SEC-002: Secret and Credential Management Standard
  2. [CRITICAL] Potential SQL Injection / Unparameterized Query  (src/api.py:12)
     policy: POL-DB2-001: IBM Db2 Parameterized SQL and Injection Defense
  3. [HIGH    ] Subprocess Executed with shell=True  (src/api.py:19)
     policy: POL-SEC-004: Safe Process Execution and Dynamic Code Policy
  4. [CRITICAL] Vulnerable Dependency: pyyaml==5.3.1 (CVE-2020-14343)  (requirements.txt:1)
     policy: POL-DEP-003: Third-Party Dependency and Known Vulnerability Policy
  5. [MEDIUM  ] Vulnerable Dependency: requests==2.25.1 (CVE-2023-32681)  (requirements.txt:2)
     policy: POL-DEP-003: Third-Party Dependency and Known Vulnerability Policy
  6. [CRITICAL] Test Suite Regression: 1 Failed Test(s)  (tests:1)
     policy: POL-TST-005: Automated Test and Code Quality Gate
Persisted to IBM Db2: PROJECTS, ASSESSMENTS, TOOL_RUNS, FINDINGS, DEPENDENCIES
```

### MCP server (IBM Bob or any MCP client)
```json
{
  "mcpServers": {
    "shipsafe": {
      "command": "python",
      "args": ["-m", "shipsafe.mcp_server"],
      "cwd": "<path-to>/submissions/shipsafe-ai",
      "env": { "PYTHONPATH": "src", "DB2_PASSWORD": "<from your secret store>" }
    }
  }
}
```
Tools: `shipsafe_discover_project`, `shipsafe_run_assessment`, `shipsafe_get_assessment`, `shipsafe_get_finding`, `shipsafe_retrieve_guidance`, `shipsafe_compare_assessments`, `shipsafe_export_report`.

## Testing & Verification
```bash
# Offline unit tests (no database needed): 17 tests
PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py"

# Plus live IBM Db2 integration tests: 21 tests total
SHIPSAFE_DB2_INTEGRATION=1 PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py"
```
The integration tests check that `doctor` reports a real Db2 engine, that vector search returns `POL-DB2-001` for an SQL-injection question, that the vulnerable fixture is `BLOCKED` and its findings can be read back from Db2, and that the clean fixture is not blocked.

**Verify Db2 directly:**
```sql
SET SCHEMA SHIPSAFE;
SELECT ASSESSMENT_ID, STATUS, CRITICAL_COUNT, HIGH_COUNT FROM ASSESSMENTS ORDER BY STARTED_AT DESC FETCH FIRST 5 ROWS ONLY;
SELECT RULE_ID, SEVERITY, FILE_PATH, LINE_START FROM FINDINGS WHERE ASSESSMENT_ID = '<id>';
SELECT PROJECT_NAME, STATUS, RISK_SCORE, RISK_DELTA FROM V_RISK_TREND;
SELECT COUNT(*) FROM POLICY_VECTORS;
```

## Screenshots & Demo
- **Demo video:** linked in the pull request description
- **Sample report:** [`docs/sample-report.md`](docs/sample-report.md), generated from a real run on the vulnerable fixture
- Terminal screenshots: [`docs/screenshots/`](docs/screenshots/)

## Known Limitations & Future Roadmap
- **Limitations:**
  - The built-in rules target Python. Other languages are discovered but only scanned for secrets.
  - The CVE list is a small curated advisory set, not a full vulnerability feed. When `gitleaks` is installed it replaces the built-in secret rules; Bandit, Ruff and pip-audit are detected but not yet called.
  - Hashing embeddings match on shared vocabulary rather than deep meaning. They are the offline default; the Hugging Face option gives better recall.
  - Container and IaC checks (Trivy) are reported as *skipped*, never as passed.
- **Next steps:** run Bandit, pip-audit and Semgrep when installed and map their JSON into the finding contract; use an optional IBM Granite model (watsonx.ai or Ollama) to draft fix suggestions without changing the gate; add a GitHub Action that posts the report on the PR; build a Db2-backed dashboard over `V_RISK_TREND`.

## Team Members & Credits
| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Devanshu Sharma | [@ddevSharma](https://github.com/ddevSharma) | Design, scanners, IBM Db2 schema and persistence, LangChain/Db2 vector retrieval, MCP server, docs |

**Credits:** IBM Db2 Community Edition, [`langchain-db2`](https://pypi.org/project/langchain-db2/), LangChain. Rule IDs follow Bandit naming for familiarity. Licensed under [Apache-2.0](LICENSE).
