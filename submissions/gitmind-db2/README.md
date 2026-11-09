# GitMind

**One-Line Pitch:** GitMind transforms software repositories into a persistent, searchable, and auditable engineering intelligence system powered by IBM Db2, combining a repository knowledge graph, native vector retrieval, multi-agent collaboration, and historical change-risk intelligence to prevent software regressions.

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

### The Problem
Engineering teams suffer from acute institutional amnesia:
- **Lost Context & Intent:** Codebases preserve *what* was written, but obscure *why*. Commit messages are frequently cryptic (`fix bug`, `updates`, `refactoring`), pull requests are scattered across external portals, and original authors leave organizations taking unwritten context with them.
- **Repeated Software Regressions:** Developers inadvertently re-introduce flaws, regressions, and broken patterns that were already investigated, debugged, or reverted months or years earlier.
- **Fragmented Engineering Tooling:** Git histories, Tree-sitter Abstract Syntax Tree (AST) structures, GitHub PR discussions, issues, and security reviews exist in disparate, disconnected silos.
- **Flaws of Generic RAG & Coding Assistants:** Conventional RAG chatbots treat code as flat text strings. They hallucinate commit SHAs, lack repository knowledge graphs, have no repository-scoped multi-tenant boundaries, and lack persistent memory of engineering investigations across sessions.

### Target Audience
- **Software Engineers & Technical Leads:** Rapidly comprehend complex legacy codebases, understand why changes occurred, and prevent regressions during code review.
- **Engineering Managers & Architects:** Audit repository health, trace architectural evolutions, and preserve institutional knowledge across team turnovers.
- **DevOps & QA Engineers:** Automate pre-merge risk scoring, detect vulnerable patterns, and generate safe reflog recovery plans.

### Why Existing Tooling Is Insufficient
Traditional Git tools (`git log`, `git blame`) are purely local and syntax-blind. They cannot link a commit to a modified AST symbol, a resolved GitHub issue, or an active architectural finding. Standard coding assistants lack database persistence; their context resets on every prompt, rendering them unable to learn from past engineering failures or enforce organizational memory.

---

## Solution Overview

GitMind solves these challenges by turning repository history and code structures into an enterprise-grade, persistent knowledge network inside **IBM Db2**.

### Core Capabilities:
1. **Repository Knowledge Graph in IBM Db2 (`GITMIND_RELATIONS`):**  
   Automatically maps commits, parent relationships, touched files, Tree-sitter AST symbols (functions and classes), GitHub PRs, and issues into an auditable relational graph with foreign keys and cascade deletion.
2. **Persistent Multi-Agent Engineering Memory (`GITMIND_FINDINGS`):**  
   Seven specialist agents collaborate on queries. High-value discoveries (e.g. regression risks, architectural patterns) are persisted in Db2 along with their supporting evidence, allowing future CLI sessions to immediately recall precedents.
3. **Historical Change-Risk & Regression Intelligence (`gitmind review`):**  
   GitMind's signature differentiator. It inspects a developer's working tree diff against a base branch, detects changed AST functions, searches IBM Db2 for past reverts, bug fixes, and prior unresolved findings, and computes an explainable, deterministic risk score with actionable merge recommendations.
4. **Evidence Verification Layer:**  
   Every AI-generated response passes through a verification layer that cross-checks candidate commit hashes and file paths against actual Db2 records, classifying statements into *Verified Facts* versus *Historical Inferences* to eliminate hallucinations.
5. **Non-Destructive Safety Guardrails:**  
   Enforces read-only safety guardrails that block destructive Git operations (`git reset --hard`, `git push --force`, `git branch -D`) without explicit developer confirmation.

---

## IBM Db2 Integration

IBM Db2 is the primary operational database and intelligence engine powering GitMind:

