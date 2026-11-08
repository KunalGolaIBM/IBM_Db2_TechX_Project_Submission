# Metric Semantics

Registry version: all metrics `1.0.0`. Source of truth: [`backend/metricguard/core/registry.py`](../src/backend/metricguard/core/registry.py). `metricguard db init` copies it into `METRICGUARD.METRIC_DEFINITIONS` with a SHA-256 `DEFINITION_HASH` per metric.

The registry is **declarative**. It never stores SQL. SQL comes from the reviewed compiler (`core/compiler.py`), which only knows three base measures. If a metric definition changes, its hash changes, and the API will not mark answers `VERIFIED` until the approved row in Db2 matches again.

---

## 1. Shared rules

| Rule | Decision |
|---|---|
| Eligible orders | `ORDERS.STATUS = 'COMPLETED'` only. `CANCELLED` and `PENDING` orders are never revenue. |
| Revenue grain | Order line (`ORDER_ITEMS`). Line revenue = `QUANTITY * UNIT_PRICE - DISCOUNT_AMOUNT`. |
| Discounts | `DISCOUNT_AMOUNT` is a line total, not per unit. It reduces revenue. A 100%-discounted line contributes 0 and its order still counts. |
| Shipping and tax | Excluded from every metric. `SHIPPING_AMOUNT` is an order-header column. It is never aggregated after a join to lines. |
| Refunds counted | `REFUNDS.STATUS = 'PROCESSED'` only. `PENDING` and `REJECTED` are ignored. |
| Refunds on ineligible orders | Excluded. A cancelled order's payment reversal is not a "refund of revenue". |
| Partial refunds | Any number of processed refund rows per line. Their sum is capped at the line revenue (checked by DQ-02). Partial refunds reduce net revenue by exactly the refunded amount. |
| Refund attribution | **Cohort basis.** A refund is attributed to the *order date* of the refunded order, not to `REFUND_TS`. A January order refunded in February lowers January's net revenue. This keeps `refund_rate` meaningful, because numerator and denominator come from the same orders. Note that historical months can change as late refunds arrive. A cash-basis "refunds processed" metric is out of scope for v1. |
| Date attribution | UTC `ORDERS.ORDER_TS`. |
| Date ranges | Inclusive calendar dates `[start_date, end_date]`, executed as `ORDER_TS >= start 00:00:00 AND ORDER_TS < end_date + 1 day`. This includes `23:59:59.999999` on the last day, which `BETWEEN 'YYYY-MM-01' AND 'YYYY-MM-31'` misses. |
| Default date range | If a question names no period, the range is the data coverage `2026-01-01 … 2026-06-30`, reported as assumption `DEFAULT_DATE_RANGE`. |
| Rounding | Money is `DECIMAL(18,2)`. AOV is rounded half-up to 2 dp. Refund rate is a ratio rounded half-up to 6 dp (`0.077766` = 7.7766%). Sums are exact decimals with no floating point. |
| Join safety | Refunds are pre-aggregated **per order line** in a CTE before the left join to lines. A line with N refund rows is still one row, so there is no fan-out. Order counts use `COUNT(DISTINCT ORDER_ID)`. |
| Order count derivation | Counted from line facts. This is valid because every order has at least one line (DQ-01). |

## 2. Metric definitions

| Metric | Business meaning | Calculation | Unit | Additive | NULL handling |
|---|---|---|---|---|---|
| `gross_revenue` | Merchandise revenue charged on completed orders, after line discounts and before refunds | Σ line revenue | USD | yes | empty → `0.00` |
| `net_revenue` | Gross revenue minus processed refunds on the same orders | `gross_revenue − refund_amount` | USD | yes | lines without refunds count 0 refund; empty → `0.00` |
| `order_count` | Distinct completed orders | `COUNT(DISTINCT ORDER_ID)` | COUNT | yes | empty → `0` |
| `average_order_value` | Average gross revenue per completed order | `gross_revenue / order_count` | USD | no | `NULL` when `order_count = 0` |
| `refund_amount` | Money returned via processed refunds on completed orders | Σ processed refunds (per-line pre-aggregated) | USD | yes | empty → `0.00` |
| `refund_rate` | Share of gross revenue refunded (value-based, not order-based) | `refund_amount / gross_revenue` | RATIO | no | `NULL` when `gross_revenue = 0` |

## 3. Allowed dimensions and filters

| Metric | `order_month` | `region` | `channel` | `product_category` | Filters |
|---|:-:|:-:|:-:|:-:|---|
| gross_revenue | ✓ | ✓ | ✓ | ✓ | region, channel, product_category |
| net_revenue | ✓ | ✓ | ✓ | ✓ | region, channel, product_category |
| refund_amount | ✓ | ✓ | ✓ | ✓ | region, channel, product_category |
| refund_rate | ✓ | ✓ | ✓ | ✓ | region, channel, product_category |
| order_count | ✓ | ✓ | ✓ | ✗ | region, channel |
| average_order_value | ✓ | ✓ | ✓ | ✗ | region, channel |

**Why order-grain metrics cannot use `product_category`:** an order with lines in two categories would be counted in both groups. The category counts would then add up to more than the total order count, and per-category AOV would mean nothing. Such plans are `BLOCKED` with `DIMENSION_NOT_ALLOWED` or `FILTER_NOT_ALLOWED`.

