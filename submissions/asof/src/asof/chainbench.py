"""Chain benchmark: how long VERIFY_CHAIN takes over a real hash chain, at volume.

    python -m asof.chainbench [--rows 1000000] [--keep]

Installs the AsOf schema in a scratch schema (CBENCH), then appends the rows inside Db2 through the ledger's own
APPEND_LEDGER_ROW, so every row carries a real SHA-256 link and two claim citations, as a check with two claims
does. A stored procedure loops on the server and commits every 5,000 rows, flushing the buffer pools so dirty pages
never hold the log, and the load costs no network round trips. Then it runs VERIFY_CHAIN as the runtime user, which
recomputes every row hash and checks every citation against the hashed verdicts, and records the time at each size it
passes on the way (10,000, 100,000, then the full count). Results go to docs/chain_benchmark.md and docs/chainbench/.

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

# Two claims, as a typical check records them; APPEND_LEDGER_ROW shreds them into CLAIM_CITATION.
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
                           DATE('2026-03-10') + MOD(I, 300) DAYS,
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
        seed.seed_documents(conn, target)
        seed.seed_chain_head(conn, target)
        seed.seed_faq(conn, get_embeddings(settings.embedding_model), target)  # the grants name every table
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


def run(settings: Settings, rows: int, keep: bool = False, target: str = BENCH_SCHEMA) -> dict[str, Any]:
    prepare(settings, target)
    points, loaded, load_s = [], 0, 0.0
    try:
        for size in [c for c in CHECKPOINTS if c < rows] + [rows]:
            load_s += fill(settings, size - loaded, target=target)
            loaded = size
            v = verify(settings, target)
            v |= {"rows": loaded, "load_seconds_total": round(load_s, 1)}
            points.append(v)
            print(f"  {loaded:>9,} rows: VERIFY_CHAIN {v['status']} in {v['seconds']} s "
                  f"(loaded in {v['load_seconds_total']} s so far)", flush=True)
            if v["status"] != "OK":
                break
    finally:
        if not keep:
            with db.connection(settings, "admin") as conn:
                schema.drop(conn, target)
    return {"ran_at": datetime.now(UTC).isoformat(timespec="seconds"), "git_commit": _git_commit(),
            "rows": rows, "citations_per_row": 2, "points": points}


def report(results: list[dict[str, Any]]) -> str:
    lines = ["# Chain benchmark", "",
             "How long `VERIFY_CHAIN` takes over a real hash chain: rows appended through the ledger's own "
             "`APPEND_LEDGER_ROW` (a SHA-256 link each, two claim citations each), then verified as the runtime user, "
             "which recomputes every row hash and checks every citation against the hashed verdicts. Run with "
             "`python -m asof.chainbench --rows N` ([chainbench.py](../src/asof/chainbench.py)).", ""]
    for r in sorted(results, key=lambda x: x["ran_at"], reverse=True):
        lines += [f"## {r['rows']:,} rows, run {r['ran_at'][:16].replace('T', ' ')} UTC at `{r['git_commit']}`", "",
                  "| Rows | VERIFY_CHAIN | Time | Per 1,000 rows | Load so far |", "|---|---|---|---|---|"]
        for p in r["points"]:
            per = p["seconds"] / max(p["rows"], 1) * 1000
            lines.append(f"| {p['rows']:,} | {p['status']} | {p['seconds']:,.1f} s | {per:.2f} s | "
                         f"{p['load_seconds_total']:,.0f} s |")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m asof.chainbench")
    p.add_argument("--rows", type=int, default=1_000_000)
    p.add_argument("--keep", action="store_true", help="keep the CBENCH schema afterwards")
    args = p.parse_args(argv)
    result = run(get_settings(), args.rows, args.keep)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"chain__{args.rows}__{result['git_commit']}.json").write_text(json.dumps(result, indent=1))
    REPORT.write_text(report([json.loads(f.read_text()) for f in sorted(OUT_DIR.glob("*.json"))]))
    print(f"Wrote {REPORT.name}.")
    return 0 if all(p["status"] == "OK" for p in result["points"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