```
Developer CLI / PR
        │
        ▼
LangGraph Supervisor & Query Router
        │
┌───────┴───────────────────────────────────────────────────────┐
│ Seven Specialist Agents (History, Code, Recovery, PR, etc.)   │
└───────┬───────────────────────────────────────────────────────┘
        │
        ▼
Evidence Verification Layer (Cross-checks Db2 Records)
        │
        ▼
Shared Repository Intelligence Interface
        ├── Relational Knowledge Graph (ibm_db_dbi)
        ├── Native Db2 Vector Store (langchain-db2 DB2VS)
        ├── Persistent Agent Memory (GITMIND_FINDINGS)
        └── Append-Only Audit Trail (GITMIND_AUDIT_EVENTS)
        │
        ▼
IBM Db2 Database (v12.1.2+ / v12.1.5 Native Vector Engine)
        ├── GITMIND_REPOSITORIES      (Repo metadata & indexing state)
        ├── GITMIND_ARTIFACTS         (Commits, files, AST symbols, PRs, docs)
        ├── GITMIND_RELATIONS         (Knowledge Graph relational edges)
        ├── GITMIND_VECTORS           (Native VECTOR(768, FLOAT32) + DB2VS)
        ├── GITMIND_INDEX_RUNS        (Incremental indexing run tracking)
        ├── GITMIND_AGENT_RUNS        (Multi-agent execution tracking)
        ├── GITMIND_FINDINGS          (Persistent institutional memory)
        ├── GITMIND_FINDING_EVIDENCE  (Grounded evidence references)
        └── GITMIND_AUDIT_EVENTS      (Append-only governance trail)
```

### 1. Db2 Edition & Environment
- **Tested & Certified On:** IBM Db2 v12.1.5 (`12.01.0500`) Community Edition on Docker and Db2 on IBM Cloud (`BLUDB`).
- **Compatibility:** Requires IBM Db2 v12.1.2+ for native vector support.
- **Vector Engine:** Leverages Db2's native `VECTOR(dim, FLOAT32)` data type and server-side `VECTOR_DISTANCE` execution with `COSINE` distance strategy.

### 2. Connector & Driver Used
- **Primary Driver:** Official `ibm_db` (v3.3.0) and `ibm_db_dbi` native Python C-extension drivers.
- **Vector Integration:** Official `langchain-db2` (v1.0.0+) package utilizing `from langchain_db2 import DB2VS`.
- **Connection Management:** `Db2ConnectionManager` featuring bounded retries with exponential backoff, transaction management, connection pooling, SSL/TLS validation, and credential redaction.

### 3. Database Schema & Data Models
GitMind defines 9 relational and vector tables in the `GITMIND` schema:
- `GITMIND_REPOSITORIES`: Stores repository metadata, default branch, latest indexed commit SHA, and schema version.
- `GITMIND_ARTIFACTS`: Stores commits, diffs, source files, AST functions/classes, GitHub PRs, and documentation sections with SHA-256 content hashes.
- `GITMIND_RELATIONS`: Relational graph table with foreign keys (`COMMIT_PARENT`, `COMMIT_TOUCHES_FILE`, `COMMIT_MODIFIES_FUNCTION`, `PR_RESOLVES_ISSUE`).
- `GITMIND_VECTORS`: Official `DB2VS` table with columns `ID CHAR(16)`, `TEXT CLOB`, `METADATA BLOB`, and `EMBEDDING VECTOR(768, FLOAT32)`.
- `GITMIND_INDEX_RUNS`: Tracks incremental vs. full indexing executions, chunk counts, and status.
- `GITMIND_AGENT_RUNS`: Records user queries, invoked specialist agents, and latency metrics.
- `GITMIND_FINDINGS`: Stores agent-generated findings (architectural notes, regression alerts) across sessions.
- `GITMIND_FINDING_EVIDENCE`: Links findings to verified commit SHAs, file paths, and line ranges.
- `GITMIND_AUDIT_EVENTS`: Append-only compliance log recording indexing, queries, reviews, and recovery operations.

### 4. Key Queries & Operations
- **Vector Similarity Search:**
  ```sql
  SELECT id, text, SYSTOOLS.BSON2JSON(metadata),
         VECTOR_DISTANCE(embedding, VECTOR(?, 768, FLOAT32), COSINE) AS distance
  FROM GITMIND_VECTORS
  ORDER BY distance ASC
  FETCH FIRST ? ROWS ONLY;
  ```
