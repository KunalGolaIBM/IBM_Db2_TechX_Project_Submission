# G1 evidence: Db2 chooses the DiskANN vector index for FETCH APPROX (NEEDLE.ADV_DOC, 26,210 rows)

Recorded 2026-11-09 ~19:27-19:30 CST (EXPLAIN_TIME values below are UTC). Db2 v12.1.5.0 in codespace
`db2hack-needle-jj7gxr4xqg4vhw95`, container `db2`, database VECDB. Producer: data agent.

## Summary (observed, not interpreted)

| Variant | Plan (operator ids 1..n) | ADV_DOC_VIX used | Optimizer cost | Median latency (20 queries) |
|---|---|---|---|---|
| APPROX, literal query vector, k literal 10 | RETURN, TBSCAN, SORT, FETCH, IXSCAN on `VECIDX: NEEDLE.ADV_DOC_VIX` | yes | 501.8 | 3.0 ms |
| APPROX, bound query vector `VECTOR(CAST(? AS CLOB(100K)),768,FLOAT32)`, k literal 10 | same as above | yes | 501.8 | 4.8 ms |
| EXACT, literal vector | RETURN, TBSCAN, SORT, TBSCAN (table) | no | 3391.4 | 71.7 ms |
| EXACT, bound vector | RETURN, TBSCAN, SORT, TBSCAN (table) | no | 3391.4 | 72.3 ms |
| APPROX, bound vector, **k as parameter marker** (`FETCH APPROX FIRST ? ROWS`) | RETURN, TBSCAN, SORT, TBSCAN (table) | **no** | 3401.6 | not timed |
| APPROX, bound vector, `WHERE ROW_BUCKET < 25` | RETURN, TBSCAN, SORT, FETCH, IXSCAN on ADV_DOC_VIX | yes | 973.5 | 4.6 ms |

- APPROX vs EXACT top-10 overlap over the same 20 queries: mean 0.995, min 0.90 (bound and literal alike).
- The earlier 3,000-row result (TBSCAN+SORT for APPROX) does not repeat at 26,210 rows after
  CREATE VECTOR INDEX + RUNSTATS: the index is chosen for both a literal and a bound query vector.
- Confirmed: `FETCH APPROX FIRST ? ROWS ONLY` (k as a parameter marker) does NOT use the index. Write k as a validated integer literal.
- No tuning was needed, so DB2_VECTOR_INDEXING, optimization guidelines and dropping the PK were NOT tried.

## Filtered ANN (a plain WHERE predicate, not RCAC yet)

20 queries, bound vector, k literal 10. Recall = |APPROX top-10 ∩ EXACT top-10| / |EXACT top-10| under the same predicate.
ROW_BUCKET is uniform 0-99, so `ROW_BUCKET < b` keeps about b % of rows.

```
bucket<100 APPROX n=20 median=7.4 ms p95=8.6 ms min=6.0 max=11.7 | EXACT n=20 median=73.9 ms p95=107.4 ms min=71.1 max=125.2 | recall@10 mean=0.995 min=0.90 | APPROX rows returned min=10
bucket<50  APPROX n=20 median=2.2 ms p95=2.4 ms min=2.1 max=5.2 | EXACT n=20 median=40.5 ms p95=44.7 ms min=38.2 max=46.4 | recall@10 mean=0.905 min=0.50 | APPROX rows returned min=5
bucket<25  APPROX n=20 median=4.6 ms p95=5.8 ms min=3.4 max=6.7 | EXACT n=20 median=27.1 ms p95=36.0 ms min=25.1 max=45.9 | recall@10 mean=0.840 min=0.50 | APPROX rows returned min=5
bucket<10  APPROX n=20 median=6.1 ms p95=45.7 ms min=5.3 max=59.2 | EXACT n=20 median=14.2 ms p95=16.0 ms min=13.9 max=16.9 | recall@10 mean=0.750 min=0.50 | APPROX rows returned min=5
bucket<5   APPROX n=20 median=9.7 ms p95=11.5 ms min=9.2 max=13.1 | EXACT n=20 median=9.3 ms p95=10.6 ms min=9.1 max=11.8 | recall@10 mean=1.000 min=1.00 | APPROX rows returned min=10
```

