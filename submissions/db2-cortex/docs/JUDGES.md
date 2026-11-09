# Judge's 90-second path (Db2 Cortex)

## Official criteria → exact proof

| Criterion | Weight | Where to look | One command / click |
|---|---|---|---|
| **IBM Db2 Integration** | 30% | `src/db.py`, `src/seed.py`, `src/agents.py` | `python src/verify.py` → VECTOR_DISTANCE, cache, memory, hash-chain, PREPARE, DB2VS all PASS |
| **Innovation & Creativity** | 25% | Guardrail + Auditor + Intent gate | Ask "Delete all customers" → blocked. Ask same question twice → cache hit. Audit tab → **Simulate tampering** → chain breaks (rolled back) |
| **Technical Architecture** | 20% | `architecture.md`, `src/agents.py` | 9-node LangGraph with conditional edges: cache hit, self-repair (max 3), policy stop |
| **Reproducibility** | 15% | `docker-compose.yml`, `src/verify.py`, `tests/` | 7 commands in README. `pytest tests` needs **no database** |
| **Documentation** | 10% | README, this file, UI "Db2 inside" page | Live counts of every Db2 object the agents use |

## Fastest path to conviction

```bash
cd submissions/db2-cortex
cp .env.example .env          # set DB2_PASSWORD
docker compose up -d
cd src && python wait_db.py && python seed.py && python verify.py
uvicorn app:app --port 8000   # open http://localhost:8000
```

In the UI (2 minutes):

1. **Ask** → "Which branches have the highest loan default rate?"
2. **Repeat** the same question → semantic cache hit (no LLM)
3. **Ask** → "Delete all customers" → Guardrail blocks, row count unchanged
4. **Role = Analyst** → "Top 10 customers by balance" → PII denied
5. **Audit ledger** → Verify chain → Simulate tampering (detects break, rolls back)
6. **Db2 inside** → live counts: SEMANTIC_LAYER, QUERY_CACHE, SESSION_MEMORY, AUDIT_LOG

## What makes this different from "LLM + SQL"

- Every stateful AI component lives **inside Db2** (not Redis / files / another DB)
- VECTOR semantic layer + VECTOR_DISTANCE for retrieval and cache
- Hash-chained audit log (`PREV_HASH → HASH`) that is tamper-evident
- sqlglot AST + role-aware PII + Db2 PREPARE before any row is touched
- Self-repair loop feeds Db2 errors back to the SQL Writer (max 3 attempts)

## Offline demo mode

`LLM_PROVIDER=demo` (default) answers 6 banking topics without any API key so judges can evaluate the full pipeline, guardrails and audit without external dependencies. Set a real provider in `.env` for free-form questions.
