# Scale benchmark: the same schema at 1,000,000 reservations

Run 2026-11-10 09:41 UTC on DB2 v12.1.5.0 (Docker on a laptop, WSL2) · **1,000,000 reservations**, 12,000 rooms, 200,000 guests, loaded inside Db2 in 41 s · statistics collected in 1 s · no LLM.

The schema is built from the project's own `01_schema.sql` and `04_extensions.sql` in a separate schema (`HOTELSCALE`), so the views, temporal tables, MQT and the hash-chain trigger are exactly the ones the copilot uses. Timings are medians of repeated runs after one warm-up. Reproduce with `python src/benchmark_scale.py`.

| What | Measured | Note |
|---|---|---|
| EXPLAIN cost guard: the agent's "occupancy tonight" query | 142,782 timerons | REFUSED by the 25,000-timeron guard |
| EXPLAIN cost guard: a runaway self cross join | 79,160,287,232 timerons | refused before it runs |
| Same "occupancy tonight" question asked of the MQT | 71 timerons | passes the guard: at scale the agent should read KPIs from the MQT |
| 30-night KPI history from the live view | 221 ms | aggregates every reservation |
| Same 30 nights from the MQT | 0.4 ms | **506× faster**; `REFRESH TABLE` took 2.8 s |
| Mass update with automatic history | 38,512 row versions in 2.1 s | Db2 writes `RESERVATIONS_HISTORY` itself, no triggers |
| Time travel: confirmed arrivals next 14 days `AS OF` before the change | 19 ms | answers 45,408 from history |
| Change feed (before/after pairs from history) | 210 ms | 38,512 changes paired |
| Audit steps hash-chained by the trigger | 50,000 steps in 17 s | 2,960 steps/s including SHA-256 per row |
| Verify the whole hash chain inside Db2 (`LAG()` + `HASH`) | 304 ms | intact |