Plans chosen for `FETCH APPROX` under the predicate (EXPLAIN, same session):

```
bucket<100 APPROX plan: RETURN <- TBSCAN <- SORT <- FETCH <- IXSCAN | uses ADV_DOC_VIX=True | cost=501.8
bucket<50  APPROX plan: RETURN <- TBSCAN <- SORT <- FETCH <- IXSCAN | uses ADV_DOC_VIX=True | cost=654.9
bucket<25  APPROX plan: RETURN <- TBSCAN <- SORT <- FETCH <- IXSCAN | uses ADV_DOC_VIX=True | cost=973.5
bucket<10  APPROX plan: RETURN <- TBSCAN <- SORT <- FETCH <- IXSCAN | uses ADV_DOC_VIX=True | cost=1806.9
bucket<5   APPROX plan: RETURN <- TBSCAN <- SORT <- TBSCAN | uses ADV_DOC_VIX=False | cost=3391.6
```

Observed: with the index in the plan, APPROX
returned as few as 5 of 10 requested rows (b = 50, 25, 10) and recall fell to 0.905 / 0.840 / 0.750.
Interpretation (not verified in plan details): the predicate is applied at FETCH after the index returns its approximate candidates.
At b = 5 the optimizer switched to a table scan (exact) and recall was 1.000.
This is the effect the RCAC sweep measures; the RCAC row permission may behave differently and must be measured separately.

## How to reproduce

PC: `PYTHONPATH=src .venv\Scripts\python scripts\g1_make_queries.py` (20 fixed queries, `search_query: ` prefix),
copy `scripts/g1_explain.py`, `scripts/load_in_codespace.py`, `data/g1_queries.json` to `/tmp/needle/` in the codespace,
then `python3 /tmp/needle/g1_explain.py` and `python3 /tmp/needle/g1_explain.py --extra` with DB2_PASSWORD on stdin
(see scripts/load_in_codespace.sh for the stdin pattern). EXPLAIN tables: schema DB2INST1; db2exfmt runs as db2inst1 in the container.

---

# Raw output 1: baseline run (`g1_explain.py`)

## G1 run: baseline: 26,210 rows, vector index + RUNSTATS

```
ADV_DOC rows: 26210
index: ('SQL261110012227340', 'REG ', '+ADV_ID', 28, datetime.datetime(2026, 11, 10, 1, 26, 38, 884082))
index: ('ADV_DOC_CANON', 'REG ', '+CANON_ID', 28, datetime.datetime(2026, 11, 10, 1, 26, 38, 884082))
index: ('ADV_DOC_VIX', 'VANN', '+EMB', -1, None)
table stats CARD/NPAGES/STATS_TIME: (26210, 2913, datetime.datetime(2026, 11, 10, 1, 26, 38, 884082))
EMB nullable: N
```

### APPROX_literal

```sql
SELECT ADV_ID FROM NEEDLE.ADV_DOC ORDER BY VECTOR_DISTANCE(EMB, VECTOR('<768 floats>', 768, FLOAT32), COSINE) FETCH APPROX FIRST 10 ROWS ONLY
```

EXPLAIN_TIME 2026-11-10 01:27:09.649346  total cost 501.7973327636719  **uses ADV_DOC_VIX: True**

```
OPERATOR_ID OPERATOR_TYPE TOTAL_COST
          1 RETURN        501.7973327636719
          2 TBSCAN        501.7973327636719
          3 SORT          501.7971496582031
          4 FETCH         501.7875671386719
          5 IXSCAN        431.440185546875

EXPLAIN_STREAM rows with an object (SRC_ID SRC_TYPE -> TGT_ID TGT_TYPE OBJECT ROWS):
  -1 D -> 4 O  NEEDLE.ADV_DOC  26210.0
  -1 D -> 5 O  NEEDLE.ADV_DOC_VIX  26210.0

EXPLAIN_OBJECT:
  SYSIBM.ACV261110012537972461_P2_O15_I3 TA
  NEEDLE.ADV_DOC TA
  NEEDLE.ADV_DOC_VIX VI
  SYSIBM.AGT261110012537972461_P2_O15_I3 TA
  SYSIBM.AIJ261110012537972461_P2_O15_I3 TA
```

