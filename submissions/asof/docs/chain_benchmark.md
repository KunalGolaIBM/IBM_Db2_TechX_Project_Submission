# Chain benchmark

How long `VERIFY_CHAIN` takes over a real hash chain: rows appended through the ledger's own `APPEND_LEDGER_ROW` (a SHA-256 link each, two claim citations each), then verified as the runtime user, which recomputes every row hash and checks every citation against the hashed verdicts. Run with `python -m asof.chainbench --rows N` ([chainbench.py](../src/asof/chainbench.py)).

Runs since checkpoints exist also time `VERIFY_CHAIN_FROM_CHECKPOINT` ([12_chain_checkpoints.sql](../src/asof/sql/12_chain_checkpoints.sql)) at each size: it re-checks the latest checkpoint's row, then recomputes only the rows after it as `VERIFY_CHAIN` does, and records a new checkpoint. The first one has no checkpoint to start from, so it is a full scan. The last line of such a run appends more rows and times one incremental verify of just those.

What an incremental verify does not cover: it recomputes no row before the checkpoint. An owner who drops the triggers and edits an old row without touching its stored hashes is caught by the full `VERIFY_CHAIN` only. The chain-head anchors ([anchor.py](../src/asof/anchor.py)) compare each anchored `ROW_HASH` with the one the ledger stores now, so they catch a rebuild that rewrote stored hashes up to the last anchor, not an edit that left them in place; `python -m asof.anchor verify` runs the full `VERIFY_CHAIN` after that comparison. A checkpoint is a row in Db2 that the owner could also write, so it saves time and adds no trust: keep the full scan for audits (the nightly Airflow run) and the incremental one in between.

## 300,000 rows, run 2026-11-11 02:02 UTC at `60fea77`

Machine: Google Cloud VM asof-build: 16 vCPU AMD EPYC 7B12, 64 GB RAM, Ubuntu 24.04; IBM stock image icr.io/db2_community/db2:12.1.5.0 running natively on x86_64 (container db2c, 6 GiB memory limit), client on the same VM; seven other Db2 containers on the VM, load average under 2 at the start; the last minute of a Db2 test run on the same container overlapped the start of the 300,000-row full verify, and the 100,000 to 300,000 load shared it with that run.

Stopped at 300,000 rows, not 1,000,000: on this container an append took about 9 ms at the start and about 25 ms near 300,000 (before the overlapping test run began), with the release-rules trigger, the row permissions and the MQT maintenance all running on each one; the cause was not profiled. 1,000,000 rows would have needed several hours of loading.

| Rows | VERIFY_CHAIN (full) | Time | Per 1,000 rows | From the checkpoint | Rows recomputed | Time | Load so far |
|---|---|---|---|---|---|---|---|
| 10,000 | OK | 26.7 s | 2.67 s | OK | 10,000 (from row 1) | 27.8 s | 90 s |
| 100,000 | OK | 247.8 s | 2.48 s | OK | 90,001 (from row 10,000) | 220.9 s | 1,118 s |
| 300,000 | OK | 890.9 s | 2.97 s | OK | 200,001 (from row 100,000) | 506.0 s | 4,272 s |

Then 1,000 more rows: `VERIFY_CHAIN_FROM_CHECKPOINT` OK in 4.3 s, recomputing 1,001 rows (the checkpoint row at 300,000 and the 1,000 after it), against 890.9 s for the full `VERIFY_CHAIN` over 300,000 rows.

## 1,000,000 rows, run 2026-11-08 23:45 UTC at `91aadc2`

Machine: MacBook Air (Apple Silicon), Db2 12.1.5 in IBM's x86 image under Rosetta.

| Rows | VERIFY_CHAIN | Time | Per 1,000 rows | Load so far |
|---|---|---|---|---|
| 10,000 | OK | 24.3 s | 2.43 s | 12 s |
| 100,000 | OK | 245.6 s | 2.46 s | 111 s |
| 1,000,000 | OK | 2,755.8 s | 2.76 s | 1,127 s |