- **Graph Traversal (Commits Modifying AST Function):**
  ```sql
  SELECT C.COMMIT_SHA, C.TITLE, C.AUTHOR, C.CREATED_AT
  FROM GITMIND_RELATIONS R
  JOIN GITMIND_ARTIFACTS C ON R.SOURCE_ARTIFACT_ID = C.ARTIFACT_ID
  JOIN GITMIND_ARTIFACTS F ON R.TARGET_ARTIFACT_ID = F.ARTIFACT_ID
  WHERE R.REPO_ID = ? AND R.RELATION_TYPE = 'COMMIT_MODIFIES_FUNCTION'
    AND F.SOURCE_KEY = ?
  ORDER BY C.CREATED_AT DESC;
  ```
- **Multi-Tenant Repository Isolation:**
  Every query and vector search applies strict `WHERE REPO_ID = ?` or metadata filtering, preventing cross-repository data leakage.

---

## AI / LLM Architecture

### 1. Framework
- **Orchestration:** Built on **LangGraph** functional workflows (`@entrypoint` and `@task`) and **LangChain Core**.
- **Agent Architecture:** Coordinated supervisor/router pattern with 7 specialist domain agents:
  1. **Router Agent:** Classifies user query intent and selects specialist agents.
  2. **History Agent:** Traces Git commits, authors, blame, and feature timelines.
  3. **Code Agent:** Tree-sitter AST analysis for functions, classes, and code structures.
  4. **GitHub Agent:** Maps human discussions across PRs, reviews, and issues via PyGithub.
  5. **Suggest Agent:** Audits unpushed commits, stale branches, and force-push hazards.
  6. **Recovery Agent:** Analyzes reflog and dangling commits to plan safe recovery steps.
  7. **Project Agent:** Synthesizes architecture, tech stacks, and onboarding documentation.
  8. **Synthesizer Agent:** Validates agent findings against Db2 evidence and compiles grounded responses.

### 2. Model Provider & Models
- **Google Gemini:** `gemini-3.1-flash-lite`, `gemini-flash-latest`, and `gemini-2.5-flash` with Google GenAI Embeddings (`models/gemini-embedding-001`, dimension: 768).
- **OpenAI:** `gpt-4o-mini` and `gpt-4o` with `text-embedding-3-small` (dimension: 1536).
- **Configurable Factory:** Provider is switched simply via `LLM_PROVIDER=gemini` or `LLM_PROVIDER=openai` in `.env`.

### 3. RAG / Tool Calling Workflow
- Agents retrieve grounded historical facts from IBM Db2 via parameterized tools (`semantic_search`, `get_commit_history`, `get_file_history`).
- Tool results are ingested into the LangGraph state.
- Before final response generation, the **Evidence Verification Layer** validates all cited commit SHAs, file names, and line ranges against IBM Db2 relational records.
- Synthesized responses partition facts into **Verified Facts**, **Historical Inferences**, and **Actionable Recommendations**.

---

## Tech Stack

- **Backend / Core:** Python 3.10, 3.11, 3.12, 3.13
- **Primary Database:** IBM Db2 (v12.1.2+ / v12.1.5 Native Vector Engine)
- **Database Connectors:** `langchain-db2` (v1.0.0+), `ibm_db` (v3.3.0+), `ibm_db_dbi`
- **Agent Framework:** LangGraph, LangChain Core
- **Code Intelligence:** Tree-sitter (Python, JavaScript, TypeScript grammar parsers)
- **Version Control Engine:** GitPython, PyGithub
- **CLI Interface:** Typer, Rich (formatted tables, ASCII banners, status indicators)
- **Quality & Linting:** Flake8 (zero errors on `E9,F63,F7,F82`)

---

## Prerequisites

Before setting up GitMind, ensure you have:
1. **Python:** Version `>= 3.10` (Python 3.10, 3.11, 3.12, or 3.13 supported).
2. **IBM Db2 Instance:**
   - Local Docker container running Db2 Community Edition (v12.1.2+):
     ```bash
     docker run -d --name db2 -p 50000:50000 -e DB2INSTANCE=db2inst1 -e DB2INST1_PASSWORD=GitMindDb2_StrongPassword123! -e DBNAME=GITMIND ibmcom/db2:12.1.5.0
     ```
   - Or an active IBM Cloud Db2 instance with SSL.
