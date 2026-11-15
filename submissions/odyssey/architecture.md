# Odyssey Architecture

## Components

```text
React/Vite UI
  -> existing Supabase Edge Function (optional Gemini suggestions)
  -> deterministic TypeScript planner (offline fallback)

backend/src/odyssey_db2.py
  -> parse_capture()
  -> LangChain chain (optional model planning)
  -> Db2TaskStore (parameterized ibm_db writes)
  -> IBM Db2 ODYSSEY_TASKS table
```

The browser application remains responsible for the interactive Capture, Plan, and Execute screens. The Python service is a separate, reproducible Db2 integration boundary for the submission and can run without changing the existing frontend deployment.

## Request Flow

1. A user submits free-form text such as `"finish report, email mentor"`.
2. `parse_capture()` creates typed `Task` values.
3. `generate_plan()` uses a LangChain `ChatPromptTemplate` chain when `OPENAI_API_KEY` is present. Otherwise, `order_tasks()` provides an offline priority-ordered plan.
4. With `--save`, `Db2TaskStore` validates required environment variables, connects through `ibm_db`, and executes a prepared INSERT for every task.
5. The CLI emits JSON containing the parsed tasks and plan, making the service easy to wrap with an API later.

## Db2 Data Model

`ODYSSEY_TASKS` stores the original capture alongside normalized task fields. The timestamp index supports future history and recurring-goal queries.

```sql
ODYSSEY_TASKS(
  ID, RAW_INPUT, TITLE, CATEGORY, PRIORITY, CAPTURED_AT, CREATED_AT
)
```

All values from the capture are bound as statement parameters. Secrets are loaded from environment variables and are never written to the repository.

## Reliability and Security

- The frontend has a deterministic planner fallback when its optional AI function is unavailable.
- The backend has a deterministic fallback when no model API key is configured.
- Db2 configuration is validated before connecting.
- SQL uses prepared statements; the schema and example environment file contain no real credentials.
