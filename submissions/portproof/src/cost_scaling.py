"""Measure what the model tiers cost as the source database grows.

    python -m src.cost_scaling                       # 1 thousand to 1 million rows, SQLite
    python -m src.cost_scaling --engine postgres     # the same on a real PostgreSQL
    python -m src.cost_scaling --sizes 1000 5000000

The claim under test is that the cost of the AI does not depend on the size of
the database being migrated. The experiment holds everything fixed except the
number of rows in the source tables: the same schema, the same three queries,
no dataset cache and no fix memory, so nothing is answered for free the second
time. For each size it reports

* how long the source engine took to profile its own tables (this is the one
  step that reads the data, and it is SQL on the source, not a model),
* how many model calls were made and how many tokens the provider counted,
* a hash of every prompt that was sent.

If the claim holds, the last three are the same on every row of the table, and
the prompt hash proves it is not a coincidence of similar numbers: the model
was sent byte-for-byte the same text whether the source held a thousand rows or
a million.

With no API key the model tiers do not run. The experiment then reports the
size of the prompt that would be sent, which is the quantity the claim is
about.
"""
from __future__ import annotations

import argparse
import hashlib
import time

from . import db, samples
from .config import llm_config, runtime_config, setup_config
from .corpus import Statement, Variant
from .datasets import DATASET_PROMPT, DatasetAgent, introspect, profile
from .llm import METER, HttpRepairLLM, build_model
from .pipeline import Pipeline

#: The three bank queries that exercise all three model stages between them.
QUERIES = ("large_euro_transactions", "rent_payments", "frozen_or_closed")

_FILL = {
    "sqlite": (
        "INSERT INTO accounts SELECT n, 'Owner ' || n, "
        "CASE n % 3 WHEN 0 THEN 'ACTIVE' WHEN 1 THEN 'FROZEN' ELSE 'CLOSED' END, "
        "(n % 50) * 100.0, '2020-01-01 09:00:00' FROM seq",
        "INSERT INTO transactions SELECT n, n, (n % 997) * 13.37, "
        "CASE n % 2 WHEN 0 THEN 'EUR' ELSE 'USD' END, 'memo ' || n, "
        "'2026-03-01 08:00:00' FROM seq",
    ),
    "postgres": (
        "INSERT INTO accounts SELECT n, 'Owner ' || n, "
        "CASE n % 3 WHEN 0 THEN 'ACTIVE' WHEN 1 THEN 'FROZEN' ELSE 'CLOSED' END, "
        "(n % 50) * 100.0, TIMESTAMP '2020-01-01 09:00:00' FROM generate_series(1, {n}) AS n",
        "INSERT INTO transactions SELECT n, n, (n % 997) * 13.37, "
        "CASE n % 2 WHEN 0 THEN 'EUR' ELSE 'USD' END, 'memo ' || n, "
        "TIMESTAMP '2026-03-01 08:00:00' FROM generate_series(1, {n}) AS n",
    ),
}


def _fill(engine, dialect: str, rows: int) -> None:
    """Put ``rows`` rows in each bank table, generated inside the engine."""
    ddl, _ = samples.SAMPLES["bank"]
    engine.load(Variant("bank:seed", "", {"accounts": [], "transactions": []},
                        ddl=ddl, tables=("accounts", "transactions")))
    conn = engine._conn
    if dialect == "sqlite":
        conn.execute("CREATE TEMP TABLE seq (n INTEGER)")
        conn.execute(
            "WITH RECURSIVE c(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM c WHERE n < ?) "
            "INSERT INTO seq SELECT n FROM c", (rows,))
        for sql in _FILL[dialect]:
            conn.execute(sql)
        conn.execute("DROP TABLE seq")
        conn.commit()
    else:
        with conn.cursor() as cur:
            for sql in _FILL[dialect]:
                cur.execute(sql.format(n=rows))


def _source(dialect: str):
    if dialect == "sqlite":
        from .engines import SqliteSource

        return SqliteSource()
    from .counterexample import PostgresSource

    return PostgresSource()


