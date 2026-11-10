Db2 DB2 v12.1.5.0 | NEEDLE.ADV_DOC | k=10 | queries=170 (dev 81, heldout 89) | stats [['ADV_DOC', '26210', '2026-11-10 01:31:23.968119'], ['USER_ACCESS', '7', '2026-11-10 01:46:42.280438']] | auto_runstats=OFF

### Line-for-line: plain WHERE (DB2INST1, before RCAC) vs RCAC user, FETCH APPROX FIRST 10 (all queries)

| visible | WHERE literal: recall / rows / under-fill | plan (literal) | FF literal | WHERE subquery: recall / rows | plan (subquery) | RCAC user | RCAC: recall / rows / under-fill | RCAC plan (shared text) | FF permission | leaks |
|---|---|---|---|---|---|---|---|---|---|---|
| 10% (2616 rows) | 0.682 / 7.77 / 0.62 | IXSCAN VECIDX; L=90; est=85 | 0.1179 | 0.206 / 2.06 | IXSCAN VECIDX; L=50; est=21 | NDL_P10 | 0.205 / 2.05 / 1.00 | IXSCAN VECIDX; L=50; est=21 | 0.495 | 0 |
| 25% (6570 rows) | 0.787 / 8.49 / 0.46 | IXSCAN VECIDX; L=60; est=39 | 0.2585 | 0.503 / 5.08 | IXSCAN VECIDX; L=50; est=21 | NDL_P25 | 0.502 / 5.08 / 0.97 | IXSCAN VECIDX; L=50; est=21 | 0.495 | 0 |
| 50% (13001 rows) | 0.850 / 9.02 / 0.36 | IXSCAN VECIDX; L=50; est=21 | 0.4963 | 0.850 / 9.02 | IXSCAN VECIDX; L=50; est=21 | NDL_P50 | 0.848 / 9.00 / 0.36 | IXSCAN VECIDX; L=50; est=21 | 0.495 | 0 |
| 75% (19632 rows) | 0.910 / 9.42 / 0.31 | IXSCAN VECIDX; L=50; est=14 | 0.7489 | 0.952 / 9.99 | IXSCAN VECIDX; L=50; est=21 | NDL_P75 | 0.952 / 9.99 / 0.01 | IXSCAN VECIDX; L=50; est=21 | 0.495 | 0 |
| 100% (26210 rows) | 0.950 / 10.00 / 0.00 | IXSCAN VECIDX; L=50; est=10 | n/a | n/a / n/a | n/a | NDL_SENIOR | 0.950 / 10.00 / 0.00 | IXSCAN VECIDX; L=50; est=21 | 0.495 | 0 |

### RCAC users: depth and search-list levers (recall / mean rows / under-fill rate / p50 ms; all queries)

