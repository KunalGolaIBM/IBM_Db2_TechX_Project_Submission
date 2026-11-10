# Model gateway

## What it does

All model calls go through one gateway in `src/parity/gateway/client.py`. Agents never call a provider directly.

## Features

- **Cache first.** Every call has a stable key from agent, prompt, model, and settings. A cache hit costs zero tokens and no network time.
- **Provider fallback.** Providers are tried in order. Rate limits, server errors, and timeouts move to the next provider. The last link can be a local model.
- **Budgets.** Per query and per run token limits. When a limit hits, the query goes to a human instead of looping.
- **Replay mode.** With `replay_only=True`, the gateway uses cache only. A miss raises a clear error. A recorded run can repeat offline with no API key.
- **Usage report.** Calls, cache hits, cache hit rate, tokens in and out, and counts per provider.

## Cache stores

- `InMemoryCache` for tests and short runs.
- `Db2Cache` stores calls in the `llm_cache` table in Db2. The DDL is in `src/parity/gateway/cache.py`.

## Data privacy

Prompts hold only SQL text, table and column names, and synthetic test values. Production rows are never sent to a model.

## Transport

The default transport speaks the OpenAI compatible chat API with the standard library only. No extra dependency is needed. Tests inject a fake transport.
