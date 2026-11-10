# Screenshots

Take these from the running app against a real Db2 (after `python -m time_machine reset-demo`, an injected fault and an investigation), and save them in this folder with these exact names so the README links resolve:

| File | What to capture |
|---|---|
| `01-ui-home.png` | Top of the UI with the Db2 and LLM status pills and the agent pipeline |
| `02-agents-retry.png` | Pipeline after a run, showing a rejected hypothesis, the retry banner and the confirmed hypothesis |
| `03-report.png` | The incident report: banner, KPI cards, time-travel chart, root cause and timeline |
| `04-audit-log.png` | The "Db2 audit log" tab |
| `05-db2-history.png` | A Db2 CLI query on `ORDER_ITEMS_HISTORY` or `SYSCAT.TABLES` (proves the temporal table is real) |
