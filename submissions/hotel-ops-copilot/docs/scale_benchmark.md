# Scale benchmark: the same schema at 1,000,000 reservations

Run 2026-11-14 04:35 UTC on DB2 v12.1.5.0 (Docker on a laptop, WSL2) · **1,000,000 reservations**, 40 hotels, 12,000 rooms, 200,000 guests, loaded inside Db2 in 46 s · statistics collected in 1 s · no LLM.

The schema is built from the project's own `01_schema.sql` and `04_extensions.sql` in a separate schema (`HOTELSCALE`), so the views, temporal tables, MQT and the hash-chain trigger are exactly the ones the copilot uses. Timings are medians of repeated runs after one warm-up. Reproduce with `python src/benchmark_scale.py`.

The last four rows switch on the same property row permissions as `03_security.sql` and connect as the agent identity, scoped to one hotel of the group. Rewriting the permission so the role test runs once per query (an uncorrelated `UNION ALL` subquery) did not change the timings at 200,000 reservations (agent 109 vs 141 ms, manager 5.0 vs 5.3 s): the cost comes from applying the permission inside the KPI view's correlated subqueries, which is why group-wide history should come from `MQT_DAILY_KPIS`.

| What | Measured | Note |
|---|---|---|
| EXPLAIN cost guard: the agent's "occupancy tonight" query | 809,270 timerons | REFUSED by the 25,000-timeron guard |
| EXPLAIN cost guard: a runaway self cross join | 79,160,287,232 timerons | refused before it runs |
| Same "occupancy tonight" question asked of the MQT | 1,298 timerons | passes the guard: at scale the agent should read KPIs from the MQT |
| 30-night KPI history from the live view | 1,676 ms | aggregates every reservation |
| Same 30 nights from the MQT | 4.6 ms | **362× faster**; `REFRESH TABLE` took 16.8 s |
| Mass update with automatic history | 38,512 row versions in 3.1 s | Db2 writes `RESERVATIONS_HISTORY` itself, no triggers |
| Time travel: confirmed arrivals next 14 days `AS OF` before the change | 26 ms | answers 45,408 from history |
| Change feed (before/after pairs from history) | 230 ms | 38,512 changes paired |
| Audit steps hash-chained by the trigger | 50,000 steps in 17 s | 2,985 steps/s including SHA-256 per row |
| Verify the whole hash chain inside Db2 (`LAG()` + `HASH`) | 306 ms | intact |
| Hotel group: row permissions on 4 tables (`ROOM_TYPES`, `ROOMS`, `RESERVATIONS`, `RATE_PLAN`) | activated in 0.1 s | 40 hotels; the agent identity is scoped to hotel 7 in `AGENT_SCOPE` |
| Reservations the hotel's agent can see | 25,000 of 1,000,000 | only its own hotel (1 of 40 hotels visible, 0 rows of the others) |
| Agent: 30-night KPI history, filtered by Db2 RCAC | 135 ms | identical figures to the manager's query with `WHERE PROPERTY_ID = 7` (48 ms without RCAC) |
| Manager: group-wide 30-night KPI history, before → after RCAC | 1,838 → 5,244 ms | managers pass the permission's role test and still see every hotel |
