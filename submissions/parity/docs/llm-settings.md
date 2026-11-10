# LLM settings

## What it does

`LlmSettings` in `src/parity/config.py` is the only place that reads model settings. The CLI, the pipeline, and the gateway all use it. No other code touches the environment for LLM values.

## Environment

- `PARITY_LLM_MODEL`: the model name. Defaults to `recorded-model`.
- `PARITY_LLM_BASE_URL`: the OpenAI compatible base URL. Defaults to `http://localhost`.
- `PARITY_LLM_API_KEY`: the API key. No default. It is never written to a file or printed.

## Rules

- The model name must not be empty.
- The base URL must start with `http://` or `https://`.
- A live run requires an API key. With `--llm-cache` or `--replay`, a missing key means replay only, and the CLI says so instead of failing in the middle of a run.
- `parity replay` needs no key at all.

A settings error fails before any database work starts, with the variable name in the message.
