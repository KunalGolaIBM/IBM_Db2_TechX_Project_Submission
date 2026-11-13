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

from . import db, federation, samples
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
        print("\n  model calls by stage (tokens as the provider counted them):")
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
    )
    print(f"  source engines: {pipeline.source_engines}")
    try:
        dialect = None if args.dialect == "all" else args.dialect
        statements = [] if args.workload == "samples" else statements_for(dialect)
        if args.workload != "corpus" and agent is not None:
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
