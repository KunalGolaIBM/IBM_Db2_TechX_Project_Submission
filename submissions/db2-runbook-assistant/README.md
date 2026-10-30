# Db2 Runbook Assistant

> **One-Line Pitch:** A RAG assistant that answers IT support questions from internal runbooks, using IBM Db2 as the vector store, Haystack for the pipeline, and IBM Granite models running locally through Ollama.

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
- IT support engineers lose time searching through long runbooks when an incident happens (for example S3 access errors, disk usage alerts, crash loops, expired TLS certificates).
- The target users are internal IT support and operations teams, and new engineers who do not know the runbooks yet.
- Keyword search misses answers when the wording of the question differs from the runbook text, and reading whole documents is slow during an incident.

---

## Solution Overview
- Runbooks (Markdown files in `src/data/runbooks`) are split, embedded and stored in IBM Db2 as vectors.
- When a user asks a question, Db2 vector search finds the most relevant runbook content.
- A local Granite language model writes a short, grounded answer from that content.
- Core features: semantic search over runbooks, grounded answers from the retrieved text, fully local models, no cloud account needed.

---

## IBM Db2 Integration
- **Db2 Edition & Environment:** Db2 Community Edition 12.1.2.0 in Docker (`icr.io/db2_community/db2:12.1.2.0`). This version supports the native `VECTOR` type.
- **Connector / Driver Used:** `ibm-db-haystack`, the official IBM Db2 integration for Haystack (`IBMDb2DocumentStore`).
- **Database Schema / Data Models:** database `RUNBOOKS`; one document-store table holding the runbook text, its metadata and the embedding vector.
- **Key Queries & Operations:** documents and embeddings are written with `write_documents`; questions are answered with vector similarity search (cosine distance) through `IBMDb2EmbeddingRetriever`.

---

## AI / LLM Architecture
- **Framework:** Haystack.
- **Model Provider & Model:** Ollama running locally. Embeddings: `granite-embedding:278m`. Answers: `granite3.3:8b`.
- **RAG Workflow:** the question is embedded, Db2 returns the closest runbook chunks, and those chunks are placed into a prompt for the Granite model, which writes the answer.

---

## Tech Stack
- **Backend / Core:** Python 3
- **Database:** IBM Db2 Community Edition (Docker)
- **Frontend / UI:** Command line (`ask.py`)
- **Libraries & Tools:** Haystack, ibm-db-haystack, Ollama, Docker, Docker Compose

---

## Prerequisites
- Docker (Docker Desktop with WSL 2 on Windows)
- Python 3.11 or newer
- Ollama
- About 10 GB free disk space (Db2 image about 2.5 GB, Granite 8B model about 5 GB)

---

## Setup & Installation

```bash
# 1. Go to the project folder
cd submissions/db2-runbook-assistant

# 2. Create your settings file and set your own password
cp .env.example .env
# open .env and replace your_password_here with a password you choose

# 3. Start Db2 (first start takes 5-10 minutes)
cd src
docker compose --env-file ../.env up -d

# 4. Install Python dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 5. Download the models
ollama pull granite-embedding:278m
ollama pull granite3.3:8b
```

---

## Configuration

Copy `.env.example` to `.env` and set your own password:

```bash
cp .env.example .env
```

| Variable | Meaning |
|---|---|
| `DB2_HOST`, `DB2_PORT` | Db2 address (default `localhost`, `50000`) |
| `DB2_DATABASE` | Database name (`RUNBOOKS`) |
| `DB2_USERNAME`, `DB2_PASSWORD` | Db2 login. Use the same password for the Docker container and the app |
| `OLLAMA_URL` | Ollama address (default `http://localhost:11434`) |
| `EMBED_MODEL`, `LLM_MODEL` | Ollama model names |

> **Security Warning:** Never commit `.env` or any real password to Git. Only `.env.example` with placeholder values is committed.

---

## Running the Project

From the `src` folder, with the virtual environment active:

```bash
set -a; source ../.env; set +a   # load settings into the terminal
python manage.py                 # prepare the database table
python ingest.py                 # read data/runbooks, create embeddings, store them in Db2
python ask.py                    # ask questions
```

---

## Testing & Verification
1. After `ingest.py`, open the Db2 table (for example with the IBM Db2 Developer Extension in VS Code). It should contain one row per runbook chunk.
2. Run `python ask.py` and ask: `S3 sync gives AccessDenied in prod, what should I do?`. The answer should follow runbook RB-001.
3. Ask a question that is not covered by the runbooks. The assistant should say it cannot find the answer.

---

## Screenshots & Demo
- **Live Demo Link:** not hosted (runs locally)
- **Demo Video Link:** not provided
- Screenshots:

  ![Db2 table after ingest](docs/screenshots/ingest.png)
  ![ask.py answering a question](docs/screenshots/ask.png)

---

## Known Limitations & Future Roadmap
- **Current Limitations:** command-line interface only; runs on a small set of sample runbooks; answer speed depends on the laptop, because the 8B model runs locally.
- **Next Steps:** a web interface, more runbooks, and showing the source runbook next to each answer.

---

## Team Members & Credits
| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Kashish Rajawat | [@KashishRajawat](https://github.com/KashishRajawat) | Backend & Db2 Integration |

Built with Haystack, IBM Db2, IBM Granite models and Ollama.
