"""Chain benchmark: how long VERIFY_CHAIN takes over a real hash chain, at volume.

    python -m asof.chainbench [--rows 1000000] [--extra 1000] [--machine "..."] [--keep]

Installs the AsOf schema in a scratch schema (CBENCH), then appends the rows inside Db2 through the ledger's own
APPEND_LEDGER_ROW, so every row carries a real SHA-256 link and two claim citations, as a check with two claims
does. A stored procedure loops on the server and commits every 5,000 rows, flushing the buffer pools so dirty pages
never hold the log, and the load costs no network round trips. Then it runs VERIFY_CHAIN as the runtime user, which
recomputes every row hash and checks every citation against the hashed verdicts, and records the time at each size it
passes on the way (10,000, 100,000, then the full count). At each size it also runs VERIFY_CHAIN_FROM_CHECKPOINT
(12_chain_checkpoints.sql), which recomputes only the rows since the previous size's checkpoint, and at the end it
appends --extra more rows and times one incremental verify of just those. Results go to docs/chain_benchmark.md and
docs/chainbench/, labelled with --machine.

ledgerbench's synthetic rows are not a chain; this is the benchmark for the one operation that reads them as one.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import db, ledger, schema, seed
from .config import Settings, get_settings
from .embeddings import get_embeddings
from .eval.__main__ import _git_commit

BENCH_SCHEMA = "CBENCH"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "docs" / "chainbench"
REPORT = PROJECT_ROOT / "docs" / "chain_benchmark.md"
CHECKPOINTS = (10_000, 100_000)

# Two claims, as a typical check records them; APPEND_LEDGER_ROW shreds them into CLAIM_CITATION. The re-check's
# claim quotes BRV-002 v1 (in force from 2026-01-01 to 2026-04-30), and every row's customer date falls in that
# period, so each append passes Db2's release rules (08_release_rules.sql) like a real CORRECTED decision.
VERDICTS = json.dumps({"version": 1, "claims": [
    {"pass": 1, "claim_no": 1, "text": "Bereavement fares can be requested after travel.", "area": "bereavement",
     "verdict": "CONTRADICTED", "llm_verdict": "CONTRADICTED", "rule_check": "MISMATCH", "clause_id": "BRV-002",
     "clause_version": "v1", "clause_bus_start": "2026-01-01", "clause_sys_start": None, "distance": 0.21,
     "quoted_span": "cannot be applied retroactively"},
    {"pass": 2, "claim_no": 1, "text": "Bereavement fares must be requested before travel begins.",
     "area": "bereavement", "verdict": "SUPPORTED", "llm_verdict": "SUPPORTED", "rule_check": "MATCH",
     "clause_id": "BRV-002", "clause_version": "v1", "clause_bus_start": "2026-01-01", "clause_sys_start": None,
     "distance": 0.12, "quoted_span": "must be requested before travel begins"}]})

# Created in the scratch schema (unqualified names resolve to it): appends P_ROWS rows, committing every P_BATCH.
SQL_FILL = """CREATE OR REPLACE PROCEDURE CHAINBENCH_FILL (IN P_ROWS INTEGER, IN P_BATCH INTEGER, IN P_VERDICTS VARCHAR(30000))
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  DECLARE I INTEGER DEFAULT 0;
  DECLARE V_ID BIGINT;
  DECLARE V_HASH CHAR(64);
  DECLARE V_AT TIMESTAMP(12);
  DECLARE V_BASE BIGINT;
  SET V_BASE = (SELECT COALESCE(MAX(LEDGER_ID), 0) FROM ANSWER_LEDGER);
  WHILE I < P_ROWS DO
    CALL APPEND_LEDGER_ROW(RIGHT(REPEAT('0', 36) || RTRIM(CHAR(V_BASE + I + 1)), 36), 'api', 'AURELIA-CSP',
                           DATE('2026-01-01') + MOD(I, 120) DAYS,
                           'My grandmother died. Can I get the bereavement fare after I travel?',
                           'Yes, you can request it after you travel.',
                           'Bereavement fares must be requested before travel begins.',
                           'CORRECTED', 'CORRECTED_FROM_CLAUSES', 'bench:none', 'bench', 6000, P_VERDICTS,
                           V_ID, V_HASH, V_AT);
    SET I = I + 1;
    IF MOD(I, P_BATCH) = 0 THEN
      COMMIT;
      -- Write the dirty pages now: under a sustained load they would hold the active log until Db2's page-age
      -- target (240 s by default) and fill it (SQL0964C, ADM1822W) long before the rows run out.
      EXECUTE IMMEDIATE 'FLUSH BUFFERPOOLS ALL';
    END IF;
  END WHILE;
  COMMIT;
