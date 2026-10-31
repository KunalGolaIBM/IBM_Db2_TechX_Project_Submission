# System Architecture — CodeFix AI

## Overview
CodeFix AI is an intelligent developer assistant featuring a client-side web workspace, a Flask application layer with deterministic static AST validation, an AI orchestration layer powered by LangChain and local Ollama, and a persistent audit layer utilizing IBM Db2.

---

## Architecture Diagram

`mermaid
graph TD
    Client[Browser UI / Prism.js] -->|HTTP POST /generate, /analyze, /improve, /explain| Flask[Flask Backend API]
    Flask -->|Step 1: 0-Execution Check| AST[Python AST Static Analyzer]
    AST -->|Diagnostics & Line Numbers| Flask
    Flask -->|Step 2: Prompt + Context| Agent[LangChain Agent Service]
    Agent -->|Inference via HTTP 11434| Ollama[Local Ollama: qwen2.5-coder:1.5b]
    Ollama -->|Markdown Code + Prose| Agent
    Agent -->|Structured Payload| Flask
    Flask -->|Step 3: Parameterized SQL (?, ?)| Db2[(IBM Db2 Database: CODEFIX_HISTORY)]
    Db2 -->|Persisted Record ID| Flask
    Flask -->|JSON Response| Client
`

---

## Component Breakdown

1. **User Interface / Client Layer**:
   - Modern dark charcoal theme with a dual-pane workspace.
   - Prism.js dynamic syntax highlighting for Python, JavaScript, Java, and C++.
   - Mode selectors, preset demonstration cards, one-click code copy, file download, and multi-turn conversational follow-up threads.

2. **Application Backend Layer (pp.py)**:
   - Flask 3.1.3 web controller managing application routing, input validation (MAX_INPUT_CHARS=10000), error handling, and JSON API endpoints.
   - Coordinates deterministic static analysis before any AI agent invocation.

3. **Deterministic Static Analyzer Layer (nalyzer.py)**:
   - Employs Python's built-in st module (st.parse and st.walk).
   - Detects SyntaxError, unclosed brackets, line numbers, mutable default arguments, bare except: clauses, and division by literal zero.
   - **Zero Code Execution**: Code is parsed without running, eliminating remote code execution vulnerabilities on the host server.

4. **AI Orchestration Layer (gent_service.py)**:
   - Built on LangChain (langchain_ollama.ChatOllama and langchain_core.messages).
   - Dynamically constructs mode-specific prompts for **Write**, **Debug**, **Improve**, and **Explain**.
   - Integrates pre-flight AST diagnostics directly into the LLM context to ensure accurate bug fixes.
   - Extracts clean, runnable source code and separates natural-language explanations using regular expressions.
   - Manages conversational history (HumanMessage and AIMessage pairs) for interactive follow-up requests.

5. **Database Persistence Layer (database.py)**:
   - Direct integration using the official ibm_db driver.
   - Manages connection lifecycle and provides automated schema DDL execution.
   - Stores session history in the CODEFIX_HISTORY table using parameterized SQL statements (? parameter markers) to prevent SQL injection.
   - Includes transparent Setup Mode fallback with descriptive UI notifications when Db2 credentials are not configured.

---

## Data Flow

`mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as Workspace UI
    participant Backend as Flask API (app.py)
    participant AST as Static Analyzer (analyzer.py)
    participant AI as LangChain + Ollama
    participant Db2 as IBM Db2 (database.py)

    User->>UI: Submit Code / Prompt (e.g. Debug Mode)
    UI->>Backend: POST /analyze {language, code, prompt}
    Backend->>AST: analyze_code(code, "python")
    AST-->>Backend: Diagnostics (SyntaxError, Warnings)
    Backend->>AI: execute_task(mode="debug", diagnostics)
    AI->>AI: Build prompt with AST findings
    AI->>AI: Local Ollama Inference (qwen2.5-coder:1.5b)
    AI-->>Backend: {generated_code, explanation}
    Backend->>Db2: INSERT INTO CODEFIX_HISTORY (?, ?, ...)
    Db2-->>Backend: Success / Record Saved
    Backend-->>UI: JSON {code, explanation, diagnostics, suggestions}
    UI-->>User: Render highlighted code & diagnostics card
`

---

## IBM Db2 Schema & Storage Design

`sql
-- Schema Definition: CODEFIX_HISTORY
CREATE TABLE CODEFIX_HISTORY (
    ID VARCHAR(36) NOT NULL PRIMARY KEY,
    SESSION_ID VARCHAR(64) NOT NULL,
    LANGUAGE VARCHAR(32) NOT NULL,
    MODE VARCHAR(32) NOT NULL,
    USER_PROMPT CLOB(1048576),
    ORIGINAL_CODE CLOB(1048576),
    ERROR_MESSAGE CLOB(1048576),
    GENERATED_CODE CLOB(1048576),
    EXPLANATION CLOB(1048576),
    MODEL_NAME VARCHAR(64) NOT NULL,
    CREATED_AT TIMESTAMP DEFAULT CURRENT TIMESTAMP
);

-- Index for Fast Session Queries
CREATE INDEX IDX_CODEFIX_SESSION ON CODEFIX_HISTORY (SESSION_ID, CREATED_AT DESC);
`

---

## Security & Reliability Guardrails
1. **Zero Server Code Execution**: No exec(), eval(), or subprocess shells are used on user-submitted code.
2. **Parameterized Queries**: 100% of SQL statements targeting IBM Db2 utilize parameterized markers (?).
3. **Input Guardrails**: Incoming payloads are strictly capped at 10,000 characters to prevent buffer overruns and denial of service.
4. **Environment Isolation**: Database credentials and secrets are loaded strictly from .env and kept out of version control.
