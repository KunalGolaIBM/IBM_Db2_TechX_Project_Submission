"""PortProof command line.

    python -m src.main                  # migrate the whole corpus and prove it
    python -m src.main --dialect mysql  # one source dialect
    python -m src.main --no-prove       # compile proof only (fast)
    python -m src.main --physical       # measured physical-design advice
    python -m src.main --ledger         # read the Db2 ledger back
    python -m src.main --workload samples   # schemas discovered on the source
    python -m src.main --datasets original  # the first six datasets only
    python -m src.main --budget 6       # the agent's best six datasets per query
    python -m src.main --cost           # what the model calls cost, from Db2
    python -m src.main --yield          # which datasets have been finding things
"""
from __future__ import annotations

import argparse
import sys

from . import costgate, db, federation, samples
from .config import llm_config, runtime_config, setup_config
from .corpus import DIALECTS, ORIGINAL_VARIANTS, VARIANTS, statements_for
from .datasets import DatasetAgent, DatasetStore
from .embeddings import LocalEmbeddings
from .fixmemory import FixMemory
from .llm import METER, build_model
from .pipeline import MigrationReport, Pipeline

BAR = "=" * 74


def _print_report(report: MigrationReport) -> None:
    print(f"\n{BAR}\nPortProof migration report\n{BAR}")
    for line in report.summary_lines():
        print(f"  {line}")

    print("\n  by source dialect:")
    for line in report.by_dialect():
        print(line)

    if report.agent_lines:
        print("\n  dataset agent:")
        for line in report.agent_lines:
            print(f"    {line}")

    stages = METER.by_stage()
    if stages:
        counted = ("estimated from text length; Db2 made the calls"
                   if any(c.estimated for c in METER.calls) else "as the provider counted them")
        print(f"\n  model calls by stage (tokens {counted}):")
        for stage, (calls, prompt, completion) in sorted(stages.items()):
            print(f"    {stage:16} {calls:3} call(s)  {prompt:7} in  {completion:7} out")

    print(f"\n{'case':38} {'status':18} {'proof'}")
    print("-" * 100)
    for result in report.results:
        proof = ""
        if result.semantic:
            proof = result.semantic.headline
        elif result.status in ("COMPILE_FAIL", "TRANSLATE_FAIL"):
            proof = f"SQLCODE={result.first_sqlcode} unrepaired"
        print(f"{result.case_name:38} {result.status:18} {proof[:42]}")

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
            small = result.minimal
            if small is not None:
                print(f"    smallest input that still disagrees: {small.rows_after} row(s), "
                      f"down from {small.rows_before} ({small.trials} trials on both engines)")
                for table, rows in small.rows.items():
                    for row in rows[:4]:
                        print(f"      {table}: {tuple(str(v) for v in row)}")
                print(f"      source returns {small.source_rows[:3]}")
                print(f"      db2 returns    {small.db2_rows[:3]}")
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
            if result.cost_ratio is not None:
                flag = ("  <-- correct, and estimated much slower"
                        if result.cost_ratio >= costgate.SLOWER_RATIO else "")
                print(f"    cost   : {result.cost_before:.1f} -> {result.cost_after:.1f} timerons "
                      f"by Db2's estimate ({result.cost_ratio:.1f}x){flag}")

    repaired = [r for r in report.results if r.repaired]
    if repaired:
        print(f"\n{BAR}\nRepaired, then re-verified by Db2\n{BAR}")
        for result in repaired:
            rules = sorted({r for a in result.repair.attempts for r in a.rules_fired})
            print(
                f"  {result.case_name:30} first SQLCODE={result.first_sqlcode:<8} "
                f"attempts={result.repair.attempt_count} by={result.repair.fixed_by:6} rules={rules}"
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


def _print_cost(conn) -> None:
    """The model-call ledger, summed by the engine."""
    print(f"\n{BAR}\nModel calls recorded in Db2 (PORTPROOF.LLM_CALL)\n{BAR}")
    rows = db.fetch_all(
        conn,
        "SELECT STAGE, MODEL, CALLS, PROMPT_TOKENS, COMPLETION_TOKENS, AVG_LATENCY_MS "
        "FROM PORTPROOF.LLM_COST ORDER BY STAGE",
    )
    if not rows:
        print("  no model has been called")
        return
    print(f"  {'stage':16} {'model':24} {'calls':>5} {'tokens in':>10} {'tokens out':>10} {'avg ms':>7}")
    for stage, model, calls, prompt, completion, latency in rows:
        print(
            f"  {str(stage).strip():16} {str(model).strip():24} {calls:>5} "
            f"{prompt:>10} {completion:>10} {int(latency or 0):>7}"
        )
    row = db.fetch_one(
        conn,
        "SELECT COUNT(*), COALESCE(SUM(PROMPT_TOKENS), 0), COALESCE(SUM(COMPLETION_TOKENS), 0), "
        "COALESCE(MAX(PROMPT_TOKENS), 0) FROM PORTPROOF.LLM_CALL",
    )
    print(
        f"\n  total: {row[0]} call(s), {row[1]} tokens in, {row[2]} tokens out; "
        f"largest single prompt {row[3]} tokens"
    )


def _print_yield(conn) -> None:
    """What the dataset agent has learned, read straight from its log."""
    store = DatasetStore(conn)
    datasets, runs = store.count()
    print(f"\n{BAR}\nDataset cache in Db2: {datasets} datasets, {runs} logged runs\n{BAR}")
    for origin, n in db.fetch_all(
        conn, "SELECT ORIGIN, COUNT(*) FROM PORTPROOF.DATASET GROUP BY ORIGIN ORDER BY ORIGIN"
    ):
        print(f"  {str(origin).strip():10} {n}")
    print(f"\n  {'strategy':24} {'dialect':9} {'runs':>5} {'returned rows':>14} {'exposed a divergence':>21}")
    for strategy, dialect, n, substantive, kills in db.fetch_all(
        conn,
        "SELECT STRATEGY, SRC_DIALECT, RUNS, SUBSTANTIVE, KILLS FROM PORTPROOF.DATASET_YIELD "
        "ORDER BY KILLS DESC, SUBSTANTIVE DESC, STRATEGY FETCH FIRST 40 ROWS ONLY",
    ):
        print(
            f"  {str(strategy).strip():24} {str(dialect).strip():9} {n:>5} {substantive:>14} {kills:>21}"
        )


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


def _captured_workload(args, pipeline, agent) -> list:
    """The source's own statements, over a schema read from its catalogue."""
    from . import capture
    from .datasets import introspect, profile

    engine = pipeline.sources.get(args.dialect)
    if engine is None:
        raise SystemExit(f"no {args.dialect} source engine is reachable")
    tables = tuple(t.strip() for t in args.tables.split(",") if t.strip())
    if args.sql_file:
        taken = capture.from_file(args.sql_file, args.dialect, tables)
    else:
        try:
            taken = capture.from_engine(engine, args.dialect, tables, top=args.top)
        except ValueError as exc:
            raise SystemExit(f"  capture failed: {exc}")
    print(f"  captured     : {taken.summary()}")
    schema = introspect(engine, "captured", tables=tables)
    prof = profile(engine, schema)
    agent.register("captured", args.dialect, schema, prof)
    print(
        f"  discovered   : {args.dialect}/captured -- {len(schema.tables)} tables, "
        f"{sum(len(t.columns) for t in schema.tables)} columns, "
        f"{prof.total_rows} rows profiled (fingerprint {schema.fingerprint})"
    )
    return taken.statements("captured")


def _gate(report, fail_on: str) -> int:
    """The exit code for a CI job: 0 passes the branch, 2 holds it."""
    if fail_on == "none":
        return 0
    if fail_on == "different":
        held = [r for r in report.results if r.status in ("PROVEN_DIFFERENT", "COMPILE_FAIL")]
    else:
        held = [r for r in report.results if r.status != "PROVEN_EQUIVALENT"]
    if held:
        print(f"\n  GATE ({fail_on}): {len(held)} statement(s) hold the migration:")
        for r in held[:20]:
            print(f"    {r.case_name:38} {r.status}")
        return 2
    print(f"\n  GATE ({fail_on}): passed")
    return 0


def _write_json(report, path: str) -> None:
    import json

    rows = []
    for r in report.results:
        witness = r.semantic.witness if r.semantic else None
        rows.append({
            "case": r.case_name,
            "dialect": r.statement.dialect,
            "status": r.status,
            "source_sql": r.statement.sql,
            "db2_sql": r.db2_sql,
            "first_sqlcode": r.first_sqlcode,
            "compile_repaired_by": r.repair.fixed_by if r.repair and r.repaired else None,
            "meaning_repaired_by": r.semantic_repair.rule
            if r.semantic_repair and r.semantic_repair.repaired else None,
            "evidence": r.semantic.strength if r.semantic else None,
            "datasets": r.datasets_used,
            "witness_dataset": witness.variant if witness and not witness.agreed else None,
            "minimal_counterexample": r.minimal.as_detail() if r.minimal else None,
            "estimated_cost_before": r.cost_before,
            "estimated_cost_after": r.cost_after,
            "compile_certificate": r.compile_cert,
            "semantic_certificate": r.semantic_cert,
        })
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"statements": len(rows), "by_status": counts, "results": rows},
                  handle, indent=2, default=str)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="portproof", description=__doc__)
    parser.add_argument("--dialect", choices=[*DIALECTS, "all"], default="all")
    parser.add_argument(
        "--workload",
        choices=["corpus", "samples", "all"],
        default="all",
        help="corpus: the fixture statements; samples: two schemas discovered "
        "on each source engine; all: both (default)",
    )
    parser.add_argument(
        "--datasets",
        choices=["agent", "all", "original"],
        default="agent",
        help="agent: cached, generated and query-aware datasets (default); "
        "all: the twelve hand-built ones; original: the first six",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=0,
        help="with --datasets agent, prove each statement on only its N "
        "best-ranked datasets (0 = all of them)",
    )
    parser.add_argument(
        "--capture", action="store_true",
        help="take the workload from the source engine's own statement record "
        "(needs one --dialect and --tables)",
    )
    parser.add_argument(
        "--sql-file", default="",
        help="take the workload from a .sql file, one statement per ';' "
        "(needs one --dialect and --tables)",
    )
    parser.add_argument(
        "--tables", default="",
        help="comma-separated tables of the schema being migrated; with --capture "
        "or --sql-file, only statements over these tables are proved",
    )
    parser.add_argument("--top", type=int, default=50,
                        help="with --capture, the N most executed statements (default 50)")
    parser.add_argument(
        "--fail-on", choices=["none", "different", "unproven"], default="none",
        help="exit 2 if any statement is PROVEN DIFFERENT (different), or if any "
        "is not PROVEN EQUIVALENT (unproven). For a CI gate on a migration branch",
    )
    parser.add_argument("--report-json", default="",
                        help="also write the per-statement verdicts to this file as JSON")
    parser.add_argument("--no-minimise", action="store_true",
                        help="do not shrink the counterexample of a PROVEN DIFFERENT statement")
    parser.add_argument("--cost", action="store_true", help="print the model-call ledger and exit")
    parser.add_argument(
        "--yield", dest="show_yield", action="store_true",
        help="print the dataset cache and its yield log, and exit",
    )
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
    parser.add_argument(
        "--federation",
        action="store_true",
        help="ask Db2 to compare the source rows against its own, and exit",
    )
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

    if args.cost:
        _print_cost(app_conn)
        return 0

    if args.show_yield:
        _print_yield(app_conn)
        return 0

    if args.federation:
        # The owner connection, not the application one: the fixture tables the
        # comparison reads belong to the schema owner, and the least-privilege
        # runtime identity is deliberately not allowed to read them.
        print(federation.report(owner_conn))
        return 0

    print(f"PortProof on Db2 {db.server_version(owner_conn)}")
    print(f"  runtime user : {db.current_identity(app_conn)[0]} (least privilege)")
    print(f"  owner user   : {db.current_identity(owner_conn)[0]}")
    print(f"  repair policy: {cfg.provider} -- {cfg.label}")

    memory: FixMemory | None = None
    if not args.no_learn:
        try:
            memory = FixMemory(app_conn, embeddings=LocalEmbeddings())
            print(f"  fix memory   : {memory.count()} verified repairs in Db2")
        except Exception as exc:
            print(f"  fix memory   : unavailable ({str(exc)[:70]})")
            memory = None

    captured_mode = bool(args.capture or args.sql_file)
    if captured_mode:
        if args.dialect == "all" or not args.tables.strip():
            parser.error("--capture and --sql-file need one --dialect and --tables")
        args.workload = "captured"
    agent: DatasetAgent | None = None
    if args.datasets == "agent" or args.workload != "corpus":
        agent = DatasetAgent(
            store=DatasetStore(app_conn),
            model=build_model(cfg),
            max_datasets=args.budget,
            builtin=ORIGINAL_VARIANTS if args.datasets == "original" else VARIANTS,
            learn=not args.no_learn,
        )
    pipeline = Pipeline(
        app_conn=app_conn,
        owner_conn=owner_conn,
        memory=memory,
        learn=not args.no_learn,
        dataset_agent=agent,
        variants=ORIGINAL_VARIANTS if args.datasets == "original" else VARIANTS,
        minimise=not args.no_minimise,
    )
    print(f"  source engines: {pipeline.source_engines}")
    status = 0
    try:
        dialect = None if args.dialect == "all" else args.dialect
        statements = [] if args.workload in ("samples", "captured") else statements_for(dialect)
        if captured_mode:
            statements = _captured_workload(args, pipeline, agent)
        elif args.workload != "corpus" and agent is not None:
            # Play the customer: put two schemas in each source engine, then
            # find them again through the engine's own catalogue.
            sources = {
                d: s for d, s in pipeline.sources.items() if dialect in (None, d)
            }
            found = samples.discover(sources, agent)
            for (name, found_dialect), (schema, prof) in sorted(found.items()):
                print(
                    f"  discovered   : {found_dialect}/{name} -- {len(schema.tables)} tables, "
                    f"{sum(len(t.columns) for t in schema.tables)} columns, "
                    f"{prof.total_rows} rows profiled (fingerprint {schema.fingerprint})"
                )
            statements += samples.statements(tuple(sources))
        report = pipeline.run(
            prove_meaning=not args.no_prove,
            limit=args.limit,
            statements=statements,
        )
        _print_report(report)
        if args.report_json:
            _write_json(report, args.report_json)
            print(f"\n  verdicts written to {args.report_json}")
        status = _gate(report, args.fail_on)
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
    return status


if __name__ == "__main__":
    raise SystemExit(main())
