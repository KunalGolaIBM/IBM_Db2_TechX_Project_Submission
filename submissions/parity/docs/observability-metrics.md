# Observability metrics

## What it does

Every JSON summary carries a `metrics` object computed from the report entries. Nothing is sampled and nothing is guessed.

## Numbers

- `queries_total`: queries in the run.
- `match_rate`, `mismatch_rate`, `error_rate`, `not_comparable_rate`: shares of the total.
- `high_risk_count` and `avg_risk`: from the risk scoring formula.
- `cost_per_query_tokens`: total model tokens for the run divided by the number of queries. Zero when no gateway was used.

An empty run reports zeros instead of failing.

## Known limit

Fix rate is not tracked yet. Agent re-proven fixes will feed it in a later branch. The note in every metrics object says so.
