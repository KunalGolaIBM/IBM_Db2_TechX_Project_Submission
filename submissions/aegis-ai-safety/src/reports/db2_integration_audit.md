# IBM Db2 Integration Audit

## Method

Real IBM Db2 Community Edition 12.1.5 at `localhost:50000`, database `TESTDB`, schema
`AEGIS`. Raw results: `reports/db2_reliability_results.json`.

## Results

| Check | Status | Evidence |
| --- | --- | --- |
| Health and six tables | PASSED | all six present, no missing tables |
| Constraints | PASSED | 15 primary/foreign/unique/check constraints |
| Indexes | PASSED | 18 indexes in `AEGIS` |
| Idempotent initialization/migrations | PASSED | `init_db.py --stats` twice, both exit 0 |
| Duplicate upload by content hash | PASSED | both calls returned document 5661; `already_existed=true`; 1 row |
| Transaction rollback | PASSED | failed FK insert left 0 documents and 0 orphan passages |
| Failed session state | PASSED | status `FAILED`, duration 12 ms, error retained |
| Concurrent reads | PASSED | 16 reads over 8 workers, 1.16 s, all succeeded |
| Safe connection failure | PASSED | wrong port raised `DatabaseUnavailableError`, no credentials leaked |
| Document persistence | PASSED | paper and synthetic documents persist |
| Passage provenance | PASSED | page/passage/character offsets stored |
| Session/result/evidence persistence | PASSED | integration tests and live session #501 |
| Foreign keys | PASSED | invalid FK rejected; no orphans |
| Unique constraints | PASSED | duplicate hash rejected/deduplicated |

## Defect found and fixed

### P1 — Repository ignored injected Db2 settings

`Db2Repository(settings)` accepted a settings object, but `health()` and all repository
operations called `transaction()` without passing it. `transaction()` therefore always
used the global environment settings. An intentionally wrong port still reported a live
connection, and alternate schemas/credentials would have been ignored.

**Fix:** `get_connection` and `transaction` now accept an optional settings object, and
every repository transaction passes `self.settings`. After the fix, a repository
configured with port 59999 correctly raises `DatabaseUnavailableError`.

This does not change normal app behavior (the app repository uses the same global
settings), but makes connection failure testing, schema isolation, and testability
correct.

## Limitations

- No high-volume concurrent write/soak test.
- No simulated Db2 crash/restart during a live request.
- No replication/failover testing.
- The local Db2 runs under amd64 emulation on Apple Silicon; raw performance is not
  representative of a production Db2 host.
- Session retention/deletion is manual; no retention policy is implemented.