db2exfmt access plan:

```
Access Plan:
-----------
	Total Cost: 		501.797
	Query Degree:		1


             Rows 
            RETURN
            (   1)
             Cost 
              I/O 
              |
              10 
            TBSCAN
            (   2)
            501.797 
            70.4381 
              |
              10 
            SORT  
            (   3)
            501.797 
            70.4381 
              |
              10 
            FETCH 
            (   4)
            501.788 
            70.4381 
          /---+----\
        10          26210 
      IXSCAN   TABLE: NEEDLE  
      (   5)       ADV_DOC
      431.44         Q1
      60.4536 
        |
       26210 
 VECIDX: NEEDLE  
    ADV_DOC_VIX
        Q1



Extended Diagnostic Information:
--------------------------------

No extended Diagnostic Information for this statement.


Plan Details:
```

### EXACT_literal

```sql
SELECT ADV_ID FROM NEEDLE.ADV_DOC ORDER BY VECTOR_DISTANCE(EMB, VECTOR('<768 floats>', 768, FLOAT32), COSINE) FETCH EXACT FIRST 10 ROWS ONLY
```

EXPLAIN_TIME 2026-11-10 01:27:10.602355  total cost 3391.352783203125  **uses ADV_DOC_VIX: False**

```
OPERATOR_ID OPERATOR_TYPE TOTAL_COST
          1 RETURN        3391.352783203125
          2 TBSCAN        3391.352783203125
          3 SORT          3391.3525390625
          4 TBSCAN        3389.768798828125

EXPLAIN_STREAM rows with an object (SRC_ID SRC_TYPE -> TGT_ID TGT_TYPE OBJECT ROWS):
  -1 D -> 4 O  NEEDLE.ADV_DOC  26210.0

EXPLAIN_OBJECT:
  SYSIBM.ACV261110012537972461_P2_O15_I3 +T
  NEEDLE.ADV_DOC TA
  SYSIBM.AGT261110012537972461_P2_O15_I3 +T
  SYSIBM.AIJ261110012537972461_P2_O15_I3 +T
```

db2exfmt access plan:

```
Access Plan:
-----------
	Total Cost: 		3391.35
	Query Degree:		1


      Rows 
     RETURN
     (   1)
      Cost 
       I/O 
       |
       10 
     TBSCAN
     (   2)
     3391.35 
      2913 
       |
       10 
     SORT  
     (   3)
     3391.35 
      2913 
       |
      26210 
     TBSCAN
     (   4)
     3389.77 
      2913 
       |
      26210 
 TABLE: NEEDLE  
     ADV_DOC
       Q1



Extended Diagnostic Information:
--------------------------------

No extended Diagnostic Information for this statement.


Plan Details:
```

### APPROX_bound

```sql
SELECT ADV_ID FROM NEEDLE.ADV_DOC ORDER BY VECTOR_DISTANCE(EMB, VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32), COSINE) FETCH APPROX FIRST 10 ROWS ONLY
```

EXPLAIN_TIME 2026-11-10 01:27:10.920241  total cost 501.7973327636719  **uses ADV_DOC_VIX: True**

```
OPERATOR_ID OPERATOR_TYPE TOTAL_COST
          1 RETURN        501.7973327636719
          2 TBSCAN        501.7973327636719
          3 SORT          501.7971496582031
          4 FETCH         501.7875671386719
          5 IXSCAN        431.440185546875

EXPLAIN_STREAM rows with an object (SRC_ID SRC_TYPE -> TGT_ID TGT_TYPE OBJECT ROWS):
  -1 D -> 4 O  NEEDLE.ADV_DOC  26210.0
  -1 D -> 5 O  NEEDLE.ADV_DOC_VIX  26210.0

EXPLAIN_OBJECT:
  SYSIBM.ACV261110012537972461_P2_O15_I3 TA
  NEEDLE.ADV_DOC TA
  NEEDLE.ADV_DOC_VIX VI
  SYSIBM.AGT261110012537972461_P2_O15_I3 TA
  SYSIBM.AIJ261110012537972461_P2_O15_I3 TA
```

