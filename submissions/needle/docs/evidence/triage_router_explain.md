# TRIAGE search depth per user (RCAC router) and the plans it produces (bm25 agent)

Date: 2026-11-09 ~20:40 CST. Db2 12.1.5.0, VECDB, RCAC active on ADV_DOC / POSTING (sql/04_rcac.sql), 27 embargoed
advisories. Code: `src/needle/triage.py` (`depth_for_visibility`, `choose_depth`, `call_triage_ex`), router rule from
`src/needle/rcac.py` (`choose_strategy`, rcac agent). Tests: `tests/test_triage_router.py` (11 passed).
Full db2exfmt output: `docs/evidence/explain/router/*.exfmt.txt`.

## Rule

Under RCAC every plan carries the row permission with one filter factor (FF 0.495 for every user,
docs/evidence/rcac_real.md), and Db2 sizes the vector IXSCAN at depth / FF. Depth 50 (~101 candidates) keeps the
vector index; at depth 100 Db2 already switches to an exact table scan, and FETCH APPROX FIRST 99/100 raised SQL0901N
on one query (docs/evidence/eval_sql0901n_fetch_approx.md). So TRIAGE uses two depths only:

| Router (`choose_strategy`, k = 10) | TRIAGE depth | Plan of the vector leg |
|---|---|---|
| APPROX with depth <= 50 (high visibility) | 50 (`approx-index`) | IXSCAN VECIDX ADV_DOC_VIX (ANN) |
| EXACT, or APPROX deeper than 50 (low visibility) | max(128, 2k) (`deep-exact`) | TBSCAN ADV_DOC (exact scan, full recall) |

`triage()` / `call_triage()` default `depth=None` -> this rule; an explicit integer depth still overrides it.
Visibility = `COUNT(*)` on NEEDLE.ADV_DOC as the session user (RCAC applies) and SYSCAT.TABLES.CARD, read once and
cached on the connection object. `TriageResult.depth` is the depth that answered; `TriageResult.depth_choice` holds
user, visible rows, router decision and reason (for the UI line "search depth chosen for your visibility: N").

## Measured per user (through the PC tunnel, k = 10, 3 HYBRID queries each)

```
NDL_SENIOR  visible= 26210/26210 frac=1.000 router=APPROX 50 -> depth 50 (approx-index); lookup 234 ms; HYBRID rows for 3 queries [10, 10, 10]
NDL_JUNIOR  visible= 26183/26210 frac=0.999 router=APPROX 50 -> depth 50 (approx-index); lookup 250 ms; HYBRID rows for 3 queries [10, 10, 10]
NDL_P75     visible= 19630/26210 frac=0.749 router=APPROX 50 -> depth 50 (approx-index); lookup 232 ms; HYBRID rows for 3 queries [10, 10, 10]
NDL_P50     visible= 12999/26210 frac=0.496 router=APPROX 100 -> depth 128 (deep-exact); lookup 204 ms; HYBRID rows for 3 queries [10, 10, 10]
NDL_P25     visible=  6570/26210 frac=0.251 router=EXACT 10 -> depth 128 (deep-exact); lookup 210 ms; HYBRID rows for 3 queries [10, 10, 10]
NDL_P10     visible=  2616/26210 frac=0.100 router=EXACT 10 -> depth 128 (deep-exact); lookup 222 ms; HYBRID rows for 3 queries [10, 10, 10]
```
"lookup" = the one-time visibility query per connection (two statements through the tunnel). Recall and latency of
TRIAGE per user at these depths: not measured here (UNKNOWN); the rcac agent's sweep measures the vector leg.

## Plans

Method: (1) `EXPLAIN PLAN FOR` the exact HYBRID statement text that NEEDLE.TRIAGE_MODE builds (k = 10) at depth 50 and
128, as DB2INST1 (`r_plan_d50`, `r_plan_d128`); (2) after the users above ran TRIAGE, the cached sections of those two
statement texts were read from `MON_GET_PKG_CACHE_STMT` (package `P1279080158` = TRIAGE_MODE) and formatted with
`EXPLAIN_FROM_SECTION` + db2exfmt (`r_section_d50_1..3`, `r_section_d128_1..3`). Each text had 3 cached sections;
all 3 have the same plan. db2exfmt does not show which user compiled a section; the attribution is by depth (the
router gives depth 50 to NDL_SENIOR / NDL_JUNIOR / NDL_P75 and depth 128 to NDL_P50 / NDL_P25 / NDL_P10, as measured
above and asserted by `test_router_depth_per_user`). Assumption (not verified): one section per user, because the
default schema differs per user.

Depth 50 (executed section, NDL_SENIOR's depth), vector leg:
```
>HSJOIN<(4) <- 50 TBSCAN(5) <- SORT(6) <- TBSCAN(7) <- SORT(8) <- 50.49 NLJOIN(9)
     NLJOIN(9) outer: FETCH(10) USER_ACCESS <- IXSCAN(11)            [the permission's SESSION_USER lookup]
     NLJOIN(9) inner: 50.49 FETCH(12) TABLE NEEDLE.ADV_DOC <- 102 IXSCAN(13) <- VECIDX: NEEDLE.ADV_DOC_VIX
total cost 6354.3
```

Depth 128 (executed section, NDL_P10's depth), vector leg:
```
>HSJOIN<(4) <- 128 TBSCAN(39) <- SORT(40) <- TBSCAN(41) <- SORT(42) <- 12973.9 NLJOIN(43)
     NLJOIN(43) outer: FETCH(44) USER_ACCESS <- IXSCAN(45)
     NLJOIN(43) inner: 26210 TBSCAN(46) TABLE NEEDLE.ADV_DOC        [exact scan; no vector index]
total cost 9041.9
```
The keyword leg (right / left input of `>HSJOIN<(4)`) is the same in both: recursive term walk, TERM_DF, index-only
POSTING_PK_IX, GRPBY. EXPLAIN PLAN as DB2INST1 gives the same operators and total costs (6354.3 / 9041.9).

## Reading

- High-visibility users keep ANN through the vector index (depth 50 -> IXSCAN est. 102 candidates, ~50 after the
  permission). Before this change the default depth was 100, and under RCAC n = 100 runs a TBSCAN (rcac agent,
  rcac_real.md finding 5: "RCAC n = 50 IXSCAN (est. 102), n = 100 and 200 TBSCAN"; not re-measured here).
- Low-visibility users get the exact scan on purpose: with FF fixed at 0.495, an ANN leg would return only about
  k x fraction / 0.495 visible rows (under-fill, rcac_real.md), and the deep depth avoids that.
- The app's retriever (`src/needle/retriever.py`, app agent) still passes an explicit depth (default 50) to
  `call_triage`; it uses this rule only if it passes `depth=None`.
