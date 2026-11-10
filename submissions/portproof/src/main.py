"""PortProof command line.

    python -m src.main                  # migrate the whole corpus and prove it
    python -m src.main --dialect mysql  # one source dialect
    python -m src.main --no-prove       # compile proof only (fast)
    python -m src.main --physical       # measured physical-design advice
    python -m src.main --ledger         # read the Db2 ledger back
"""
from __future__ import annotations

import argparse
import sys

from . import db
from .config import llm_config, runtime_config, setup_config
from .embeddings import LocalEmbeddings
from .fixmemory import FixMemory
from .pipeline import MigrationReport, Pipeline

BAR = "=" * 74


def _print_report(report: MigrationReport) -> None:
    print(f"\n{BAR}\nPortProof migration report\n{BAR}")
    for line in report.summary_lines():
        print(f"  {line}")

    print(f"\n{'case':30} {'status':18} {'proof'}")
    print("-" * 74)
    for result in report.results:
        proof = ""
        if result.semantic:
            proof = result.semantic.headline
        elif result.status in ("COMPILE_FAIL", "TRANSLATE_FAIL"):
            proof = f"SQLCODE={result.first_sqlcode} unrepaired"
        print(f"{result.case_name:30} {result.status:18} {proof[:40]}")

    different = [r for r in report.results if r.status == "PROVEN_DIFFERENT"]
    if different:
        print(f"\n{BAR}\nPROVEN DIFFERENT -- these compile on Db2 but change the answer\n{BAR}")
        for result in different:
            witness = result.semantic.witness if result.semantic else None
            print(f"\n  {result.case_name}")
            print(f"    source : {result.statement.sql[:150]}")
            print(f"    db2    : {(result.db2_sql or '')[:150]}")
            if witness:
                print(f"    dataset: {witness.variant} -- {witness.targets}")
                print(f"    source rows: {witness.source_rows[:3]}")
                print(f"    db2 rows   : {witness.db2_rows[:3]}")
            if result.semantic_cert:
                print(f"    certificate: {result.semantic_cert}")

    unstable = [r for r in report.results if r.status == "UNSTABLE"]
    if unstable:
        print(
            f"\n{BAR}\nOrder not determined by the SQL -- not a Db2 bug\n{BAR}"
        )
        print(
            "  The engines differ, and the SOURCE engine differs from itself on\n"
            "  the same rows inserted in the opposite order. The ORDER BY has\n"
            "  ties, so neither engine owes you this order. Add a tiebreaker.\n"
        )
        for result in unstable:
            print(f"  {result.case_name}")
            print(f"    source : {result.statement.sql[:150]}")
            if result.semantic and result.semantic.witness:
                w = result.semantic.witness
                print(f"    dataset: {w.variant}")
                print(f"    source rows: {w.source_rows[:3]}")
                print(f"    db2 rows   : {w.db2_rows[:3]}")

    semfixed = [r for r in report.results if r.semantically_repaired]
    if semfixed:
        print(
            f"\n{BAR}\nMeaning repaired, then re-proved against the source engine\n{BAR}"
        )
        print(
            "  These compiled on Db2 and returned the WRONG ROWS. Each rewrite\n"
            "  below was re-run through the same differential proof that caught\n"
            "  the divergence, and is reported only because that proof now agrees.\n"
        )
        for result in semfixed:
            fix = result.semantic_repair
            before = result.original_semantic
            print(f"  {result.case_name}")
            print(f"    rule   : {fix.rule}")
            print(f"    why    : {fix.because}")
            if before and before.witness:
                print(
                    f"    was    : {before.witness.source_rows[:2]} on "
                    f"{before.source_engine} vs {before.witness.db2_rows[:2]} on Db2"
                )
            print(f"    now    : {result.semantic.headline if result.semantic else ''}")
            print(f"    db2 sql: {(result.db2_sql or '')[:150]}")

    repaired = [r for r in report.results if r.repaired]
    if repaired:
        print(f"\n{BAR}\nRepaired, then re-verified by Db2\n{BAR}")
        for result in repaired:
            rules = sorted({r for a in result.repair.attempts for r in a.rules_fired})
            print(
                f"  {result.case_name:30} first SQLCODE={result.first_sqlcode:<8} "
                f"attempts={result.repair.attempt_count} rules={rules}"
            )


