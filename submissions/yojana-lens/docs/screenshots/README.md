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

## Preview captures (Db2 stubbed)

`preview-1-results.png`, `preview-2-rule-trace.png` and `preview-3-audit.png` are
UI previews captured before the Docker/Db2 path was available. They run the real
LangGraph agent and the real rule engine over `data/schemes.json`, with only the
four Db2 calls replaced by in-memory stand-ins; the interface carries a banner
that says so. They are **not** the submission captures — replace them with the
five files above once `docker compose up --build` has been run end to end.