def measure(rows: int, dialect: str, app_conn, owner_conn) -> dict:
    engine = _source(dialect)
    prompts: list[str] = []
    original = HttpRepairLLM.ask

    def recording(self, system, user, *, stage, case_name=""):
        prompts.append(f"{stage}\n{system}\n{user}")
        return original(self, system, user, stage=stage, case_name=case_name)

    HttpRepairLLM.ask = recording
    METER.reset()
    pipeline = None
    try:
        _fill(engine, dialect, rows)
        schema = introspect(engine, "bank", tables=("accounts", "transactions"))
        started = time.monotonic()
        stats = profile(engine, schema)
        profile_ms = (time.monotonic() - started) * 1000

        # No store and no memory: nothing may be answered from a cache, or the
        # second size would look cheaper than the first for the wrong reason.
        agent = DatasetAgent(model=build_model())
        agent.register("bank", dialect, schema, stats)
        pipeline = Pipeline(app_conn=app_conn, owner_conn=owner_conn, sources={dialect: engine},
                            dataset_agent=agent, learn=False, memory=None)
        todo = [Statement(dialect, f"bank.{name}", sql, schema="bank")
                for s, name, sql in samples.WORKLOAD if s == "bank" and name in QUERIES]
        started = time.monotonic()
        results = [pipeline.run_statement(s) for s in todo]
        proof_s = time.monotonic() - started
        would_send = DATASET_PROMPT.format(
            dialect=dialect, schema=schema.prompt_text(), sql=todo[0].sql, reason="(reason)")
        calls = list(METER.calls)
        return {
            "rows": stats.total_rows,
            "profile_ms": profile_ms,
            "proof_s": proof_s,
            "calls": len(calls),
            "prompt_tokens": sum(c.prompt_tokens for c in calls),
            "largest_prompt": max((c.prompt_tokens for c in calls), default=0),
            "output_tokens": sum(c.completion_tokens for c in calls),
            "prompt_hash": hashlib.sha256("\x00".join(sorted(prompts)).encode()).hexdigest()[:12]
            if prompts else "-",
            "dataset_prompt_chars": len(would_send),
            "statuses": ",".join(r.status.replace("PROVEN_", "")[:5] for r in results),
        }
    finally:
        HttpRepairLLM.ask = original
        go = getattr(engine, "home", None)
        if dialect != "sqlite" and callable(go):
            go()
            with engine._conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS transactions")
                cur.execute("DROP TABLE IF EXISTS accounts")
        if pipeline is not None:
            pipeline.close()
        else:
            engine.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="portproof-cost-scaling", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sizes", type=int, nargs="+", default=[1_000, 100_000, 1_000_000],
                        help="rows per table")
    parser.add_argument("--engine", choices=["sqlite", "postgres"], default="sqlite")
    args = parser.parse_args(argv)

    cfg = llm_config()
    app_conn = db.connect(runtime_config(), role="app")
    owner_conn = db.connect(setup_config(), role="setup")
    db.execute(app_conn, "SET CURRENT SCHEMA PORTPROOF")
    print(f"source engine: {args.engine}    model: "
          f"{cfg.model if cfg.has_model else 'none configured (prompt sizes only)'}")
    print(f"queries: {', '.join(QUERIES)} (no dataset cache, no fix memory)\n")
    header = (f"{'source rows':>12} {'profile ms':>11} {'proof s':>8} {'model calls':>12} "
              f"{'tokens in':>10} {'largest prompt':>15} {'tokens out':>11} {'prompts sha':>13}")
    print(header)
    print("-" * len(header))
    seen = []
    for size in args.sizes:
        m = measure(size, args.engine, app_conn, owner_conn)
        seen.append(m)
        print(f"{m['rows']:>12,} {m['profile_ms']:>11.1f} {m['proof_s']:>8.1f} {m['calls']:>12} "
              f"{m['prompt_tokens']:>10} {m['largest_prompt']:>15} {m['output_tokens']:>11} "
              f"{m['prompt_hash']:>13}")
    same_prompts = len({m["prompt_hash"] for m in seen}) == 1
    same_input = len({m["prompt_tokens"] for m in seen}) == 1
    print(f"\ndataset prompt size: {seen[0]['dataset_prompt_chars']} characters at every size"
          if len({m['dataset_prompt_chars'] for m in seen}) == 1 else "\ndataset prompt size VARIED")
    print(f"identical prompts at every size: {'yes' if same_prompts else 'NO'}")
    print(f"identical input tokens at every size: {'yes' if same_input else 'NO'}")
    return 0 if same_prompts and same_input else 1


if __name__ == "__main__":
    raise SystemExit(main())