def _print_ledger(conn) -> None:
    print(f"\n{BAR}\nDb2 ledger (PORTPROOF.STATEMENT / VERDICT)\n{BAR}")
    rows = db.fetch_all(
        conn,
        "SELECT s.CASE_NAME, s.STATUS, s.ATTEMPTS, v.KIND, v.OUTCOME, v.INSTANCES, "
        "       SUBSTR(v.CERT_SHA, 1, 16) "
        "  FROM PORTPROOF.STATEMENT s LEFT JOIN PORTPROOF.VERDICT v ON v.STMT_ID = s.STMT_ID "
        " ORDER BY s.CASE_NAME, v.KIND",
    )
    print(f"{'case':28} {'status':18} {'kind':9} {'outcome':12} {'n':3} cert")
    for case, status, attempts, kind, outcome, instances, cert in rows:
        print(
            f"{str(case).strip():28} {str(status).strip():18} "
            f"{str(kind or '').strip():9} {str(outcome or '').strip():12} "
            f"{str(instances or ''):3} {str(cert or '').strip()}"
        )

    print("\n  failure rollup, maintained by the engine (MQT REFRESH IMMEDIATE):")
    for dialect, sqlcode, n in db.fetch_all(
        conn, "SELECT SRC_DIALECT, LAST_SQLCODE, N FROM PORTPROOF.MQT_FAILURE_BY_CODE ORDER BY N DESC"
    ):
        print(f"    {str(dialect).strip():10} SQLCODE={sqlcode:<8} {n} statement(s)")

    print("\n  time travel: how many statements existed at each recorded moment")
    for row in db.fetch_all(
        conn,
        "SELECT COUNT(*) FROM PORTPROOF.STATEMENT "
        "FOR SYSTEM_TIME AS OF CURRENT TIMESTAMP - 1 SECOND",
    ):
        print(f"    one second ago: {row[0]} statement(s)")
    row = db.fetch_one(conn, "SELECT COUNT(*) FROM PORTPROOF.STATEMENT_HIST")
    print(f"    rows the engine has preserved in the history table: {row[0] if row else 0}")


def _print_physical(advice: dict) -> None:
    print(f"\n{BAR}\nPhysical design, measured by Db2\n{BAR}")
    print(f"  {advice['compression'].headline}")
    print(f"  {advice['columnar'].headline}")
    hotspots = advice["hotspots"]
    if hotspots:
        print("\n  hottest statements in the package cache (real executions):")
        for text, executions, cpu in hotspots:
            print(f"    {executions:>6} exec  {cpu:>12.0f} us  {text[:58]}")
    else:
        print("  package cache: no monitored statements visible to this user")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="portproof", description=__doc__)
    parser.add_argument("--dialect", choices=["postgres", "mysql", "all"], default="all")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-prove", action="store_true", help="skip the semantic proof")
    parser.add_argument("--no-learn", action="store_true", help="do not write the fix memory")
    parser.add_argument(
        "--no-escalate",
        action="store_true",
        help="do not hand stalled statements to human review",
    )
    parser.add_argument("--physical", action="store_true", help="measured physical-design advice")
    parser.add_argument("--ledger", action="store_true", help="print the Db2 ledger and exit")
    args = parser.parse_args(argv)

    cfg = llm_config()
    try:
        app_conn = db.connect(runtime_config(), role="app")
        owner_conn = db.connect(setup_config(), role="setup")
    except db.Db2Error as exc:
        print(f"Db2 connection failed: {exc}", file=sys.stderr)
        print("Is the container up? Did you run `python -m src.setup_db`?", file=sys.stderr)
        return 2
    db.execute(app_conn, "SET CURRENT SCHEMA PORTPROOF")

    if args.ledger:
        _print_ledger(app_conn)
        return 0

    print(f"PortProof on Db2 {db.server_version(owner_conn)}")
    print(f"  runtime user : {db.current_identity(app_conn)[0]} (least privilege)")
    print(f"  owner user   : {db.current_identity(owner_conn)[0]}")
    print(
        f"  repair model : {cfg.provider}"
        + ("  (deterministic rules, no API key needed)" if cfg.is_mock else f" / {cfg.model}")
    )

    memory: FixMemory | None = None
    if not args.no_learn:
        try:
            memory = FixMemory(app_conn, embeddings=LocalEmbeddings())
            print(f"  fix memory   : {memory.count()} verified repairs in Db2")
        except Exception as exc:
            print(f"  fix memory   : unavailable ({str(exc)[:70]})")
            memory = None

    pipeline = Pipeline(
        app_conn=app_conn,
        owner_conn=owner_conn,
        memory=memory,
        learn=not args.no_learn,
    )
    try:
        report = pipeline.run(
            dialect=None if args.dialect == "all" else args.dialect,
            prove_meaning=not args.no_prove,
            limit=args.limit,
        )
        _print_report(report)
        if not args.no_escalate:
            escalated = pipeline.escalate_stalled()
            print(
                f"\n  escalated to human review by the engine: {escalated} "
                f"statement(s) that burned the repair budget without a proof"
            )
        if args.physical:
            _print_physical(pipeline.physical_advice())
        if memory is not None:
            print(f"\n  fix memory now holds {memory.count()} verified repairs")
    finally:
        pipeline.close()

    print(f"\nLedger written to Db2. Read it with:  python -m src.main --ledger")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