| condition | plan as DB2INST1 | NDL_P10 | NDL_P25 | NDL_P50 | NDL_P75 | NDL_SENIOR |
|---|---|---|---|---|---|---|
| approx10 | IXSCAN VECIDX; L=50; est=21 | 0.205 / 2.0 / 1.00 / 2.1 | 0.502 / 5.1 / 0.97 / 2.1 | 0.848 / 9.0 / 0.36 / 2.1 | 0.952 / 10.0 / 0.01 / 3.0 | 0.950 / 10.0 / 0.00 / 2.4 |
| approx25 | IXSCAN VECIDX; L=68; est=51 | 0.493 / 5.2 / 0.94 / 3.3 | 0.857 / 12.8 / 0.21 / 2.6 | 0.953 / 23.5 / 0.00 / 2.7 | 0.973 / 25.0 / 0.00 / 3.9 | 0.971 / 25.0 / 0.00 / 3.1 |
| approx50 | IXSCAN VECIDX; L=102; est=102 | 0.729 / 10.3 / 0.44 / 3.5 | 0.944 / 25.8 / 0.00 / 3.5 | 0.978 / 48.1 / 0.00 / 3.7 | 0.984 / 50.0 / 0.00 / 4.7 | 0.978 / 50.0 / 0.00 / 4.6 |
| approx100 | no vector index (TBSCAN); L=n/a; est=n/a | 1.000 / 100.0 / 0.00 / 18.1 | 1.000 / 100.0 / 0.00 / 36.4 | 1.000 / 100.0 / 0.00 / 69.8 | 1.000 / 100.0 / 0.00 / 104.4 | 1.000 / 100.0 / 0.00 / 131.3 |
| approx200 | no vector index (TBSCAN); L=n/a; est=n/a | 1.000 / 200.0 / 0.00 / 17.9 | 1.000 / 200.0 / 0.00 / 37.1 | 1.000 / 200.0 / 0.00 / 67.8 | 1.000 / 200.0 / 0.00 / 112.8 | 1.000 / 200.0 / 0.00 / 140.6 |
| approx10_L50 | IXSCAN VECIDX; L=50; est=21 | 0.205 / 2.0 / 1.00 / 2.5 | 0.502 / 5.1 / 0.97 / 2.1 | 0.848 / 9.0 / 0.36 / 2.1 | 0.952 / 10.0 / 0.01 / 3.1 | 0.950 / 10.0 / 0.00 / 2.4 |
| approx25_L75 | IXSCAN VECIDX; L=75; est=51 | 0.497 / 5.2 / 0.93 / 4.0 | 0.872 / 12.8 / 0.19 / 2.7 | 0.959 / 23.5 / 0.00 / 2.8 | 0.974 / 25.0 / 0.00 / 3.4 | 0.971 / 25.0 / 0.00 / 4.1 |
| approx50_L150 | IXSCAN VECIDX; L=150; est=102 | 0.801 / 10.1 / 0.46 / 4.5 | 0.973 / 25.3 / 0.01 / 4.4 | 0.988 / 47.7 / 0.00 / 6.4 | 0.991 / 50.0 / 0.00 / 5.6 | 0.988 / 50.0 / 0.00 / 5.4 |
| approx100_L300 | no vector index (TBSCAN); L=n/a; est=n/a | 1.000 / 100.0 / 0.00 / 22.5 | 1.000 / 100.0 / 0.00 / 41.1 | 1.000 / 100.0 / 0.00 / 73.5 | 1.000 / 100.0 / 0.00 / 109.8 | 1.000 / 100.0 / 0.00 / 137.0 |
| approx200_L600 | no vector index (TBSCAN); L=n/a; est=n/a | 1.000 / 200.0 / 0.00 / 21.9 | 1.000 / 200.0 / 0.00 / 42.0 | 1.000 / 200.0 / 0.00 / 72.7 | 1.000 / 200.0 / 0.00 / 123.7 | 1.000 / 200.0 / 0.00 / 134.8 |
| approx10_L200 | IXSCAN VECIDX; L=200; est=21 | 0.206 / 2.1 / 1.00 / 4.8 | 0.507 / 5.1 / 0.96 / 4.9 | 0.892 / 8.9 / 0.39 / 6.8 | 0.995 / 10.0 / 0.01 / 8.1 | 0.997 / 10.0 / 0.00 / 5.1 |
| exact | no vector index (TBSCAN); L=n/a; est=n/a | 1.000 / 10.0 / 0.00 / 16.6 | 1.000 / 10.0 / 0.00 / 36.2 | 1.000 / 10.0 / 0.00 / 66.8 | 1.000 / 10.0 / 0.00 / 109.8 | 1.000 / 10.0 / 0.00 / 145.8 |

### Oracle and identity checks

| user | SESSION_USER, CURRENT USER | visible rows | visible fraction | user EXACT == admin EXACT + explicit WHERE |
|---|---|---|---|---|
| NDL_P10 | ['NDL_P10', 'NDL_P10'] | 2616 | 0.0998 | 170 / 170 |
| NDL_P25 | ['NDL_P25', 'NDL_P25'] | 6570 | 0.2507 | 170 / 170 |
| NDL_P50 | ['NDL_P50', 'NDL_P50'] | 13001 | 0.496 | 170 / 170 |
| NDL_P75 | ['NDL_P75', 'NDL_P75'] | 19632 | 0.749 | 170 / 170 |
| NDL_SENIOR | ['NDL_SENIOR', 'NDL_SENIOR'] | 26210 | 1.0 | 170 / 170 |

### Router on the held-out split only (config fitted on dev: {'T': 7000, 'm': 3.0, 'depths': [10, 25, 50, 100, 200], 'guideline': True, 'fitted_on': 'dev split only (see router_fit)', 'evaluated_on': 'heldout split'})

| user | choice | recall@10 | mean rows | under-fill | EXACT fallbacks | errors | p50 ms | p95 ms | leaks | APPROX 10 on the same queries: recall / rows |
|---|---|---|---|---|---|---|---|---|---|---|
| NDL_P10 | EXACT 10 | 1.000 | 10.00 | 0.00 | 0 | 0 | 16.3 | 18.1 | 0 | 0.208 / 2.08 |
| NDL_P25 | EXACT 10 | 1.000 | 10.00 | 0.00 | 0 | 0 | 36.3 | 42.7 | 0 | 0.506 / 5.09 |
| NDL_P50 | APPROX 100, L=300 | 1.000 | 10.00 | 0.00 | 0 | 0 | 78.5 | 93.1 | 0 | 0.852 / 9.16 |
| NDL_P75 | APPROX 50, L=150 | 0.988 | 10.00 | 0.00 | 0 | 0 | 7.3 | 10.7 | 0 | 0.947 / 9.99 |
| NDL_SENIOR | APPROX 50, L=150 | 0.987 | 10.00 | 0.00 | 0 | 0 | 7.2 | 8.8 | 0 | 0.948 / 10.00 |

