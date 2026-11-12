# 🔒 Db2 Privacy Copilot

> A DPDP decision-support system for IBM Db2 — discover and classify personal data, manage consent, and plan rights requests with deterministic safety guardrails.

[![CI](https://github.com/dreameterftw/db2-privacy-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/dreameterftw/db2-privacy-copilot/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![IBM Db2](https://img.shields.io/badge/IBM-Db2-blue.svg)](https://www.ibm.com/db2)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What It Does

Db2 Privacy Copilot supports privacy operations teams as they review data and prepare rights-request workflows:

| Capability | Description |
|---|---|
| **🔍 Discovery** | Auto-maps schema, FK relationships, and safe deletion order |
| **🏷️ Classification** | Detects PII (email, phone, PAN, Aadhaar, health data) using AI + regex |
| **✅ Consent Ledger** | Bitemporal tracking — "what was valid when, as we knew it" |
| **🗑️ Rights Requests** | AI-planned, human-approved, guardrail-validated erasure/anonymisation |
| **📝 Audit Trail** | SHA256 hash-chained log — any tampering is detected |
| **🛡️ Guardrail** | Deterministic SQL validator — blocks injection, DDL, missing WHERE clauses |

## Project summary

**Problem:** Privacy teams can struggle to locate personal data across related
database tables and coordinate consent, erasure, and audit work. Manual reviews
are time-consuming and can miss relationships or leave an unclear record of
decisions.

**Proposed solution:** Db2 Privacy Copilot brings schema discovery, PII
classification, consent history, rights-request planning, SQL safety checks,
and audit verification into one Db2-focused decision-support application.
Sensitive actions remain subject to human review and deterministic guardrails.

**Intended beneficiaries:** Data protection officers, privacy operations
teams, database administrators, and developers building or evaluating privacy
workflows for IBM Db2. The included clinic dataset is synthetic and intended
for demos and testing.

**What is built and how Db2 is used:** A Python application with a Streamlit
workspace and FastAPI endpoints. IBM Db2 stores the clinic sample schema,
application records, bitemporal consent history, audit events, and vector
representations used for semantic PII-label lookup. The application reads Db2
catalog metadata to discover tables and relationships. A local sentence
transformer creates embeddings; Db2's vector search compares them with stored
taxonomy vectors. CrewAI planning tools can propose workflows, while separate
deterministic checks control execution.

For a short presentation, see the [pitch deck](pitch/Db2_Privacy_Copilot_Pitch_Aryan_Rane.pptx)
and its [walkthrough guide](DEMO_GUIDE.md).

---

## Architecture

```
┌───────────────────────────────────────────────────────────┐
│               Streamlit UI  /  FastAPI REST                │
└────────────────────────┬──────────────────────────────────┘
                         │
┌────────────────────────▼──────────────────────────────────┐
│            CrewAI Agents (PROPOSE ONLY — never execute)    │
│   DiscoveryAgent  │  ClassificationAgent  │  RightsAgent   │
└────────────────────────┬──────────────────────────────────┘
                         │
┌────────────────────────▼──────────────────────────────────┐
│              Core Modules (Python)                         │
│  discovery  │  classify  │  consent  │  erasure  │  audit  │
└────────────────────────┬──────────────────────────────────┘
                         │
┌────────────────────────▼──────────────────────────────────┐
│           Security Guardrail (deterministic code)          │
│      SQL shape check │ banned tokens │ approval gate       │
└────────────────────────┬──────────────────────────────────┘
                         │
┌────────────────────────▼──────────────────────────────────┐
│                    IBM Db2 (Docker)                        │
│   Clinic schema │ PII_MAP │ CONSENT │ REQUESTS │ AUDIT_LOG │
└───────────────────────────────────────────────────────────┘
```

**Key safety principle**: Agents can only **propose** — execution requires human approval, then passes through the deterministic guardrail.

The Db2 connection is implemented with `ibm_db`/`ibm_db_dbi` in `app/db.py`.
Schema discovery and classification query the live Db2 catalog and sample
columns, while consent, erasure plans, audit records, and the PII taxonomy
vectors persist to Db2. Live name-based classification uses LangChain's
`langchain-db2` `DB2VS` vector store with local sentence-transformer embeddings.
This requires Db2 12.1.2 or newer. Mock mode uses keyword heuristics instead
and is intended for development/tests only; it is not a Db2 integration.
CrewAI is wired to read-only/planning tools in `app/agents.py`; the agents do
not execute destructive SQL.

**Scope and limitations:** This project is decision-support software for DPDP
use cases, not a complete GDPR implementation or legal advice. Seeded retention
rules are marked unverified (`VERIFIED='N'`) and must be reviewed by qualified
owners before production use. Mock mode uses in-memory sample data and does not
connect to or modify Db2.

---

## Local setup with real Db2 (recommended on Windows)

The supported Windows route uses Docker Desktop for the Db2, API, and Streamlit
containers. You do **not** need to install Ubuntu or manage a separate Linux
computer; Docker Desktop runs the Linux containers in its managed environment.
Use Docker Desktop with its Linux-container/WSL 2 backend, Docker Compose v2,
and Python 3.11+ only if you also want to run the tests on the host. The first
image build downloads large machine-learning dependencies and can take several
minutes and multiple gigabytes of disk space.

1. Install and start Docker Desktop. Confirm `docker version` and
   `docker compose version` work in PowerShell.
2. Clone the repository and create your local environment file:

   ```powershell
   git clone https://github.com/dreameterftw/db2-privacy-copilot.git
   cd db2-privacy-copilot
   Copy-Item .env.example .env
   notepad .env
   ```

3. In `.env`, set a unique `DB2_PASSWORD`, a long random `API_SECRET_KEY`, and
   distinct random values for `VIEWER_TOKEN`, `ANALYST_TOKEN`, and `DPO_TOKEN`.
   Keep `.env` private; it is ignored by Git. `DB2_HOST` is set to `db2` inside
   the containers by Compose. Do not change it to `localhost` for this setup.
   `API_PORT_HOST` defaults to `8001`; set it to another free port if needed.
4. Build and start Db2, the API, and the UI:

   ```powershell
   docker compose --profile app up -d
   docker compose ps
   docker compose logs -f db2
   ```

   The first Db2 startup can take several minutes. Wait until the `db2`
   service is healthy and its setup has completed. The API and UI share the
   Compose network with Db2; the UI does not connect through the Windows host.
5. Create the application tables and synthetic sample data once:

   ```powershell
   docker compose exec api python -m app.bootstrap
   docker compose exec api python -m eval.seed
   ```

6. Open the UI at [http://localhost:8501](http://localhost:8501). The API
   documentation is at [http://localhost:8001/docs](http://localhost:8001/docs)
   and its Db2 health check is [http://localhost:8001/healthz](http://localhost:8001/healthz).
   If port 8001 is occupied, set `API_PORT_HOST` in `.env` to another free
   host port and recreate the services with `docker compose --profile app up -d`.

The Compose `app` profile deliberately turns on the API and UI together with
Db2. `docker compose up -d` without `--profile app` starts only Db2. On a fresh
clone Compose builds the missing application images. After changing source
code, rebuild them with `docker compose --profile app up -d --build`.

### Stop and reset the local application

Stop containers while preserving the Db2 data volume:

```powershell
docker compose --profile app down
```

To permanently remove the local database contents too, use
`docker compose --profile app down -v` only when you intend to delete the local
database. Seed data is synthetic; never use it to represent real people.

### Optional host Python setup

For tests and development, install the project on the host with Python 3.11+:

```powershell
.\setup.bat
.\.venv\Scripts\Activate.ps1
pytest -q
```

On macOS/Linux, use `bash setup.sh`. Running the UI or API directly on Windows
may not connect to Db2 reliably because the IBM Db2 native driver can have
platform-specific authentication issues. Use the Compose containers for the
real Db2 integration; host `DB_MOCK=1` mode is only a mock development mode.

For a detailed walkthrough see [QUICKSTART.md](QUICKSTART.md). For the
separate public HTTPS demo deployment, CI/CD, and rollback guidance, see
[the deployment guide](deploy/README.md). Public deployment requires a VM,
domain, verified SSH access, and GitHub deployment secrets; it is not created
by the local setup above.

---

## Project Structure

```
db2-privacy-copilot/
├── app/
│   ├── agents.py       # CrewAI agent definitions + tool wrappers
│   ├── api.py          # FastAPI REST backend
│   ├── audit.py        # SHA256 hash-chained audit log
│   ├── bootstrap.py    # Database initialization
│   ├── classify.py     # PII classification engine
│   ├── config.py       # Settings (pydantic-settings)
│   ├── consent.py      # Bitemporal consent ledger
│   ├── db.py           # Db2 connection & query utilities
│   ├── discovery.py    # Schema catalog scanner + FK graph
│   ├── erasure.py      # Dry-run planner + executor
│   └── guardrail.py    # Deterministic SQL validator
├── ui/
│   ├── app.py            # Streamlit landing page
│   ├── pages/            # Dashboard and privacy workflow pages
│   └── Dockerfile        # Streamlit container image
├── eval/
│   ├── seed.py         # Synthetic clinic data generator
│   └── run_eval.py     # Classification evaluation harness
├── sql/
│   ├── 00_schema_clinic.sql    # 7-table clinic schema
│   ├── 01_app_tables.sql       # PII_MAP, REQUESTS, AUDIT_LOG …
│   ├── 02_consent_temporal.sql # Bitemporal CONSENT table
│   └── 03_rcac_examples.sql    # Row & Column Access Control
├── tests/              # Unit and Db2 integration tests
├── docs/
│   ├── architecture.md
│   └── demo_script.md
├── docker-compose.yml    # Local Db2, API, and UI services
├── pyproject.toml
└── QUICKSTART.md
```

---

## Implementation Status

| Phase | Description | Status |
|---|---|---|
| 0 | Environment, Docker, synthetic data | ✅ Complete |
| 1 | Schema discovery (FK graph, delete order) | ✅ Complete |
| 2 | PII classification (value rules + Db2VS semantic name search) | ✅ Complete |
| 3 | Bitemporal consent ledger | ✅ Complete |
| 4 | Rights requests, guardrail, audit chain | ✅ Complete |
| 5 | CrewAI agents, FastAPI, Streamlit UI | ✅ Complete |
| 6 | Evaluation, hardening, polish | 📋 In progress |
| 7 | RAG over DPDP Act, RCAC proposals | 📋 Stretch goal |

---

## Security Design

### What the guardrail blocks
- `DROP`, `TRUNCATE`, `ALTER`, `GRANT`, `REVOKE`, `CREATE`
- Stacked statements (`;` separator)
- SQL comments (`--`, `/* */`)
- Missing `WHERE` clause
- Non-parameterized values (no `?` placeholder)
- Tables not in the approved plan
- Always-true conditions (`1=1`, `'a'='a'`)

### Approval workflow
```
Agent generates plan → DPO reviews → DPO approves (signs with ID)
  → Guardrail validates each statement
    → Executor runs single transaction
      → Rollback on any error
        → Audit record appended to chain
```

### Audit chain
Every record contains `hash(prev_hash + content)`. Changing any record invalidates all subsequent hashes — tamper-evident by design.

### Dependency audit exceptions
CrewAI currently requires ChromaDB, although application code does not directly
use it and neither Compose stack starts or exposes a ChromaDB service. The
dependency audit accepts only the four documented ChromaDB advisories in
[the exception policy](security/audit-exceptions.toml). The exception is owned
by `aryan` and expires on **2026-12-10**; the audit fails after that date or for
any other finding. Container scans use the matching CVE IDs in
[`.trivyignore`](.trivyignore) and fail on all other CRITICAL/HIGH findings.
CODEOWNERS requests review from the repository owner for the policy, tests, and
scanner workflows; enable required Code Owner approvals in branch protection to
enforce that review.

---

## API Overview

```bash
# Auth header: Authorization: Bearer <role token from .env>
# Configure VIEWER_TOKEN, ANALYST_TOKEN, and DPO_TOKEN in .env.

GET  /health                      # Component health check
GET  /discovery/{schema}          # Scan schema (VIEWER+)
GET  /classification/{schema}     # Run PII classification (ANALYST+)
POST /consent/grant               # Grant consent (ANALYST+)
POST /consent/withdraw            # Withdraw consent (ANALYST+)
GET  /consent/{patient_id}        # View consents (VIEWER+)
POST /requests                    # Create erasure request (ANALYST+)
GET  /requests                    # List requests (VIEWER+)
GET  /requests/{id}               # Get request detail (VIEWER+)
POST /requests/{id}/approve       # Approve & execute (DPO only)
GET  /audit                       # Audit log (VIEWER+)
GET  /audit/verify                # Verify chain (DPO only)
GET  /audit/subject/{id}          # Subject audit trail (VIEWER+)
```

Interactive docs: `http://localhost:8001/docs` with the local Compose setup.

---

## Running Tests

```bash
# All tests
pytest -v

# Specific modules
pytest tests/test_guardrail.py -v
pytest tests/test_audit.py -v
pytest tests/test_erasure.py -v
pytest tests/test_classify.py -v
pytest tests/test_consent.py -v

# With coverage
pytest --cov=app --cov-report=html
```

---

## Configuration

All settings live in `.env` (see [.env.example](.env.example)):

```env
DB2_HOST=localhost
DB2_PORT=50000
DB2_DB=clinic
DB2_USER=db2inst1
DB2_PASSWORD=replace-with-a-strong-password
DB2_SCHEMA=DB2INST1

API_SECRET_KEY=change-this-in-production
PII_VALUE_THRESHOLD=0.30
PII_NAME_THRESHOLD=0.35
DEFAULT_REQUEST_DEADLINE_DAYS=30
```

---

## Development

```bash
# Install with dev extras
pip install -e ".[dev,ui]"

# Lint
ruff check app/ tests/

# Type check
mypy app/

# Security scan
bandit -r app/

# Pre-commit hooks
pre-commit install
```

---

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Run tests (`pytest -v`)
4. Run lint (`ruff check .`)
5. Submit a pull request

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

## Acknowledgements

- [IBM Db2](https://www.ibm.com/db2) — database engine with temporal table support
- [CrewAI](https://crewai.com) — multi-agent orchestration
- [LangChain Db2](https://pypi.org/project/langchain-db2/) — Db2VS vector storage and semantic name search
- [FastAPI](https://fastapi.tiangolo.com) — REST API framework
- [Streamlit](https://streamlit.io) — rapid UI development
- [NetworkX](https://networkx.org) — FK graph analysis
- India's [DPDP Act 2023](https://www.meity.gov.in/data-protection-framework) — compliance target
