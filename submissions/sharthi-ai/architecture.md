# Sharthi AI Architecture

## Overview
Sharthi AI is a Db2-powered conversational assistant built for educational and institutional data access. It emphasizes natural-language interaction, safe query generation, and human-readable analytics output.

---

## System Architecture

```text
User
  |
  v
+----------------------+
| Frontend / Streamlit |
| or CLI / Web UI     |
+----------------------+
          |
          v
+----------------------+
| AI Layer             |
| - Intent detection   |
| - SQL generation     |
| - Response summary  |
+----------------------+
          |
          v
+----------------------+
| Db2 Connector        |
| - ibm_db / SQLAlchemy|
| - schema validation |
+----------------------+
          |
          v
+----------------------+
| IBM Db2 Database     |
| - students           |
| - attendance         |
| - courses            |
| - results            |
| - events             |
+----------------------+
```

---

## Data Flow
1. User enters a question in natural language
2. App routes it to the AI layer
3. LLM converts it into a Db2-safe query
4. Query is executed against IBM Db2
5. Data is returned and summarized
6. Result is displayed in plain English

---

## Db2 Data Model
Example conceptual schema:
- `students(id, name, program, year, cgpa)`
- `attendance(student_id, course_id, present_days, total_days)`
- `courses(course_id, name, faculty_id, credits)`
- `results(student_id, course_id, marks, grade, semester)`
- `events(event_id, title, date, venue, type)`

This allows the assistant to answer academic and operational queries with real data.

---

## Security Considerations
- Validate generated SQL before execution
- Restrict access based on role
- Avoid exposing raw DB credentials
- Use safe environment variables and `.env.example`