db2exfmt access plan:

```
Access Plan:
-----------
	Total Cost: 		501.797
	Query Degree:		1


             Rows 
            RETURN
            (   1)
             Cost 
              I/O 
              |
              10 
            TBSCAN
            (   2)
            501.797 
            70.4381 
              |
              10 
            SORT  
            (   3)
            501.797 
            70.4381 
              |
              10 
            FETCH 
            (   4)
            501.788 
            70.4381 
          /---+----\
        10          26210 
      IXSCAN   TABLE: NEEDLE  
      (   5)       ADV_DOC
      431.44         Q1
      60.4536 
        |
       26210 
 VECIDX: NEEDLE  
    ADV_DOC_VIX
        Q1



Extended Diagnostic Information:
--------------------------------

No extended Diagnostic Information for this statement.


Plan Details:
```

### EXACT_bound

```sql
SELECT ADV_ID FROM NEEDLE.ADV_DOC ORDER BY VECTOR_DISTANCE(EMB, VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32), COSINE) FETCH EXACT FIRST 10 ROWS ONLY
```

EXPLAIN_TIME 2026-11-10 01:27:11.224029  total cost 3391.352783203125  **uses ADV_DOC_VIX: False**

```
OPERATOR_ID OPERATOR_TYPE TOTAL_COST
          1 RETURN        3391.352783203125
          2 TBSCAN        3391.352783203125
          3 SORT          3391.3525390625
          4 TBSCAN        3389.768798828125

EXPLAIN_STREAM rows with an object (SRC_ID SRC_TYPE -> TGT_ID TGT_TYPE OBJECT ROWS):
  -1 D -> 4 O  NEEDLE.ADV_DOC  26210.0

EXPLAIN_OBJECT:
  SYSIBM.ACV261110012537972461_P2_O15_I3 +T
  NEEDLE.ADV_DOC TA
  SYSIBM.AGT261110012537972461_P2_O15_I3 +T
  SYSIBM.AIJ261110012537972461_P2_O15_I3 +T
```

db2exfmt access plan:

```
Access Plan:
-----------
	Total Cost: 		3391.35
	Query Degree:		1


      Rows 
     RETURN
     (   1)
      Cost 
       I/O 
       |
       10 
     TBSCAN
     (   2)
     3391.35 
      2913 
       |
       10 
     SORT  
     (   3)
     3391.35 
      2913 
       |
      26210 
     TBSCAN
     (   4)
     3389.77 
      2913 
       |
      26210 
 TABLE: NEEDLE  
     ADV_DOC
       Q1



Extended Diagnostic Information:
--------------------------------

No extended Diagnostic Information for this statement.


Plan Details:
```

### Timing (20 triage queries, k literal 10, wall clock from python3+ibm_db inside the codespace)

```
APPROX_bound    n=20 median=4.8 ms p95=5.6 ms min=2.4 max=5.6
EXACT_bound     n=20 median=72.3 ms p95=73.1 ms min=70.5 max=75.8
APPROX_literal  n=20 median=3.0 ms p95=3.4 ms min=2.8 max=4.5
EXACT_literal   n=20 median=71.7 ms p95=74.1 ms min=71.1 max=78.6
overlap@10 APPROX_bound vs EXACT_bound: mean=0.995 min=0.90
overlap@10 APPROX_literal vs EXACT_literal: mean=0.995 min=0.90
```

Verdict per variant (uses ADV_DOC_VIX): {"APPROX_literal": true, "EXACT_literal": false, "APPROX_bound": true, "EXACT_bound": false}

---

# Raw output 2: extra run (`g1_explain.py --extra`)

## G1 run: extra: k as parameter marker, ROW_BUCKET filter

```
ADV_DOC rows: 26210
index: ('SQL261110012227340', 'REG ', '+ADV_ID', 28, datetime.datetime(2026, 11, 10, 1, 26, 38, 884082))
index: ('ADV_DOC_CANON', 'REG ', '+CANON_ID', 28, datetime.datetime(2026, 11, 10, 1, 26, 38, 884082))
index: ('ADV_DOC_VIX', 'VANN', '+EMB', -1, None)
table stats CARD/NPAGES/STATS_TIME: (26210, 2913, datetime.datetime(2026, 11, 10, 1, 26, 38, 884082))
EMB nullable: N
```

