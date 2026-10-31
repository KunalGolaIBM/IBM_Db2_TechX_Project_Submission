# CodeFix AI — Intelligent AI Coding Agent

> **One-Line Pitch:** A full-stack, local-first AI coding assistant that combines zero-execution deterministic Python AST syntax analysis, LangChain-orchestrated local LLM code generation, and enterprise session persistence backed by IBM Db2.

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
- **The Challenge:** Developers frequently write code with subtle syntax bugs, unhandled exceptions, and poor structural patterns. Traditional cloud AI tools send proprietary code to external third-party APIs with high latency, subscription fees, and data privacy risks.
- **Unreliable AI Debugging:** Typical LLMs often 'hallucinate' syntax explanations without verifying language grammar rules, sometimes executing untrusted code on remote servers to find runtime errors.
- **Target Audience:** Developers, students, hackathon builders, and enterprise engineers requiring a secure, private, zero-latency coding assistant that guarantees data isolation and auditability.

---

## Solution Overview
CodeFix AI introduces a dual-layer architecture:
1. **Deterministic Static Pre-Flight Analysis:** Uses Python's native \st\ (Abstract Syntax Tree) engine to parse code in sub-millisecond time. It catches \SyntaxError\, unclosed brackets, mutable default arguments, bare except clauses, and zero-division errors with **zero server code execution**.
2. **Local AI Agent Inference:** Powered by LangChain and local Ollama (\qwen2.5-coder:1.5b\ / \3b\), offering four specialized modes: **Write Code**, **Debug Code**, **Improve Code**, and **Explain Code**, plus multi-turn conversational follow-ups.
3. **Enterprise Audit & History Persistence:** Every prompt, source snippet, error diagnostic, generated solution, and explanation is securely recorded in **IBM Db2** via parameterized SQL queries.

---

## IBM Db2 Integration
- **Db2 Edition & Environment:** IBM Db2 on Cloud / Db2 Community Edition (Linux / Docker).
- **Connector / Driver Used:** Official \ibm_db\ native C-extension driver for Python.
- **Database Schema / Data Models:**
  - Table: \CODEFIX_HISTORY\
  - Columns:
    - \ID VARCHAR(36) NOT NULL PRIMARY KEY\
    - \SESSION_ID VARCHAR(64) NOT NULL\
    - \LANGUAGE VARCHAR(32) NOT NULL\
    - \MODE VARCHAR(32) NOT NULL\
    - \USER_PROMPT CLOB(1048576)\
    - \ORIGINAL_CODE CLOB(1048576)\
    - \ERROR_MESSAGE CLOB(1048576)\
    - \GENERATED_CODE CLOB(1048576)\
    - \EXPLANATION CLOB(1048576)\
    - \MODEL_NAME VARCHAR(64) NOT NULL\
    - \CREATED_AT TIMESTAMP DEFAULT CURRENT TIMESTAMP\
  - Index: \CREATE INDEX IDX_CODEFIX_SESSION ON CODEFIX_HISTORY (SESSION_ID, CREATED_AT DESC);\
- **Key Queries & Operations:**
  - **Parameterized Inserts:** \INSERT INTO CODEFIX_HISTORY (ID, SESSION_ID, LANGUAGE, MODE, USER_PROMPT, ORIGINAL_CODE, ERROR_MESSAGE, GENERATED_CODE, EXPLANATION, MODEL_NAME) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\
  - **Indexed Session Queries:** \SELECT * FROM CODEFIX_HISTORY WHERE SESSION_ID = ? ORDER BY CREATED_AT DESC\
  - **Transparent Setup Mode:** When credentials are not yet configured in \.env\, the UI seamlessly displays a dedicated Setup Mode banner while unit tests mock the Db2 connection cleanly.

---

## AI / LLM Architecture
- **Framework:** LangChain (\langchain_core\ and \langchain_ollama\).
- **Model Provider & Model:** Ollama local runtime serving \qwen2.5-coder:1.5b\ (default, optimized for rapid CPU inference with 6 Performance-core threads) and \qwen2.5-coder:3b\.
- **Workflow & Guardrails:**
  - Pre-execution AST diagnostics are formatted and injected into mode-tailored system prompts.
  - Strict system directives command the model to treat input code as untrusted and output clean markdown blocks.
  - \extract_code_and_explanation()\ automatically isolates runnable source code from architectural explanations.
  - Multi-turn conversational memory maintains context across follow-up queries (\HumanMessage\ / \AIMessage\ chains).

---

## Tech Stack
- **Backend:** Python 3.10+ / Flask 3.1.3
- **Database:** IBM Db2 (\ibm_db\ >= 3.2.0)
- **AI Engine:** LangChain 1.4.7 + Ollama Local LLM
- **Frontend:** Modern Charcoal Dark Theme, Responsive Flexbox/Grid, Prism.js Syntax Highlighting, FontAwesome
- **Static Analysis:** Python native \st\ (Abstract Syntax Tree)
- **Testing:** pytest 9.2.0 (36 automated unit & integration tests)

---

## Prerequisites
- Python 3.10 or higher
- Ollama installed on your system ([ollama.com](https://ollama.com))
- IBM Db2 credentials (or use the built-in Setup Mode)

---

## Setup & Installation

`ash
# 1. Navigate to submission directory
cd submissions/codefix-ai

# 2. Create and activate a virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# 3. Install required packages
pip install -r src/requirements.txt
`

---

## Configuration

Copy \.env.example\ to create your local \.env\:

`ash
cp .env.example .env
`

Edit \.env\ with your settings:
\\\ini
SECRET_KEY=dev-secret-key-codefix-ai
PORT=5000

# Ollama Local Runtime
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:1.5b

# IBM Db2 (Leave blank for Setup Mode)
DB2_DATABASE=BLUDB
DB2_HOSTNAME=
DB2_PORT=32733
DB2_UID=
DB2_PWD=
DB2_PROTOCOL=TCPIP
DB2_SECURITY=SSL
\\\

---

## Running the Project

`ash
# 1. Start Ollama and download the model (one-time)
ollama pull qwen2.5-coder:1.5b

# 2. Run the built-in system verification check
python src/demo_check.py

# 3. Launch the web application
python src/app.py
`
Open your browser at: **\http://localhost:5000\**

---

## Testing & Verification
Execute the test suite (36 unit, integration, and mock tests):
`ash
pytest tests/ -v
`

---

## Screenshots & Demo
- **Live Demo URL:** \http://localhost:5000\
- **Demo Video Link:** [Watch Demo Video](https://youtu.be/YOUR_DEMO_VIDEO_ID)
- **Repository:** [https://github.com/raiakanchha07/CodeFix-AI](https://github.com/raiakanchha07/CodeFix-AI)

---

## Known Limitations & Future Roadmap
- **Current Limitations:** Deterministic AST analysis is implemented natively for Python. JavaScript, Java, and C++ syntax checking currently rely on LLM semantic verification.
- **Future Roadmap:**
  - Multi-file workspace and GitHub repository analysis.
  - Adding ESLint and Clang AST static passes for multi-language deterministic checking.
  - IBM watsonx.ai cloud model provider integration alongside local Ollama.

---

## Team Members & Credits
| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Akanchha Rai | [@raiakanchha07](https://github.com/raiakanchha07) | Full-Stack Architecture, LangChain & IBM Db2 Integration |