END"""


def prepare(settings: Settings, target: str = BENCH_SCHEMA) -> None:
    with db.connection(settings, "admin") as conn:
        schema.drop(conn, target)
        schema.install(conn, target)
        embeddings = get_embeddings(settings.embedding_model)
        seed.seed_policy(conn, embeddings, target)  # the release rules check each row's citation against it
        seed.seed_chain_head(conn, target)
        seed.seed_faq(conn, embeddings, target)  # the grants name every table
        schema.apply_grants(conn, settings.asof_app_user, settings.asof_editor_user, target)
        db.use_schema(conn, target)
        db.execute(conn, SQL_FILL)
        conn.commit()


def fill(settings: Settings, rows: int, batch: int = 5000, target: str = BENCH_SCHEMA) -> float:
    """Append `rows` more rows inside Db2; returns the seconds it took."""
    started = time.monotonic()
    with db.connection(settings, "admin") as conn:
        db.use_schema(conn, target)
        cur = conn.cursor()
        try:
            cur.callproc("CHAINBENCH_FILL", (rows, batch, VERDICTS))
        finally:
            cur.close()
        conn.commit()
    return time.monotonic() - started


def verify(settings: Settings, target: str = BENCH_SCHEMA) -> dict[str, Any]:
    """VERIFY_CHAIN once, as the runtime user (the only one that reads the ledger text unmasked)."""
    started = time.monotonic()
    with db.connection(settings, "app") as conn:
        status = ledger.verify_chain(conn, target)
    return {"status": status.status, "rows_checked": status.checked, "detail": status.detail,
            "seconds": round(time.monotonic() - started, 1)}


def verify_incremental(settings: Settings, target: str = BENCH_SCHEMA) -> dict[str, Any]:
    """VERIFY_CHAIN_FROM_CHECKPOINT once, as the runtime user: the rows since the latest checkpoint, then a new one."""
    started = time.monotonic()
    with db.connection(settings, "app") as conn:
        status = ledger.verify_from_checkpoint(conn, target, requested_by="chainbench")
    return {"status": status.status, "rows_checked": status.checked, "from_ledger_id": status.from_id,
            "detail": status.detail, "seconds": round(time.monotonic() - started, 1)}


def run(settings: Settings, rows: int, keep: bool = False, target: str = BENCH_SCHEMA, extra: int = 1000,
        machine: str = "") -> dict[str, Any]:
    prepare(settings, target)
    points: list[dict[str, Any]] = []
    loaded, load_s = 0, 0.0
    after: dict[str, Any] | None = None
    try:
        for size in [c for c in CHECKPOINTS if c < rows] + [rows]:
            load_s += fill(settings, size - loaded, target=target)
            loaded = size
            v = verify(settings, target)
            v |= {"rows": loaded, "load_seconds_total": round(load_s, 1)}
            v["incremental"] = verify_incremental(settings, target)
            points.append(v)
            print(f"  {loaded:>9,} rows: VERIFY_CHAIN {v['status']} in {v['seconds']} s; from the checkpoint "
                  f"{v['incremental']['status']} in {v['incremental']['seconds']} s "
                  f"({v['incremental']['rows_checked']:,} rows) (loaded in {v['load_seconds_total']} s so far)", flush=True)
            if v["status"] != "OK" or v["incremental"]["status"] != "OK":
                break
        else:
            if extra > 0:
                fill(settings, extra, target=target)
                after = verify_incremental(settings, target) | {"rows": loaded + extra, "appended": extra}
                print(f"  +{extra:,} rows: from the checkpoint {after['status']} in {after['seconds']} s "
                      f"({after['rows_checked']:,} rows)", flush=True)
    finally:
        if not keep:
            with db.connection(settings, "admin") as conn:
                schema.drop(conn, target)
    return {"ran_at": datetime.now(UTC).isoformat(timespec="seconds"), "git_commit": _git_commit(),
            "machine": machine, "rows": rows, "citations_per_row": 2, "points": points, "after_checkpoint": after}


def report(results: list[dict[str, Any]]) -> str:
    lines = ["# Chain benchmark", "",
             "How long `VERIFY_CHAIN` takes over a real hash chain: rows appended through the ledger's own "
             "`APPEND_LEDGER_ROW` (a SHA-256 link each, two claim citations each), then verified as the runtime user, "
             "which recomputes every row hash and checks every citation against the hashed verdicts. Run with "
             "`python -m asof.chainbench --rows N` ([chainbench.py](../src/asof/chainbench.py)).", "",
             "Runs since checkpoints exist also time `VERIFY_CHAIN_FROM_CHECKPOINT` ([12_chain_checkpoints.sql]"
             "(../src/asof/sql/12_chain_checkpoints.sql)) at each size: it re-checks the latest checkpoint's row, then "
             "recomputes only the rows after it as `VERIFY_CHAIN` does, and records a new checkpoint. The first one has "
             "no checkpoint to start from, so it is a full scan. The last line of such a run appends more rows and times "
             "one incremental verify of just those.", "",
             "What an incremental verify does not cover: it recomputes no row before the checkpoint. An owner who drops "
             "the triggers and edits an old row without touching its stored hashes is caught by the full `VERIFY_CHAIN` "
             "only. The chain-head anchors ([anchor.py](../src/asof/anchor.py)) compare each anchored `ROW_HASH` with the "
             "one the ledger stores now, so they catch a rebuild that rewrote stored hashes up to the last anchor, not an "
             "edit that left them in place; `python -m asof.anchor verify` runs the full `VERIFY_CHAIN` after that "
             "comparison. A checkpoint is a row in Db2 that the owner could also write, so it saves time and adds no "
             "trust: keep the full scan for audits (the nightly Airflow run) and the incremental one in between.", ""]
    for r in sorted(results, key=lambda x: x["ran_at"], reverse=True):
        lines += [f"## {r['rows']:,} rows, run {r['ran_at'][:16].replace('T', ' ')} UTC at `{r['git_commit']}`", "",
                  f"Machine: {r.get('machine') or MACHINE_BEFORE_LABELS}.", ""] + ([r["note"], ""] if r.get("note") else [])
        incremental = any("incremental" in p for p in r["points"])
        if incremental:
            lines += ["| Rows | VERIFY_CHAIN (full) | Time | Per 1,000 rows | From the checkpoint | Rows recomputed | "
                      "Time | Load so far |", "|---|---|---|---|---|---|---|---|"]
        else:
            lines += ["| Rows | VERIFY_CHAIN | Time | Per 1,000 rows | Load so far |", "|---|---|---|---|---|"]
        for p in r["points"]:
            per = p["seconds"] / max(p["rows"], 1) * 1000
            if incremental:
                i = p["incremental"]
                lines.append(f"| {p['rows']:,} | {p['status']} | {p['seconds']:,.1f} s | {per:.2f} s | {i['status']} | "
                             f"{i['rows_checked']:,} (from row {i['from_ledger_id']:,}) | {i['seconds']:,.1f} s | "
                             f"{p['load_seconds_total']:,.0f} s |")
            else:
                lines.append(f"| {p['rows']:,} | {p['status']} | {p['seconds']:,.1f} s | {per:.2f} s | "
                             f"{p['load_seconds_total']:,.0f} s |")
        after = r.get("after_checkpoint")
        if after:
            last = r["points"][-1]
            lines += ["", f"Then {after['appended']:,} more rows: `VERIFY_CHAIN_FROM_CHECKPOINT` {after['status']} in "
                      f"{after['seconds']:,.1f} s, recomputing {after['rows_checked']:,} rows (the checkpoint row at "
                      f"{after['from_ledger_id']:,} and the {after['appended']:,} after it), against "
                      f"{last['seconds']:,.1f} s for the full `VERIFY_CHAIN` over {last['rows']:,} rows."]
        lines.append("")
    return "\n".join(lines)


# The one run recorded before results carried a machine label (docs/db2.md describes it).
MACHINE_BEFORE_LABELS = "MacBook Air (Apple Silicon), Db2 12.1.5 in IBM's x86 image under Rosetta"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m asof.chainbench")
    p.add_argument("--rows", type=int, default=1_000_000)
    p.add_argument("--extra", type=int, default=1000, help="rows appended after the last size, then verified "
                   "from the checkpoint (0: skip)")
    p.add_argument("--machine", default="", help="where it ran, for the report (CPU, memory, what else was running)")
    p.add_argument("--keep", action="store_true", help="keep the CBENCH schema afterwards")
    args = p.parse_args(argv)
    result = run(get_settings(), args.rows, args.keep, extra=args.extra, machine=args.machine)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"chain__{args.rows}__{result['git_commit']}.json").write_text(json.dumps(result, indent=1))
    REPORT.write_text(report([json.loads(f.read_text()) for f in sorted(OUT_DIR.glob("*.json"))]))
    print(f"Wrote {REPORT.name}.")
    ok = all(p["status"] == "OK" and p.get("incremental", {}).get("status", "OK") == "OK" for p in result["points"])
    return 0 if ok and (result["after_checkpoint"] or {}).get("status", "OK") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