### APPROX_k_param

```sql
SELECT ADV_ID FROM NEEDLE.ADV_DOC ORDER BY VECTOR_DISTANCE(EMB, VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32), COSINE) FETCH APPROX FIRST ? ROWS ONLY
```

EXPLAIN_TIME 2026-11-10 01:27:48.356520  total cost 3401.550537109375  **uses ADV_DOC_VIX: False**

```
OPERATOR_ID OPERATOR_TYPE TOTAL_COST
          1 RETURN        3401.550537109375
          2 TBSCAN        3401.550537109375
          3 SORT          3401.447265625
          4 FILTER        3400.354736328125
          5 TBSCAN        3394.194091796875
          6 SORT          3393.884521484375
          7 TBSCAN        3389.768798828125

EXPLAIN_STREAM rows with an object (SRC_ID SRC_TYPE -> TGT_ID TGT_TYPE OBJECT ROWS):
  -1 D -> 7 O  NEEDLE.ADV_DOC  26210.0

EXPLAIN_OBJECT:
  SYSIBM.ACV261110012537972461_P2_O15_I3 +T
  NEEDLE.ADV_DOC TA
  SYSIBM.AGT261110012537972461_P2_O15_I3 +T
  SYSIBM.AIJ261110012537972461_P2_O15_I3 +T
```

db2exfmt access plan:

```
Access Plan:
-----------
	Total Cost: 		3401.55
	Query Degree:		1


      Rows 
     RETURN
     (   1)
      Cost 
       I/O 
       |
     8736.67 
     TBSCAN
     (   2)
     3401.55 
      2913 
       |
     8736.67 
     SORT  
     (   3)
     3401.45 
      2913 
       |
     8736.67 
     FILTER
     (   4)
     3400.35 
      2913 
       |
      26210 
     TBSCAN
     (   5)
     3394.19 
      2913 
       |
      26210 
     SORT  
     (   6)
     3393.88 
      2913 
       |
      26210 
     TBSCAN
     (   7)
     3389.77 
      2913 
       |
      26210 
 TABLE: NEEDLE  
     ADV_DOC
       Q1



Extended Diagnostic Information:
--------------------------------

No extended Diagnostic Information for this statement.


Plan Details:
```

### APPROX_bound_where_bucket25

```sql
SELECT ADV_ID FROM NEEDLE.ADV_DOC WHERE ROW_BUCKET < 25 ORDER BY VECTOR_DISTANCE(EMB, VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32), COSINE) FETCH APPROX FIRST 10 ROWS ONLY
```

EXPLAIN_TIME 2026-11-10 01:27:48.730389  total cost 973.506103515625  **uses ADV_DOC_VIX: True**

```
OPERATOR_ID OPERATOR_TYPE TOTAL_COST
          1 RETURN        973.506103515625
          2 TBSCAN        973.506103515625
          3 SORT          973.5059204101562
          4 FETCH         973.4962158203125
          5 IXSCAN        700.4992065429688

EXPLAIN_STREAM rows with an object (SRC_ID SRC_TYPE -> TGT_ID TGT_TYPE OBJECT ROWS):
  -1 D -> 4 O  NEEDLE.ADV_DOC  26210.0
  -1 D -> 5 O  NEEDLE.ADV_DOC_VIX  26210.0

EXPLAIN_OBJECT:
  SYSIBM.ACV261110012537972461_P2_O15_I3 TA
  NEEDLE.ADV_DOC TA
  NEEDLE.ADV_DOC_VIX VI
  SYSIBM.AGT261110012537972461_P2_O15_I3 TA
  SYSIBM.AIJ261110012537972461_P2_O15_I3 TA
```

db2exfmt access plan:

