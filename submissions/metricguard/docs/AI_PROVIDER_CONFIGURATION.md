# AI Provider Configuration

MetricGuard's language model only ever produces a typed `PlannerOutput` (metrics, dimensions, filters, dates, sort, limit). It never writes or runs SQL. Everything after planning is deterministic: Pydantic validation, registry hash check, SQL compiler, SQL guard, parameterized read-only Db2 execution, reconciliation and audit.

## Providers

| `AI_PROVIDER` | Planner | Real inference | Needs |
|---|---|:-:|---|
| `meta` | LangChain `ChatOpenAI` → Meta Model API, model `muse-spark-1.3` | yes | `MODEL_API_KEY` |
| `anthropic` | LangChain `ChatAnthropic` (optional legacy adapter, never run live) | yes | `ANTHROPIC_API_KEY` |
| `demo` | Rule-based `RuleBasedPlanner`, labelled `DEMO_RULE_BASED` | **no** | nothing |
| `auto` (default when `AI_PROVIDER` is unset) | Meta if `MODEL_API_KEY` is set, else Anthropic if `ANTHROPIC_API_KEY` is set, else demo | per result | nothing |

## Precedence and aliases

1. `AI_PROVIDER` (`meta | anthropic | demo | auto`).
2. If unset, the deprecated `PLANNER_MODE`: `auto` → `auto`, `demo` → `demo`, `llm` → Meta, else Anthropic, else none.
3. If both are unset: `auto`.

Empty values and `your_...` placeholders count as "not set". There are no other aliases. `MODEL_API_KEY` is Meta's documented variable name; the OpenAI SDK does not read it implicitly, so the code passes it explicitly.

## Failure behavior (no silent demo fallback)

| Situation | Result |
|---|---|
| `AI_PROVIDER=meta` but no `MODEL_API_KEY` | `503 PLANNER_UNAVAILABLE` on `POST /api/analyze`; `GET /api/health` shows planner `not_configured`. **Not** demo. |
| Meta rejects the key (401/403), unknown model (404), bad request (400), rate limit (429), 5xx, timeout, network error | `503 PLANNER_UNAVAILABLE` with a short safe message. Not audited (the audit status set has only the five analysis outcomes). The key is never echoed. |
| Model answers with invalid JSON, a value outside the schema, an extra field, truncated output, or a refusal / content filter | The model was reachable, so this is a bad plan: status `BLOCKED`, check V01 `FAIL`, reason `PLAN_SCHEMA_INVALID`, audited. |
| Model plans an unknown metric or dimension, or a write | Registry validation / policy → `BLOCKED` as before. |

Only `AI_PROVIDER=demo`, or `auto` with no key at all, selects the demo planner, and the response then says `DEMO_RULE_BASED` with its disclosure.

## Meta Model API setup

Official docs: https://dev.meta.ai/docs/overview, `/docs/quickstart`, `/docs/structured-output`. This is the **Meta Model API** (Muse Spark), not the Llama API and not a Meta AI app token; create the key under *API keys* in the Model API dashboard.

```dotenv
AI_PROVIDER=meta
MODEL_API_KEY=<your key, never commit>
META_MODEL=muse-spark-1.3          # also documented: muse-spark-1.1
META_BASE_URL=https://api.meta.ai/v1
META_REASONING_EFFORT=low          # documented values: minimal|low|medium|high|xhigh|max; empty = send nothing
PLANNER_TIMEOUT_SECONDS=30         # per attempt, shared by both real providers
PLANNER_MAX_RETRIES=1              # SDK retry (also after a timeout): worst case ~2 x 30 s + backoff
```

```bash
cd metricguard-db2
uv pip install --python .venv/bin/python -e "backend[dev]"   # installs langchain-openai
make db-up && make api                                       # restart the API after changing .env
curl -s localhost:8000/api/health | jq .planner
# {"status":"ready","provider":"meta","model":"muse-spark-1.3","execution_mode":"LLM"}
```

### How the request is built

`ChatOpenAI(model, api_key, base_url, timeout, max_retries, use_responses_api=False)` calls `POST {base_url}/chat/completions`, with `with_structured_output(PlannerOutput, method="json_schema", strict=True, include_raw=True)`. The wire request carries `response_format = {"type":"json_schema","json_schema":{"name":"PlannerOutput","strict":true,"schema":{…}}}`, which matches Meta's Chat Completions format. The existing Pydantic schema already satisfies Meta's strict subset (root `object`, every object `additionalProperties:false`, `required` = all properties, no `oneOf`/`allOf`, no recursion, depth ≤ 10); `tests/test_meta_provider.py` checks this locally and a live request confirmed it.

Not sent: `temperature`, `top_p`, tools, tool choice. The planner does not need them. `reasoning_effort` is sent only when `META_REASONING_EFFORT` is set.

### `META_REASONING_EFFORT` (documented; `low` recommended for the demo)

