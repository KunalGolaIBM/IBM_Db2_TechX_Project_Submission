# Judge's 60-second guide

| Criterion (weight) | Where to look | How to verify |
|---|---|---|
| Db2 integration and depth (30%) | `src/db.py`, `src/seed.py`, `src/agents.py` | `python src/verify.py`: VECTOR_DISTANCE, cache, memory, audit chain, DB2VS, PREPARE |
| Innovation and impact (25%) | README "What it does" | Delete request blocked; PII denied for analyst; tamper-evident audit |
| Architecture and AI (20%) | `architecture.md`, `src/agents.py` | LangGraph conditional edges: cache, self-repair, policy stop |
| Reproducibility and code quality (15%) | `docker-compose.yml`, `.env.example`, `tests/` | 7 commands in README; `pytest tests` needs no database |
| Documentation (10%) | README, `docs/screenshots/`, demo video | screenshots and video linked at top of README |