3. **Git:** Installed and available on your system `PATH`.
4. **API Key:** A Google Gemini API key or OpenAI API key.

---

## Setup & Installation

```bash
# 1. Clone repository and navigate to the submission directory
git clone https://github.com/vastavikadi/gitmind-va.git
cd gitmind

# 2. Create and activate a virtual environment
python -m venv .venv
# On Linux/macOS:
source .venv/bin/activate
# On Windows PowerShell:
.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your IBM Db2 credentials and API keys:

```bash
cp .env.example .env
```

### Environment Variables (`.env`):
```ini
# Storage Backend: db2 (primary production engine)
STORAGE_BACKEND=db2

# IBM Db2 Connection Parameters
DB2_DATABASE=GITMIND
DB2_HOST=localhost
DB2_PORT=50000
DB2_USERNAME=db2inst1
DB2_PASSWORD=GitMindDb2_StrongPassword123!
DB2_SSL=false
DB2_SSL_CERTIFICATE=

# Db2 Schema and Vector Table
DB2_SCHEMA=GITMIND
DB2_VECTOR_TABLE=GITMIND_VECTORS

# LLM & Embedding Settings
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-3.1-flash-lite

EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=models/gemini-embedding-001
EMBEDDING_DIMENSION=768

# GitHub Token (Optional: enables PR and issue intent tracing)
GITHUB_TOKEN=your_github_token_here
```

> **Security Warning:** Never commit `.env` or any real API keys or database passwords to Git! GitMind includes automated pre-flight redaction to prevent secret leakage.

---

## Running the Project

### 1. Run Db2 Diagnostics & Health Check
Verify live database connectivity, version compatibility, and native vector support:
```bash
python cli.py db2 doctor
```

### 2. Apply Relational Schema Migrations
Create all 9 GitMind knowledge graph, agent memory, and vector tables:
```bash
python cli.py db2 migrate
```

### 3. Check Db2 Storage Status
Inspect record counts across repositories, artifacts, knowledge graph relations, findings, and vector chunks:
```bash
python cli.py db2 status
```

### 4. Index a Repository
Extract commits, touched files, Tree-sitter AST symbols, and semantic embeddings into IBM Db2:
```bash
# Incremental indexing (default: last 30 days)
python cli.py index --days 30

# Full indexing of entire history
python cli.py index --full
```

### 5. Run Historical Change-Risk Review (Signature Differentiator)
Analyze current working changes or diffs against a base branch:
```bash
python cli.py review --base HEAD~1
```

### 6. Evidence-Grounded Repository Q&A
Ask natural language questions grounded in your repository history and IBM Db2 knowledge graph:
```bash
python cli.py ask "What is GitMind?"
```

### 7. Search Persistent Multi-Agent Memory
Query engineering findings, past investigations, and regression alerts stored in Db2:
```bash
python cli.py memory search "Change Risk"
```

### 8. Repository Storytelling & Recovery
```bash
# Generate narrative of recent evolution
python cli.py story --days 14

# Scan reflog for dangling commits and deleted branches
python cli.py recover
```

---

## Testing & Verification

GitMind includes a complete test suite covering unit logic, Db2 integration, cross-repo isolation, safety guardrails, and a 20-question Golden Evaluation Benchmark.

### 1. Run All Tests
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```
**Results:** `Ran 28 tests in 0.039s — OK (28/28 tests passing)`.

### 2. Verify Flake8 CI Compliance
```bash
python -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
# Returns 0 (Zero syntax errors or undefined names)
```

### 3. Golden Benchmark Evaluation Metrics
| Benchmark Metric | Target Threshold | GitMind Measured Score | Result |
|---|---|---|---|
| **Retrieval Hit@5** | >= 80.0% | **100.0%** (20/20) | **PASS** |
| **Mean Reciprocal Rank (MRR)** | >= 0.700 | **0.858** | **PASS** |
| **Factual Claim Grounding** | 100.0% | **100.0%** | **PASS** |
| **Cross-Repository Isolation Leakage** | 0.0% | **0.0% (Zero Leakage)** | **PASS** |
| **Secret Redaction Rate** | 100.0% | **100.0%** | **PASS** |

