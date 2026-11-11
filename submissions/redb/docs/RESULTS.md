# Measured results

Environment: Db2 Community Edition **v12.1.5.0** in Docker (`icr.io/db2_community/db2:latest`, linux/amd64),
4 vCPU / 15 GB host, offline mode (no Gemini key; deterministic heuristics). Numbers come from
`python -m redb setup --reset && python -m redb workload --repeat 10 && python -m redb analyze --approve-all`.
Latency is the **median of 5 timed runs after 1 warm-up, all rows fetched**, measured by reDB itself.

## Scale 1.0 (100k customers, 400k orders, 1.2M order items)

### Index consolidation (nothing built yet)

Db2's advisor (`RECOMMEND INDEXES`) suggested **8** indexes, one statement at a time. reDB priced subsets of
them on virtual indexes with `EVALUATE INDEXES` and kept **5** that retain ≥95% of the workload gain:

| Kept index | Serves | Est. cost now → with index set (timerons) | Est. size |
|---|---|---|---:|
| `ORDERS (STATUS, TOTAL_AMOUNT, ORDER_DATE, CUSTOMER_ID)` | W4, W7 | 3,621.5 → 588.4 | 16.7 MB |
| `ORDER_ITEMS (PRODUCT_ID, UNIT_PRICE, QUANTITY)` | W2 | 1,708.4 → 14.4 | 29.0 MB |
| `ORDERS (ORDER_DATE, CUSTOMER_ID)` | W3, W5 | 3,949.2 → 1,361.7 | 6.4 MB |
| `CUSTOMERS (SEGMENT, CUSTOMER_ID)` | W5 | 2,278.6 → 942.5 | 2.6 MB |
| `ORDERS (CUSTOMER_ID, ORDER_DATE, TOTAL_AMOUNT, STATUS, ORDER_ID)` | W1 | 806.5 → 7.1 | 18.8 MB (flagged: wide, 5 columns) |

Costs are summed over the statements (and candidate rewrites) each index serves. W6 (primary-key lookup,
14.1 timerons) is left alone. The planted unused index `IX_CUSTOMERS_SIGNUP_LEGACY` is found via
`MON_GET_INDEX` and proposed for a reversible drop.

### Measured after applying (run 2 of 2)

| Stmt | Before (ms) | After (ms) | Gain |
|---|---:|---:|---:|
| W7 | 60.2 | 16.9 | 71.9% |
| W2 | 33.9 | 0.3 | 99.2% |
| W4 | 21.4 | 6.2 | 71.3% |
| W5 | 20.4 | 6.6 | 67.6% |
| W3 | 17.0 | 4.2 | 75.3% |
| W1 | 13.2 | 0.3 | 97.9% |
| W6 (control) | 0.3 | 0.3 | noise |
| **Total** | **166.4** | **34.7** | **79.2%** |

Run 1: 165.9 → 40.3 ms (75.7%). Sub-millisecond statements are within timing noise.

### Rewrites: proven, then accepted or rejected on the numbers

| Stmt | Rewrite | Equivalence (EXCEPT ALL both ways) | EXPLAIN cost | Measured alone | Verdict |
|---|---|---|---|---|---|
| W7 | `UNION` of two scans → one `SELECT DISTINCT … IN (…)` | 0 / 0 differing rows | 1,655.8 → 811.4 | 60.2 → 36.8 ms | **adopted** |
| W3 | `YEAR()/MONTH()` → half-open date range | 0 / 0 differing rows | 836.5 → 834.1 | 17.0 → 16.7 ms | rejected: no gain |
| W5 | `NOT IN` → `NOT EXISTS` | 0 / 0 differing rows | 1,139.3 → 1,139.3 | 20.4 → 21.1 ms | rejected: no gain |

Db2 12.1's optimizer already turns the `NOT IN` on NOT NULL columns into an anti-join and handles the
date predicates, so those textbook rewrites buy nothing here. The prove step requires **equivalent AND
(plan ≥5% cheaper and not slower, or ≥25% faster measured)**, so reDB refused to "fix" them.

## Scale 10 (1M customers, 4M orders, 12M order items)

`python -m redb setup --scale 10 --reseed` generated 17 million rows inside Db2 in **83 seconds**.
Same commands, one run:

| Stmt | Before (ms) | After (ms) | Gain |
|---|---:|---:|---:|
| W7 | 782.0 | 164.7 | 78.9% |
| W2 | 391.1 | 0.6 | 99.8% |
| W5 | 268.3 | 78.7 | 70.7% |
| W3 | 197.3 | 106.0 | 46.3% |
| W4 | 186.0 | 1.3 | 99.3% |
| W1 | 164.9 | 0.3 | 99.8% |
| W6 (control) | 0.6 | 0.3 | noise |
| **Total** | **1,990.2** | **351.8** | **82.3%** |

- Consolidation: the advisor suggested **9** indexes, reDB kept **5** (the same five as at scale 1).
- The W7 rewrite alone took the statement from 782.0 to 422.8 ms (plan cost 16,441 → 8,059 timerons) and was
  adopted; the W3 and W5 rewrites were again proven equivalent and rejected (197.3 → 192.4 ms, 268.3 → 267.0 ms).
- Because this run followed the bulk load in the same database activation, `MON_GET_TABLE` showed real write
  activity, and the write-cost warning fired on its own: the 289.5 MB `ORDER_ITEMS` index was flagged
  "write-heavy table (20% of row activity is writes)". Estimated index sizes ranged from 25.5 MB to 289.5 MB.