### Package cache after each user (FLUSH PACKAGE CACHE DYNAMIC before each order)

| order | after user | cache entries | executable_id (last 16 hex) | executions | +rows_read | +rows_returned |
|---|---|---|---|---|---|---|
| forward | NDL_P10 | 1 | 1110015942020530 | 10 (+10) | 35226 | 28 |
| forward | NDL_P25 | 1 | 1110015942020530 | 20 (+10) | 35226 | 53 |
| forward | NDL_P50 | 1 | 1110015942020530 | 30 (+10) | 35226 | 90 |
| forward | NDL_P75 | 1 | 1110015942020530 | 40 (+10) | 35226 | 100 |
| forward | NDL_SENIOR | 1 | 1110015942020530 | 50 (+10) | 35226 | 100 |
| forward | distinct executable ids | 1 | | | | |
| reverse | NDL_SENIOR | 1 | 1110015943844308 | 10 (+10) | 35226 | 100 |
| reverse | NDL_P75 | 1 | 1110015943844308 | 20 (+10) | 35226 | 100 |
| reverse | NDL_P50 | 1 | 1110015943844308 | 30 (+10) | 35226 | 90 |
| reverse | NDL_P25 | 1 | 1110015943844308 | 40 (+10) | 35226 | 53 |
| reverse | NDL_P10 | 1 | 1110015943844308 | 50 (+10) | 35226 | 28 |
| reverse | distinct executable ids | 1 | | | | |

### NEEDLE.TRIAGE_MODE(..., 'VEC') as each user, k = 10, 20 G1 queries

| user | depth 10: mean rows / queries < 10 | depth 100: mean rows / queries < 10 |
|---|---|---|
| NDL_P10 | 2.2 / 20 | 10.0 / 0 |
| NDL_P25 | 5.4 / 19 | 10.0 / 0 |
| NDL_P50 | 9.1 / 8 | 10.0 / 0 |
| NDL_P75 | 10.0 / 0 | 10.0 / 0 |
| NDL_SENIOR | 10.0 / 0 | 10.0 / 0 |

TRIAGE fused HYBRID statement, hybrid_depth10: IXSCAN VECIDX; L=50; est=21; operators ['1:RETURN', '2:TBSCAN', '3:SORT', '4:HSJOIN', '5:FILTER', '6:TBSCAN', '7:SORT', '8:FILTER', '9:GRPBY', '10:TBSCAN', '11:SORT', '12:HSJOIN', '13:NLJOIN', '14:FETCH', '15:IXSCAN', '16:IXSCAN', '17:NLJOIN', '18:NLJOIN', '19:TBSCAN', '20:TBSCAN', '21:TBSCAN', '22:TEMP', '23:TBSCAN', '24:SORT', '25:HSJOIN', '26:TBSCAN', '27:TBSCAN', '28:SORT', '29:TBSCAN', '30:TEMP', '31:UNION', '32:TBSCAN', '33:TBSCAN', '34:TBSCAN', '35:SORT', '36:TBSCAN', '37:SORT', '38:NLJOIN', '39:FETCH', '40:IXSCAN', '41:FETCH', '42:IXSCAN']

TRIAGE fused HYBRID statement, hybrid_depth100: no vector index (TBSCAN); L=n/a; est=n/a; operators ['1:RETURN', '2:TBSCAN', '3:SORT', '4:HSJOIN', '5:FILTER', '6:TBSCAN', '7:SORT', '8:FILTER', '9:GRPBY', '10:TBSCAN', '11:SORT', '12:HSJOIN', '13:NLJOIN', '14:FETCH', '15:IXSCAN', '16:IXSCAN', '17:NLJOIN', '18:NLJOIN', '19:TBSCAN', '20:TBSCAN', '21:TBSCAN', '22:TEMP', '23:TBSCAN', '24:SORT', '25:HSJOIN', '26:TBSCAN', '27:TBSCAN', '28:SORT', '29:TBSCAN', '30:TEMP', '31:UNION', '32:TBSCAN', '33:TBSCAN', '34:TBSCAN', '35:SORT', '36:TBSCAN', '37:SORT', '38:NLJOIN', '39:FETCH', '40:IXSCAN', '41:TBSCAN']
