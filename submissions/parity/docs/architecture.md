# Architecture

This document describes how Parity is built and why.

## Core rule

The model proposes. Execution decides.

Agents can suggest a translation, test data, or a fix. Only the Parity Engine can mark a query as MATCH. The engine is plain Python code. It has no model call, no prompt, and no guesswork.

## Parts

### Parity Engine

- Runs a query on the source database and on Db2.
- Normalizes results before comparison.
- Compares rows and returns MATCH, MISMATCH, ERROR, or NOT_COMPARABLE.
- Prints every setting it used, so no difference is hidden.

Comparison rules:

- Row order does not matter unless the query has ORDER BY.
- Column names are compared without case. Column order must match.
- Integers and decimals must match exactly.
- Floats use a small tolerance that is set in config.
- Timestamps are changed to UTC before comparison.
- NULL equals NULL. NULL never equals an empty string.
- Text is compared exactly. Trailing space changes get their own category.

### Agents

Parity uses CrewAI for agents. Each agent has one job.

- **Translator:** turns PostgreSQL SQL into Db2 SQL.
- **Fuzzer:** designs edge case values for the tables a query touches.
- **Diagnostician:** explains why a query mismatched.
- **Fixer:** rewrites the Db2 query to remove the difference.

Agents are not judges. The controller decides when each agent runs.

### Controller

A CrewAI Flow written in Python. It sets:

- Max 3 fix attempts per query.
- Token budget per query and per run.
- Timeouts for every step.
- Stop rules. When a limit hits, the query goes to a human.

The controller is code. Limits live in code, not in a prompt.

### IBM Db2

Db2 has three roles.

1. **Target.** Db2 is the real database under test. Not a mock.
2. **Knowledge base.** Known differences and verified fixes live in a table with a VECTOR column. Search uses similarity.
3. **System of record.** Workloads, translations, fuzz cases, runs, results, history, and model call cache all live in Db2.

One database for all three keeps backup, access control, and audit in one place.

Minimum version: Db2 12.1.2 or later because of the VECTOR type.

### LLM gateway

All model calls go through one OpenAI compatible client.

- Cache first. A repeat call costs zero tokens.
- Fallback chain. If one provider hits a rate limit, the next one answers. The last step is a local model.
- Replay mode. A recorded run can repeat offline with no API key. A cache miss stops the run with a clear error.
- Budgets. Token limits per query and per run.

Prompts hold only SQL text, table and column names, and synthetic test values. Production rows are never sent to a model.

### Safety

- Everything runs on disposable containers. Never on production.
- Only read queries run against the source workload.
- Agents can change data only in the throwaway test schema.
- Every query has a timeout and a row limit.
- Every input, output, and SQL statement is logged for audit.

## Data flow

1. Ingest and tag queries.
2. Translate with rules first, agent second.
3. Copy schema and base data to both databases.
4. Add edge case rows to both databases.
5. Run both queries.
6. Compare in the engine.
7. Diagnose mismatches with the knowledge base.
8. Fix and re-prove. Accept only a full match.
9. Save verified fixes. Write the report.

## Why this split of work

The parts that must be right are deterministic. So they are plain code. The parts that need judgement are agents. So they propose, and code checks. This split keeps results repeatable, cheap to audit, and free from model hallucination.