Allowed values: region `NA, EMEA, APAC, LATAM` · channel `WEB, MOBILE, STORE, MARKETPLACE` · category `ELECTRONICS, HOME, APPAREL, BEAUTY, SPORTS`. Plans may use at most 2 dimensions and 4 metrics.

## 4. Dataset

Deterministic generator `backend/metricguard/seed/generator.py`, seed `20260107`.

| Table | Rows |
|---|---:|
| PRODUCTS | 40 |
| ORDERS | 2,924 (2,581 completed · 224 cancelled · 119 pending) |
| ORDER_ITEMS | 6,540 |
| REFUNDS | 1,032 (953 processed · 49 rejected · 30 pending) |

The dataset deliberately includes these traps:
- multi-line orders with multiple refund rows per line
- processed refunds on cancelled orders
- pending and rejected refunds
- pending orders (mostly late June)
- refunds dated in a later month than their order
- orders at `23:59:59` on a month end and at `00:00:00` on a month start
- 100%-discounted lines, and a $0 product
- order-level shipping
- nullable `PROMO_CODE` and `REASON_CODE`

## 5. Expected results (independently computed)

`backend/metricguard/seed/oracle.py` recomputes every metric from the generated Python objects with plain loops. It shares no code with the SQL compiler. `make db-verify` requires the Db2 result to equal the oracle **exactly**, digit for digit. The full set is in [`db/expected/expected_results.json`](../src/db/expected/expected_results.json).

### H1 2026 totals (2026-01-01 … 2026-06-30)

| gross_revenue | net_revenue | refund_amount | order_count | average_order_value | refund_rate |
|---:|---:|---:|---:|---:|---:|
| 667,622.16 | 615,704.13 | 51,918.03 | 2,581 | 258.67 | 0.077766 |

### By order month

| Month | Gross | Net | Refunds | Orders | AOV | Refund rate |
|---|---:|---:|---:|---:|---:|---:|
| 2026-01 | 102,699.31 | 95,931.95 | 6,767.36 | 394 | 260.66 | 0.065895 |
| 2026-02 | 90,874.91 | 84,776.81 | 6,098.10 | 361 | 251.73 | 0.067104 |
| 2026-03 | 117,078.14 | 109,725.04 | 7,353.10 | 426 | 274.83 | 0.062805 |
| 2026-04 | 109,079.70 | 98,382.98 | 10,696.72 | 448 | 243.48 | 0.098063 |
| 2026-05 | 123,832.83 | 115,794.10 | 8,038.73 | 491 | 252.21 | 0.064916 |
| 2026-06 | 124,057.27 | 111,093.25 | 12,964.02 | 461 | 269.10 | 0.104500 |

### Golden examples (also served by `GET /api/examples`)

| Example | Expected answer |
|---|---|
| ex-02 Q1 by region: gross / refunds / rate | APAC 69,291.82 / 5,040.25 / 0.072739 · EMEA 85,880.72 / 6,588.25 / 0.076714 · LATAM 28,756.06 / 1,467.35 / 0.051028 · NA 126,723.76 / 7,122.71 / 0.056207 |
| ex-03 Q2 by channel: AOV / orders | MARKETPLACE 257.20 / 140 · MOBILE 255.82 / 426 · STORE 269.84 / 207 · WEB 249.00 / 627 |
| ex-04 H1 category refund rate (desc) | SPORTS 0.087599 · ELECTRONICS 0.078763 · APPAREL 0.075580 · HOME 0.072883 · BEAUTY 0.064089 |
| ex-05 EMEA Q1 net / orders | 2026-01 25,347.46 / 114 · 2026-02 22,552.32 / 95 · 2026-03 31,392.69 / 130 |
| ex-06 March 2026 | 426 orders · AOV 274.83 · gross 117,078.14 |
| ex-07 Top-3 WEB categories by net, Q2 | ELECTRONICS 38,877.93 · SPORTS 34,809.96 · HOME 31,735.53 |

## 6. Canary orders (hand-computed)

| Order | Setup | Hand calculation | Contribution |
|---|---|---|---|
| 90001 | `2026-01-31 23:59:59`, EMEA/WEB, completed. Line 1: 2 × 50.00 − 10.00. Line 2: 1 × 20.00. Refunds on line 1: 15.00 + 5.00 processed, 30.00 rejected. | gross = 90.00 + 20.00 = **110.00** · refunds = 15 + 5 = **20.00** (rejected ignored) · net = **90.00** | January (not February) |
| 90002 | `2026-02-01 00:00:00`, EMEA/WEB, completed. 1 × 40.00, fully refunded on 2026-03-05. | gross **40.00** · refund **40.00** · net **0.00** | February (cohort), not March |
| 90003 | Cancelled, 1 × 100.00, processed reversal 100.00 | not eligible | none |
| 90004 | `2026-03-10`, APAC/STORE, completed. 1 × 25.00 with 25.00 discount | gross **0.00** · order counted | +1 order in March |

A naive join of `REFUNDS` to `ORDER_ITEMS` on `ORDER_ID` triples order 90001's line revenue (three refund rows) and double counts its refunds. `make db-verify` measures this trap on the full dataset (see `evidence/DB2_VERIFICATION.md`).
