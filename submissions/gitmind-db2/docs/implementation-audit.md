# GitMind 2.0 — Implementation Audit (Phase Zero)

**Audit Date:** 2026-11-09  
**Auditor:** GitMind Senior Systems Architecture & Engineering Team  
**Scope:** Full codebase audit of `vastavikadi/gitmind` prior to IBM Db2 transformation

---

## 1. Executive Summary

A comprehensive source-code audit of the existing GitMind repository was conducted. The application is an AI-powered Git repository analysis and reasoning CLI built on top of:
- **Agent Orchestration:** LangGraph (using `@entrypoint` and `@task` functional workflow patterns) and LangChain Core.
- **LLM Integrations:** Google Gemini (`langchain-google-genai`) and OpenAI (`langchain-openai`).
- **Persistence & Retrieval:** SQLite (`data/database.py`) for repository metadata caching and ChromaDB (`embeddings/vector_store.py`) for semantic vector storage.
- **AST Code Analysis:** Tree-sitter for Python, JavaScript, and TypeScript (`tools/code_tools.py`).
- **Git Analysis:** GitPython (`tools/git_tools.py`, `tools/story/`).
- **GitHub Integration:** PyGithub (`github_integration/github_client.py`).
- **CLI Framework:** Typer + Rich (`cli.py`, `utils/output.py`, `utils/banner.py`).

---

## 2. Seven Agent Inventory

GitMind contains seven specialist agents defined under `agents/`:

| Agent | Entrypoint Module | System Prompt File | Key Tools | Primary Responsibility |
|---|---|---|---|---|
| **History Agent** | `agents/history/history_agent.py::history_agent` | `sys_prompt.yaml` | `HISTORY_TOOLS`, `EMBEDDING_TOOLS` | Commit history, blame, feature evolution, narrative generation. |
| **Code Agent** | `agents/code/code_agent.py::code_agent` | `sys_prompt.yaml` | `CODE_TOOLS`, `HISTORY_TOOLS` | AST function/class diffs, syntax tree exploration, code change dependencies. |
| **Recovery Agent** | `agents/recovery/recovery_agent.py::recovery_agent` | `sys_prompt.yaml` | `RECOVERY_TOOLS` | Reflog scanning, dangling object detection (`fsck`), lost commit/branch recovery plans. |
| **GitHub Agent** | `agents/github/github_agent.py::github_agent` | `sys_prompt.yaml` | `HISTORY_TOOLS`, `GITHUB_TOOLS` (conditional) | PRs, issues, code reviews, human intent linking. |
| **Suggest Agent** | `agents/suggest/suggest_agent.py::suggest_agent` | `sys_prompt.yaml` | `SUGGEST_TOOLS` | Proactive repo health, unpushed commits, detached HEAD, stale branches. |
| **Project Agent** | `agents/project/project_agent.py::project_agent` | `sys_prompt.yaml` | `PROJECT_TOOLS`, `HISTORY_TOOLS`, `EMBEDDING_TOOLS` | Repository architecture, README/docs synthesis, onboarding context. |
| **Docs Agent** | `agents/docs/docs_agent.py::docs_agent` | `sys_prompt.yaml` | `get_git_command_help`, `get_git_config_docs` | Git command documentation, syntax help, workflow explanations. |

Each agent is orchestrated via LangGraph's functional API:
```python
@task
def call_llm(messages, model_with_tools): ...

@task
def call_tool(tool_call): ...

@entrypoint()
def <agent_name>(messages: list[BaseMessage]) -> str: ...
```

---

## 3. LangGraph Orchestration & State Flow

The workflow orchestration resides in `workflows/`:
1. **Router (`workflows/router.py`):**
   - Uses `get_llm(temperature=0).with_structured_output(RoutingDecision)`.
   - Classifies queries into primary and optional secondary `AgentType` targets.
   - Provides optional fast-paths for explicit CLI commands (`story`, `explain`, etc.).
2. **Orchestrator (`workflows/orchestrator.py`):**
   - Coordinates: `User Query -> Router -> [Primary + Secondary Agents] -> Synthesizer -> Final Response`.
   - Exposes helper run functions: `run_query()`, `run_suggest()`, `run_recover()`, `run_story()`, `run_explain()`, `run_project()`.
3. **Synthesizer (`workflows/synthesizer.py`):**
   - Merges multiple agent outputs, resolves discrepancies, enforces GitHub-Flavored Markdown without HTML/ANSI noise.

---

## 4. Current Persistence & Vector Store Analysis

### 4.1 SQLite (`data/database.py`)
- **Connection:** `sqlite3.connect(self.db_path)` with WAL mode.
- **Default Location:** `~/.gitmind/gitmind.db`.
- **Existing Tables:**
  1. `commits` (hash PK, full_hash, message, author, author_email, date, files_changed, insertions, deletions, repo_path)
  2. `branches` (name, is_current, tracking, ahead, behind, last_commit_hash, repo_path)
  3. `tags` (name, commit_hash, date, message, repo_path)
  4. `pull_requests` (number, title, body, state, author, created_at, merged_at, base_branch, head_branch, labels, repo_path)
  5. `issues` (number, title, body, state, author, created_at, closed_at, labels, assignees, repo_path)
  6. `comments` (id, parent_type, parent_number, author, body, created_at, repo_path)
