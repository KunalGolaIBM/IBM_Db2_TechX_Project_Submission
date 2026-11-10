# Agent fix loop

## What it does

A mismatch goes to the Diagnostician, then to the Fixer, and every proposed fix runs on both databases. A fix is accepted only when the engine proves it matches. The agent never decides.

```bash
parity run --dir samples --fix-loop --bridge
```

## The rules of the loop

1. Only a mismatch starts the loop. A match has nothing to fix.
2. The Diagnostician sees the source SQL and the first differences. It returns a hypothesis in one sentence.
3. The Fixer sees the hypothesis and the current Db2 SQL. It returns Db2 SQL.
4. The candidate runs on the source and on Db2, and the engine compares the results. The table name is quoted the same way as the rule path.
5. A matching result ends the loop with status FIXED. The report shows the fixed SQL and the hypothesis.
6. After three tries the query is flagged NEEDS_HUMAN with the hypothesis and the number of tries. The mismatch is never hidden.
7. Without a gateway the loop is skipped and the mismatch stands. A wrong guess must never replace a real difference.

## The demo without an API key

`scripts/fake_model_server.py` speaks the OpenAI chat completion shape, so the real gateway transport talks to it with no change and no network.

```bash
python scripts/fake_model_server.py --port 8099
```

In another shell:

```bash
export PARITY_LLM_BASE_URL=http://127.0.0.1:8099/v1
export PARITY_LLM_MODEL=demo-model
export PARITY_LLM_API_KEY=demo
parity run --dir samples --fix-loop --bridge
```

The fake model explains the blank value rule and rewrites the filter on an empty string into a filter on the length. The engine proves the rewrite on both real databases and the query turns from MISMATCH into MATCH.

With a real key the same code path runs against the real model. Nothing else changes.

## What the loop leaves behind

A fixed query is recorded with the rules that fired. The capture step stores it as a candidate, a human approves it, and the next run can search for it. See docs/kb-capture.md.

## Known limits

- The loop fixes one query at a time. A run with many mismatches makes many model calls.
- The fix is proved on the data that is in the databases right now. A fix that only works for that data is still a real risk, so the human review step stays.
- The agent failure path keeps the mismatch and reports the failure. It never guesses.
