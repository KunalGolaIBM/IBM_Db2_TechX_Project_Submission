# Demo video script (about 2 minutes)

Record the browser at http://127.0.0.1:8000 (screen capture), speak over it.

| Time | Show | Say |
|---|---|---|
| 0:00 | Header and empty UI | "When a business number looks wrong, finding out why takes days. Db2 already keeps the history. Db2 Time Machine uses it." |
| 0:15 | Click **Reset demo data** | "I load orders into a Db2 system-period temporal table and take a KPI snapshot, like a nightly dashboard." |
| 0:25 | Click **Silent price change** | "Now a nightly batch silently changes a price from 500 to 50, in one SQL transaction." |
| 0:35 | Ask: *Why did Aurora Laptop revenue drop since this morning?* then **Investigate** | "A text-to-SQL tool would just report the lower number. Watch the agents instead." |
| 0:45 | Pipeline running, first hypothesis rejected, retry banner | "The Detective guesses deleted rows. The Verifier tests it against Db2 and rejects it. The LangGraph loop goes back with the evidence." |
| 1:05 | Confirmed hypothesis, banner | "Silent price change is confirmed: it explains the drop." |
| 1:15 | KPI cards, chart, root-cause card | "Revenue before and after come from two FOR SYSTEM_TIME AS OF queries. The chart is one AS OF query per point. Who: nightly_batch. When: 10:00. Which transaction. How many rows." |
| 1:35 | Open **Evidence queries**, then **Db2 audit log** | "Every number is reproducible with these read-only queries, and every agent step is logged in a Db2 table." |
| 1:50 | Click a past investigation | "Reports are stored in Db2, so past incidents can be reopened." |
| 1:55 | Optional: terminal with `pytest` | "50+ tests cover the guard, diff engine, agents and API." |
