# Screenshots

Drop the captures for the submission here. Filenames referenced by the README:

| File | What to capture | Why it matters |
| --- | --- | --- |
| `01-results.png` | Results view after the "Widow, rural UP" sample: the four verdict groups, and the corpus counters in the header | Shows the product at a glance and that Db2 is live |
| `02-rule-trace.png` | One expanded scheme (NFSA or Sukanya) with observed value, requirement, verdict and clause reference | Shows the evidence model — this is the differentiator |
| `03-audit-record.png` | The audit drawer: run metadata, `decision_trace` rows, event log | Shows auditability |
| `04-db2-cli.png` | Output of `docker compose exec db2 su - db2inst1 -c "db2 connect to YOJANADB && db2 'select count(*) from schemes'"` | Proves the data really lives in Db2 |
| `05-tests.png` | `docker compose exec app python -m pytest tests -q` → `54 passed` | Proves the suite runs in the container |

Capture at 1440 px wide or more; keep the browser chrome out of the frame where
possible. PNG, not JPEG.