---

## Screenshots & Demo

- **Live Repository:** [https://github.com/vastavikadi/gitmind-va](https://github.com/vastavikadi/gitmind-va)
- **Demo Video:** ![GitMind demo](https://github.com/vastavikadi/GitMind/blob/main/assets/gitmind.gif?raw=true)

![Demo ScreenShot](../../docs/screenshots/image.png)

### CLI Interactive Outputs:

#### 1. Db2 Doctor Capability Verification
```text
                          IBM Db2 Diagnostics Report                           
┌────────────────────────────────┬──────────────────────┬─────────────────────┐
│ Diagnostic Check               │ Result               │ Details             │
├────────────────────────────────┼──────────────────────┼─────────────────────┤
│ Connection Status              │ SUCCESS              │ localhost:50000/GI… │
│ Db2 Server Version             │ 12.01.0500           │ Parsed: (12, 1, 5)  │
│ Native VECTOR Data Type        │ SUPPORTED (v12.1.2+) │ Native vector cols  │
│ Native ANN Vector Index        │ SUPPORTED (v12.1.5+) │ ANN indexing        │
│ VECTOR_DISTANCE Probe          │ VERIFIED ON SERVER   │ Test result: 1.0    │
│ Schema 'GITMIND'               │ EXISTS               │ Schema: GITMIND     │
│ Vector Table 'GITMIND_VECTORS' │ EXISTS               │ Official DB2VS table│
└────────────────────────────────┴──────────────────────┴─────────────────────┘
```

#### 2. Change-Risk & Regression Review (`gitmind review`)
```text
┌───────────────────── Change Risk Review (Base: HEAD~1) ─────────────────────┐
│                                                                             │
│               GITMIND CHANGE REVIEW — MEDIUM HISTORICAL RISK                │
│                                                                             │
│  Repository: vastavikadi/gitmind | Base: HEAD~1 -> Head: f49be67c |         │
│  Risk Score: 35.0/100                                                       │
│                                                                             │
│  Changed Components                                                         │
│   • .env.example                                                            │
│   • data/db2/migrations.py                                                  │
│   • workflows/router.py                                                     │
│   • Modified Functions/Classes: route_query, get_llm, synthesize            │
│                                                                             │
│  Detected Risk Signals (Deterministic Model)                                │
│   • Previous Engineering Finding Active (+20.0 pts): Prior finding affects  │
│     modified persistence layer.                                             │
│   • Missing Accompanying Tests (+15.0 pts): Core source code changed.       │
│                                                                             │
│  Grounded Historical Evidence (IBM Db2)                                     │
│   1 [VERIFIED] File .env.example — Previous GitMind finding recalled.       │
│   2 [INFERRED] Artifact test — Code changes detected without new tests.     │
│                                                                             │
│  Actionable Recommendations                                                 │
│   • Review historical finding before merging changes.                       │
│   • Add automated regression test cases covering modified code paths.       │
│                                                                             │
│  Review ID: 6AB63D7F-D988-4D | Backed by IBM Db2 Multi-Agent Memory         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Known Limitations & Future Roadmap

### Current Limitations:
- **GitHub Rate Limits:** Deep PR and issue intent tracing requires a GitHub token (`GITHUB_TOKEN`); without it, GitMind operates purely on local Git history and Tree-sitter AST analysis.
- **Binary Assets:** Large binary assets (images, compiled archives) are excluded from indexing by design to keep vector search noise-free.
- **Shallow Git Clones:** Repositories cloned with `--depth 1` have restricted commit histories for historical revert matching.

### Future Roadmap:
- **Automated PR Bot:** Run `gitmind review` directly in GitHub Actions on every pull request, posting risk scores as PR comments.

---

## Team Members & Credits

| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| **Aditya Shukla** | [@vastavikadi](https://github.com/vastavikadi) | Project Creator, Systems Architect, Db2 Persistence & Multi-Agent Lead |

---

*GitMind is licensed under the [MIT License](LICENSE). Built for the IBM Db2 TechX Build Challenge 2026.*