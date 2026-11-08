# Chain benchmark

How long `VERIFY_CHAIN` takes over a real hash chain: rows appended through the ledger's own `APPEND_LEDGER_ROW` (a SHA-256 link each, two claim citations each), then verified as the runtime user, which recomputes every row hash and checks every citation against the hashed verdicts. Run with `python -m asof.chainbench --rows N` ([chainbench.py](../src/asof/chainbench.py)).

## 1,000,000 rows, run 2026-11-08 23:45 UTC at `91aadc2`

| Rows | VERIFY_CHAIN | Time | Per 1,000 rows | Load so far |
|---|---|---|---|---|
| 10,000 | OK | 24.3 s | 2.43 s | 12 s |
| 100,000 | OK | 245.6 s | 2.46 s | 111 s |
| 1,000,000 | OK | 2,755.8 s | 2.76 s | 1,127 s |
