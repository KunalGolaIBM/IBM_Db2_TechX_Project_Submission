# Agent translation and replay

## How translation works

Rules go first. Each rule rewrite is recorded. Queries the rules cannot handle are the agent path:

1. The pipeline detects an untranslatable pattern.
2. If no agent gateway is configured, the query is `NOT_COMPARABLE` with a clear note. It never executes half translated.
3. If a gateway is configured, the translator agent proposes Db2 SQL through the gateway.
4. The engine executes source and Db2 SQL and decides. Agent output alone proves nothing.

## Recording and replay

Every gateway call is cached by a key made from the agent role, the prompts, and the model name.

```bash
# recording run, needs a real key in the environment
PARITY_LLM_API_KEY=... PARITY_LLM_MODEL=<model> PARITY_LLM_BASE_URL=<url>
parity run --dir samples --llm-cache parity-llm-cache.json

# replay run, no key, no network
parity run --dir samples --replay --llm-cache parity-llm-cache.json
```

- In replay mode the cache always answers first. A call that was never recorded raises `CacheMissError`, the query becomes `NOT_COMPARABLE` with a `replay cache miss` note, and the run continues so you see every miss at once.
- Replay never touches the network, so a reviewer can reproduce a run with zero API calls.
- The LLM usage section of the JSON summary shows calls, cache hits, cache hit rate, and token totals for the run. In replay, all hits come from cache and cost zero tokens.

## Tools

- `src/parity/gateway/json_cache.py`: one JSON file per workload holds every recorded call. Works on any machine.
- `src/parity/pipeline.py`: `run_pipeline(..., gateway=None)`. The gateway is optional and lives outside the engine.
- Environment: `PARITY_LLM_MODEL`, `PARITY_LLM_BASE_URL`, `PARITY_LLM_API_KEY`. The API key never sits in a file, in Git, or on the command line. In replay mode no key is needed.

## Known limit

The translator agent contract is "output only the Db2 SQL". A response with explanations breaks execution and marks the query `ERROR`. The prompts already make that contract.
