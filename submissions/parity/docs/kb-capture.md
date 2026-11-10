# Knowledge base capture

## What it does

A run that matched proves that a translation works. The capture step keeps that proof, so the next run can reuse it instead of learning it again.

This is the learning loop of the roadmap: find a difference, fix it, prove the fix, and remember the lesson.

## The loop

```bash
parity run --dir samples --history parity-history.json --bridge
parity kb-capture --history parity-history.json --store db2
parity kb-review --action list --store db2
parity kb-review --action approve --title "alias_expressions 04091a: SELECT AVG(credit_limit) FROM customers" --store db2
```

1. The run writes its outcome into the history file, including the rules that fired.
2. The capture reads the run and stores every proven rewrite as a candidate.
3. A human lists the candidates and approves the good ones.
4. An approved entry is served by search, so the next fix can start from it.

## What becomes a candidate

Only a query that matched **and** was rewritten. A query that matched without a rewrite teaches nothing, and a query that failed proves nothing.

Each candidate holds:

- the title, built from the rule names and a short hash, so the same lesson is never stored twice
- the source pattern and the Db2 pattern
- the cause, which names the rules that fired
- the fix template, which is the Db2 SQL
- the run id that proved it

A candidate is never served by search. It only becomes searchable after a human approves it.

## Live result

A run of the 129 query sample workload produced 67 candidates. After approving one, a search for "average of the credit limit" returned that entry with its source pattern and its fix, and the entry kept the proof run id.

## Known limits

- The capture stores what the translator proved. A fix that came from the agent loop is captured the same way, because the run record says which rules fired and an agent fix has its own name, `agent_fix`.
- One candidate per title. Two queries with the same rules and the same text are one lesson.
