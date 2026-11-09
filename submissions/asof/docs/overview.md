# What is built, and how AsOf compares

The status of each part, and where AsOf stands next to existing tools. The short version is in the [README](../README.md#solution-overview).

## Build status

| Capability | Status |
|---|---|
| Db2 schema, least-privilege users, seed data, as-of + vector retrieval, replay query | Done, tested |
| LLM layer: provider switch, strict schemas, batched judge, hard deadlines | Done, tested |
| Claim pipeline, deterministic rule checks, redaction, hash-chained ledger, API, LangChain runnable | Done, tested (incl. live LLM) |
| Policy changes (`APPLY_POLICY_CHANGE`), change impact (`CHANGE_IMPACT`), JSON_TABLE views, web UI | Done, tested, checked in a browser |
| Evaluation: nine frozen splits (191 cases) | Done for OpenRouter on all nine; the airline split also on Ollama and watsonx.ai; results in [evaluation.md](evaluation.md) |
| LangGraph check graph with an investigating agent; change-impact agent drafting corrections for approval | Done, tested, evaluated |
| Second domain (a bank fee schedule) with its own frozen split; extractor-injection split | Done, evaluated |
| Row and column access control; "Ask the ledger" (SQL chain as a read-only analyst, SQLGlot gate) | Done, tested against Db2 |
| Policy intake (PDF to draft to approval), customer chat page, MCP server | Done, tested against Db2 and in a browser; intake measured on a frozen evaluation; the MCP server run against a live AsOf |
| IBM watsonx.ai as the model and as Db2's embedder | Done and run on a real (Lite) account: the airline split and the intake evaluation on `ibm/granite-4-h-small`, and Db2 embedding on watsonx.ai ([results](evaluation.md#on-ibm-watsonxai)) |
| Specialist inbox, correction notices, routing, clause version diff | Done, tested against Db2 and in a browser; inbox replies and the notice agent run end to end on the hosted and the local model, and the inbox's suggested replies replay without a key; routing measured on a frozen split ([results](routing_eval.md)) |
| dbt marts, Airflow nightly audit, Langflow component, cookbook recipe, one-command quick start | Done and run for real: dbt and Airflow against Db2 in CI; the quick start in CI from a bare runner; the Langflow flow against a live AsOf on 6 Nov (its component tests run in CI); the cookbook notebook against Db2 on 7 Nov |


## How AsOf compares

AsOf does not claim to have invented checking AI answers against policy.

- **Amazon Bedrock Automated Reasoning checks** already validate responses against policies, suggest corrections and log results.
- **NVIDIA NeMo Guardrails** fact-checking rails score an answer against retrieved text.
- **IBM watsonx.governance** measures RAG quality (faithfulness and related metrics).

What AsOf adds is time, inside the customer's own system of record: effective-dated policy versions (what was true on date X), bitemporal replay (what the database held at moment T), and change impact on past answers and published content. It is open source, runs locally, and keeps all of it in Db2.