Meta documents `reasoning_effort` as a top-level Chat Completions parameter for Muse Spark 1.3 (<https://dev.meta.ai/docs/reasoning>, read 2026-11-07): `minimal`, `low`, `medium`, `high`, `xhigh`, `max`. `none` returns HTTP 400 for Muse Spark, so the setting rejects it at startup. If the parameter is omitted, the model picks its own level. Reasoning tokens count toward the output budget and are reported in `usage.completion_tokens_details.reasoning_tokens`.

How it is wired and verified:

| Check | Evidence |
|---|---|
| Env → setting | `Settings.meta_reasoning_effort` accepts the six documented values; empty means unset; `none` and unknown values fail validation (`tests/test_meta_provider.py`) |
| LangChain forwards it | `ChatOpenAI(reasoning_effort=…)` puts it top-level in the Chat Completions payload (unit test over `_get_request_payload` for all six values; mock-server test asserts it on the wire) |
| Meta accepts it | Live wire capture, `scripts/live_e2e.py`: 3/3 requests carried `"reasoning_effort": "low"`, HTTP 200, `strict` JSON Schema, 1,016–1,518 reasoning tokens ([`evaluation/live-checks/live-e2e.json`](../src/evaluation/live-checks/live-e2e.json)) |

Why `low`: on the same 37-case benchmark `low` gave the same 37/37 result as the default and about half the latency (executed median 2.3 s vs 4.1 s, all-case p90 5.0 s vs 10.0 s). On one ambiguous prompt the default used 4,699 reasoning tokens (34.2 s) against 687 (5.3 s) for `low`. To change it, edit `.env` and restart the API; no code change is needed.

### Timeouts and the request budget

`PLANNER_TIMEOUT_SECONDS` is per attempt, and the OpenAI and Anthropic SDKs retry a timed-out attempt (`PLANNER_MAX_RETRIES`, default 1). The earlier default was 45 s, so a slow model call could hold a request for about 91 s, longer than the browser's 90 s limit for `POST /api/analyze`. That is the likely source of the one UI request that waited over 60 s (first attempt timed out at 45 s, the retry then succeeded). The default is now 30 s: the worst case is about 61 s, below the browser limit, so the UI always shows the API's own result or its `503 PLANNER_UNAVAILABLE`. A unit test keeps `timeout × (retries + 1) + 8 s < 90 s`. With `low`, the slowest planning call observed was 14.5 s.

### Observed behavior and limits

- Latency without `low` varied from 2 s to 34 s per planning call; one UI run exceeded 60 s (see "Timeouts" above). With `low`: executed requests median 2.3 s, max 3.8 s; vague classification questions 9–15 s (audit probe).
- Same prompt, different outcomes: "Show our best-performing region." returns AMBIGUOUS or BLOCKED (`OUT_OF_SCOPE`). The audit probe found the cause: the model classified it `ambiguous` 3/3 times, but only once named candidate metrics. With candidates the pipeline offers a clarification (AMBIGUOUS); without candidates it has nothing safe to offer and blocks. Both outcomes are non-executing. The guided demo no longer uses this question; for a deterministic ambiguity demo use "What was our revenue last quarter?" (the policy screen forces AMBIGUOUS regardless of the model).
- Quota and billing could not be queried (no documented endpoint). The benchmark runs used roughly 200 small requests.

## Optional Anthropic adapter

`AI_PROVIDER=anthropic` with `ANTHROPIC_API_KEY`, `PLANNER_MODEL` (default `claude-sonnet-5-5`), `PLANNER_EFFORT`, `ANTHROPIC_BASE_URL`. Covered by mock-provider tests only. Never run against the real Anthropic API.

## What the API and UI report

`planner = {name, provider, model, execution_mode, disclosure}`:

| Mode | `name` | `provider` | `model` | `execution_mode` | `disclosure` |
|---|---|---|---|---|---|
| Meta | `langchain-meta` | `meta` | `muse-spark-1.3` | `LLM` | `null` |
| Anthropic | `langchain-anthropic` | `anthropic` | e.g. `claude-sonnet-5-5` | `LLM` | `null` |
| Demo | `rules-demo` | `metricguard-rules` | `null` | `DEMO_RULE_BASED` | non-empty |

The UI shows "AI planner · Meta Model API · muse-spark-1.3" only when `execution_mode` is `LLM`; the demo banner only for `DEMO_RULE_BASED`. Audit rows store the planner name (`langchain-meta`) and model; rows written before provider selection was added say `langchain-structured` or `rules-demo`.

## Tests by kind

| Kind | Where | Network |
|---|---|---|
| Deterministic | policy, compiler, oracle, rules planner tests | none |
| Mock provider | `tests/test_meta_provider.py` (41 tests, local fake of Meta's endpoint), `tests/test_planner.py` (Anthropic fake) | localhost only |
| Real Meta inference | `make test-live-llm`, `make eval-llm`, Playwright `real.meta.spec.ts` | Meta API, costs credits |