- **Classification:** Cache information and basic relational metadata. Does **not** include a unified knowledge graph, multi-agent run tracking, persistent findings, evidence references, or audit trails.

### 4.2 ChromaDB (`embeddings/vector_store.py`)
- **Technology:** `chromadb.PersistentClient` storing in `~/.gitmind/chroma`.
- **Ingestion:**
  - `index_commits()`: embeds `f"Commit by {author}: {message}"` with doc_id `f"{repo_id}:commit:{hash}"`.
  - `index_prs()`: embeds `f"PR #{number}: {title}. {body[:500]}"` with doc_id `f"{repo_id}:pr:{number}"`.
  - `index_issues()`: embeds `f"Issue #{number}: {title}. {body[:500]}"` with doc_id `f"{repo_id}:issue:{number}"`.
- **Retrieval:** Cosine distance over batch embeddings via `collection.query()`.
- **Tool:** `@tool def semantic_search(query: str, top_k: int = 5, filter_type: str = "") -> str`.
- **Dependencies in `pyproject.toml`:** `chromadb>=0.5.0`, `llama-index>=0.12.0`, `llama-index-vector-stores-chroma>=0.4.0`, `llama-index-embeddings-langchain>=0.3.0`.

---

## 5. Embedding Model & Vector Dimensions

Configured in `config.sample.py`:
- **Default Provider:** `EMBEDDING_PROVIDER` (defaults to `gemini` or `openai`).
- **Gemini Embedding Model:** `models/gemini-embedding-001` (dimension = 768 or 1536 depending on version/output config).
- **OpenAI Embedding Model:** `text-embedding-3-small` (dimension = 1536).
- **Migration Requirement:** The vector table schema in Db2 requires dynamic dimension detection based on the active embedding model rather than hardcoded 768 dimensions.

---

## 6. GitHub Integration & Security

- **Client:** `github_integration/github_client.py` using `PyGithub`.
- **Token Configuration:** Optional `GITHUB_TOKEN`.
- **Graceful Degradation:** If `GITHUB_TOKEN` is unset or invalid, GitHub tools are omitted from agents without crashing local Git operations.

---

## 7. CLI Command Surface

Defined in `cli.py`:
1. `gitmind story` (`--days`, `--detailed`, `--quickoverview`, `--by`, `--ai/--no-ai`)
2. `gitmind ask` (`[question]`, `--chat`)
3. `gitmind recover`
4. `gitmind suggest`
5. `gitmind explain` (`[target]`)
6. `gitmind project` (`[question]`)
7. `gitmind index` (`--days`)

---

## 8. Migration Scope for GitMind 2.0 (IBM Db2)

To transform GitMind into GitMind 2.0 while preserving 100% of existing functionality:
1. **Db2 Connection Layer (`data/db2/connection.py`):**
   - Native `ibm_db` / `ibm_db_dbi` connection pooling with SSL/TLS support.
   - Comprehensive connection diagnostics (`gitmind db2 doctor`, `gitmind db2 test`).
2. **Versioned Relational Schema (`data/db2/migrations/`):**
   - `GITMIND_REPOSITORIES` (repository catalog and indexed HEAD state)
   - `GITMIND_ARTIFACTS` (unified storage for commits, code symbols, files, PRs, issues, docs)
   - `GITMIND_RELATIONS` (Repository Knowledge Graph: touches, modifies, references, parent_of)
   - `GITMIND_INDEX_RUNS` (incremental indexing runs, artifact counts, failure records)
   - `GITMIND_AGENT_RUNS` (multi-agent trace records)
   - `GITMIND_FINDINGS` (persistent engineering memory and regression records)
   - `GITMIND_FINDING_EVIDENCE` (grounded line/file/commit citations)
   - `GITMIND_AUDIT_EVENTS` (append-only compliance and developer action log)
3. **Db2 Vector Store (`data/db2/vector_store.py`):**
   - Official `langchain-db2` (`DB2VS`) implementation.
   - Native `VECTOR_DISTANCE` execution with cosine distance.
   - Strict repository isolation via metadata filtering.
4. **Evidence Verification Layer:**
   - Structured agent outputs (`AgentFinding`, `EvidenceReference`).
   - Cross-referencing against verified Db2 artifacts before synthesis.
5. **Signature Differentiator (`gitmind review`):**
   - Historical change-risk and regression intelligence comparing working diffs against historical bug fixes and reverted commits stored in Db2.
6. **No Silent Fallback:**
   - When Db2 backend is configured, errors must be explicitly reported with diagnostics.
