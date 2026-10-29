# Sharthi AI

> One-Line Pitch: Sharthi AI is an AI-powered student support and analytics assistant that connects to IBM Db2 to answer questions, retrieve insights, and simplify academic or institutional data access through a conversational interface.

---

## Problem Statement
Educational institutions generate large amounts of student, attendance, marks, and resource data, but most of it remains buried in databases and spreadsheets. Students and staff often face delays when they need quick answers such as upcoming events, performance trends, seat availability, or administrative status. Existing tools are either limited to raw SQL queries or require technical expertise, which reduces accessibility and slows decision-making.

Sharthi AI solves this by providing a natural-language interface over IBM Db2, allowing users to ask questions in plain English and receive structured insights without writing SQL.

---

## Solution Overview
Sharthi AI is a lightweight AI assistant built on top of IBM Db2 that:
- Accepts natural-language questions
- Converts them into SQL queries using a structured prompt/LLM workflow
- Executes queries against IBM Db2
- Returns summarized, human-readable answers
- Helps students, faculty, and admins explore institutional data quickly

Core features:
- Student performance summary
- Attendance and enrollment insights
- Query answering from academic records
- Safe and policy-controlled database interaction
- Clean UI or CLI for review and demonstration

---

## IBM Db2 Integration
- Db2 Edition & Environment: IBM Db2 Community Edition / local DB2 instance
- Connector / Driver Used: Python with `ibm_db` and SQLAlchemy
- Database Schema / Data Models: tables like `students`, `courses`, `attendance`, `results`, `faculty`, `events`
- Key Queries & Operations:
  - Fetch student performance summary
  - View attendance trends by subject
  - Query semester-wise result stats
  - Retrieve course and enrollment data

Example queries:
- "Show me the top 5 students by GPA."
- "How many students are absent in Database Systems this week?"
- "What courses are currently under-enrolled?"

---

## AI / LLM Architecture
- Framework: LangChain or custom prompt-driven Python flow
- Model Provider & Model: OpenAI / Gemini / local Ollama model
- RAG / Tool Calling Workflow:
  1. User asks a question in natural language
  2. LLM interprets intent and decides if a Db2 query is needed
  3. Query is generated or validated against a schema
  4. Result is fetched from IBM Db2
  5. Response is summarized and returned to the user

This makes the assistant useful for both technical and non-technical users.

---

## Tech Stack
- Backend / Core: Python 3.11, FastAPI
- Database: IBM Db2
- Frontend / UI: Streamlit or simple web interface
- Libraries & Tools: LangChain, `ibm_db`, SQLAlchemy, `python-dotenv`, `pandas`

---

## Prerequisites
- Docker or running IBM Db2 instance
- Python 3.10+
- pip
- Optional: OpenAI/Gemini API key or local LLM model

---

## Setup & Installation

```bash
git clone https://github.com/<your-username>/IBM_Db2_TechX_Project_Submission.git
cd IBM_Db2_TechX_Project_Submission
cd submissions/sharthi-ai

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Configuration

Copy the sample environment file and update your keys:

```bash
cp .env.example .env
```

Add:
- DB2 connection details
- OpenAI/Gemini key if using AI model
- optional app settings

> Security Warning: Never commit `.env` with real credentials.

---

## Running the Project

```bash
python src/main.py
```

Or if using Streamlit:

```bash
streamlit run src/app.py
```

---

## Testing & Verification

```bash
pytest
```

Also validate:
- DB2 connection
- schema visibility
- natural-language to SQL conversion
- result summarization

---

## Screenshots & Demo
- Live Demo Link: [Add URL if hosted]
- Demo Video Link: [Add YouTube / Loom / Drive link]

Add screenshots in `docs/screenshots/` and embed them below if available.

---

## Known Limitations & Future Roadmap
- Current Limitations:
  - Limited schema awareness for complex enterprise systems
  - Basic security constraints for DB access
  - Works best with a structured academic schema
- Next Steps:
  - Add role-based access control
  - Support more query templates
  - Improve AI reasoning and SQL validation
  - Add analytics dashboard and export features

---

## Team Members & Credits

| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Akash | [@akash614214-dotcom](https://github.com/akash614214-dotcom) | Project lead, architecture, DB2 integration |
| Contributor 2 | [@username](https://github.com/username) | AI workflow / backend |
