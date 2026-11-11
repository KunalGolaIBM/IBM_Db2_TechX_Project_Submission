# DBA tools and EXPLAIN

Db2 Ops Copilot exposes a fixed set of **read-only DBA tools** and a real
**EXPLAIN** service. Both work offline (mock adapter) and against a live Db2 LUW
(`ADAPTER_MODE=real`).

> **Validation status — please read.** No live Db2 was available during
> development. Everything below is covered by offline tests against a *fake*
> `ibm_db_dbi` driver (statements, parameter binding, row caps, fallbacks and
> SQLSTATE→HTTP mapping). The SQL was written from IBM Db2 LUW documentation
> and parses with the IBM `db2` sqlglot dialect, but **it has not been executed
> on a real Db2**. Run the verification steps at the end on your instance.

## Why tools instead of free-form SQL?

The SQL safety gate deliberately denies `SYSCAT`, `SYSIBMADM`, `SYSPROC`, … to
*generated* SQL. DBA tools are the only application path to those schemas, and
they are **fixed templates**:

- user values (schema, table) are only ever bound as `?` parameters,
- the only interpolated value is a validated integer row limit (Db2 does not
  allow markers in `FETCH FIRST`),
- every template is one `SELECT`, bounded by `FETCH FIRST n ROWS ONLY`,
- system schemas (`SYS*`, `NULLID`, `SQLJ`) cannot be targeted,
- tools never accept SQL text; unknown parameters are rejected (422).

These invariants are enforced by `backend/tests/test_dba_specs.py`.

## Tools

| Tool id | Source | Purpose | Params |
|---|---|---|---|
| `catalog.tables` | `SYSCAT.TABLES` | Tables/views, CARD, NPAGES, last RUNSTATS | schema, limit |
| `catalog.columns` | `SYSCAT.COLUMNS` | Columns, types, nullability, key position | schema, **table**, limit |
| `catalog.indexes` | `SYSCAT.INDEXES` | Indexes, uniqueness, key columns, levels | schema, **table**, limit |
| `catalog.constraints` | `SYSCAT.TABCONST` + `KEYCOLUSE` | PK/unique/FK/check constraints | schema, **table**, limit |
| `catalog.stale_statistics` | `SYSCAT.TABLES` | Tables with no/oldest statistics | schema, limit |
| `monitor.table_activity` | `MON_GET_TABLE` | Hot tables by rows read, scan counts | schema, limit |
| `monitor.index_usage` | `MON_GET_INDEX` + `SYSCAT.INDEXES` | Least-used indexes first | schema, limit |
| `monitor.slow_statements` | `MON_GET_PKG_CACHE_STMT` | Costly dynamic statements | limit |
| `monitor.connections` | `MON_GET_CONNECTION` | Connections, CPU, lock metrics | limit |
| `monitor.lock_waits` | `MON_GET_LOCKS` | Locks in WAIT/CONVERT state | limit |
| `monitor.bufferpool_hit_ratio` | `MON_GET_BUFFERPOOL` | Logical/physical reads, hit ratio | limit |

`schema` defaults to `DB2_APP_SCHEMA` (`APP`). `limit` is 1–100
(`DBA_DEFAULT_LIMIT`, default 20). Statement text returned by
`monitor.slow_statements` passes through the credential redactor.

### Mock equivalents

Every tool has a deterministic mock (`backend/app/dba/mock_data.py`) mirroring
migrations 001/002 (same tables, keys and indexes). The monitoring numbers are
synthetic and tell one story for demos: `DEMO_INCIDENTS` is read by full scans
because queries filter on `RESOLVED_AT`, which has no index — the "missing
index" finding. Responses carry `mock: true` and `source: "mock"`.

## EXPLAIN (`POST /api/v1/sql/explain`)

Flow (real mode):

1. SQL passes the sqlglot gate and the row-cap wrap (the explained statement is
   the one that would run). EXPLAIN **never executes** it.
2. `EXPLAIN PLAN SET QUERYTAG = '<uuid>' FOR <statement>` populates the
   `EXPLAIN_*` tables (`DB2_EXPLAIN_SCHEMA`, default `SYSTOOLS`).
3. The plan is read back by that tag: statement cost (`EXPLAIN_STATEMENT`),
   operators (`EXPLAIN_OPERATOR`), tables/indexes (`EXPLAIN_OBJECT`).
4. The rows are deleted (`EXPLAIN_INSTANCE` cascades); a cleanup failure only
   adds a warning.
5. A plain-language summary (full scans, index use, sorts, joins) is derived
   from the operators only.

### Graceful fallback

The adapter never raises. Failures are statuses on an HTTP 200 response:

| Situation | `status` | `hint` |
|---|---|---|
| No driver / Db2 unreachable | `UNAVAILABLE` | needs a live connection |
| EXPLAIN tables missing (SQL0219N) | `UNAVAILABLE` | `SYSINSTALLOBJECTS` command |
| Missing privilege (42501) | `UNAVAILABLE` | grants in migration 005 |
| Timeout (57014) / resource | `UNAVAILABLE` | simplify / raise timeout |
| Db2 rejects the statement (syntax, unknown object) | `FAILED` | SQLSTATE hint |
| Offline mock | `OK`, `source: "mock"` | synthetic plan, labelled as such |

The execution path (`/sql/execute`) uses EXPLAIN as an advisory dry-run that
never blocks execution.

## Error mapping

See *Database error mapping* in [`API_CONTRACT.md`](API_CONTRACT.md):
403 permission, 404 object, 422 SQL, 503 connectivity, 504 timeout, 502 other.

## Live-mode setup

1. `pip install -r requirements-integration.txt`
2. Apply `database/migrations/` 001–005 (005 creates the EXPLAIN tables and
   grants). `monitor.*` tools additionally need `EXECUTE` on `MON_GET_*` plus
   `DATAACCESS`/`DBADM`/`SQLADM`/`WLMADM`; without them they return 403
   `DB_PERMISSION_DENIED`. Prefer a separate monitoring account over widening
   the query account.
3. Set `ADAPTER_MODE=real` and the `DB2_*` variables in `.env`.

### Verify on a live instance

```bash
curl -s localhost:8000/api/v1/dba/tools/catalog.tables/run -XPOST -H 'content-type: application/json' -d '{}'
curl -s localhost:8000/api/v1/dba/tools/monitor.table_activity/run -XPOST -H 'content-type: application/json' -d '{"params":{"limit":5}}'
curl -s localhost:8000/api/v1/sql/explain -XPOST -H 'content-type: application/json' \
     -d '{"sql":"SELECT * FROM DEMO_INCIDENTS WHERE SEVERITY = 3"}'
```

Expected: `"source": "db2"` and `"mock": false`. If a tool fails, the error's
`detail.sqlstate` and `detail.hint` say why; report any column/function name
that differs on your Db2 version.

## Known limitations

- Not validated on a live Db2 (see the note at the top).
- `COLNAMES` in `catalog.indexes` is a legacy catalog column kept for brevity.
- `monitor.*` results are per-member (`-2` = current member); no cross-member
  aggregation.
- EXPLAIN reports optimizer cost and operators, not formatted `db2exfmt` text.