```
Access Plan:
-----------
	Total Cost: 		973.506
	Query Degree:		1


             Rows 
            RETURN
            (   1)
             Cost 
              I/O 
              |
              10 
            TBSCAN
            (   2)
            973.506 
            137.265 
              |
              10 
            SORT  
            (   3)
            973.506 
            137.265 
              |
            10.0822 
            FETCH 
            (   4)
            973.496 
            137.265 
          /---+----\
        39          26210 
      IXSCAN   TABLE: NEEDLE  
      (   5)       ADV_DOC
      700.499        Q1
      98.5178 
        |
       26210 
 VECIDX: NEEDLE  
    ADV_DOC_VIX
        Q1



Extended Diagnostic Information:
--------------------------------

No extended Diagnostic Information for this statement.


Plan Details:
```

### EXACT_bound_where_bucket25

```sql
SELECT ADV_ID FROM NEEDLE.ADV_DOC WHERE ROW_BUCKET < 25 ORDER BY VECTOR_DISTANCE(EMB, VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32), COSINE) FETCH EXACT FIRST 10 ROWS ONLY
```

EXPLAIN_TIME 2026-11-10 01:27:49.109119  total cost 3390.7294921875  **uses ADV_DOC_VIX: False**

```
OPERATOR_ID OPERATOR_TYPE TOTAL_COST
          1 RETURN        3390.7294921875
          2 TBSCAN        3390.7294921875
          3 SORT          3390.729248046875
          4 TBSCAN        3390.31982421875

EXPLAIN_STREAM rows with an object (SRC_ID SRC_TYPE -> TGT_ID TGT_TYPE OBJECT ROWS):
  -1 D -> 4 O  NEEDLE.ADV_DOC  26210.0

EXPLAIN_OBJECT:
  SYSIBM.ACV261110012537972461_P2_O15_I3 +T
  NEEDLE.ADV_DOC TA
  SYSIBM.AGT261110012537972461_P2_O15_I3 +T
  SYSIBM.AIJ261110012537972461_P2_O15_I3 +T
```

db2exfmt access plan:

```
Access Plan:
-----------
	Total Cost: 		3390.73
	Query Degree:		1


      Rows 
     RETURN
     (   1)
      Cost 
       I/O 
       |
       10 
     TBSCAN
     (   2)
     3390.73 
      2913 
       |
       10 
     SORT  
     (   3)
     3390.73 
      2913 
       |
     6775.73 
     TBSCAN
     (   4)
     3390.32 
      2913 
       |
      26210 
 TABLE: NEEDLE  
     ADV_DOC
       Q1



Extended Diagnostic Information:
--------------------------------

No extended Diagnostic Information for this statement.


Plan Details:
```

### Filtered ANN (WHERE ROW_BUCKET < b), 20 queries, k literal 10

```
bucket<100 APPROX n=20 median=7.4 ms p95=8.6 ms min=6.0 max=11.7 | EXACT n=20 median=73.9 ms p95=107.4 ms min=71.1 max=125.2 | recall@10 mean=0.995 min=0.90 | APPROX rows returned min=10
bucket<50  APPROX n=20 median=2.2 ms p95=2.4 ms min=2.1 max=5.2 | EXACT n=20 median=40.5 ms p95=44.7 ms min=38.2 max=46.4 | recall@10 mean=0.905 min=0.50 | APPROX rows returned min=5
bucket<25  APPROX n=20 median=4.6 ms p95=5.8 ms min=3.4 max=6.7 | EXACT n=20 median=27.1 ms p95=36.0 ms min=25.1 max=45.9 | recall@10 mean=0.840 min=0.50 | APPROX rows returned min=5
bucket<10  APPROX n=20 median=6.1 ms p95=45.7 ms min=5.3 max=59.2 | EXACT n=20 median=14.2 ms p95=16.0 ms min=13.9 max=16.9 | recall@10 mean=0.750 min=0.50 | APPROX rows returned min=5
bucket<5   APPROX n=20 median=9.7 ms p95=11.5 ms min=9.2 max=13.1 | EXACT n=20 median=9.3 ms p95=10.6 ms min=9.1 max=11.8 | recall@10 mean=1.000 min=1.00 | APPROX rows returned min=10
```

Verdict per variant (uses ADV_DOC_VIX): {"APPROX_k_param": false, "APPROX_bound_where_bucket25": true, "EXACT_bound_where_bucket25": false}
