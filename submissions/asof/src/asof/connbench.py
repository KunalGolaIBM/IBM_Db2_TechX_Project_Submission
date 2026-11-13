"""What connection handling costs a check: a fresh connection per use against the runtime pool.

    python -m asof.connbench [--rounds 3]

Runs the built-in checks whose drafts are fixed text, in replay mode (so no model time is mixed
in), in a scratch schema that is dropped afterwards: first with a new connection for every use,
as the app did before the pool, then through db.ConnectionPool, as the API does now. Prints the
median and mean per check and how often each decision matched the recording.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from datetime import date

from . import db, replay, schema, seed
from .config import ConfigError, get_settings
from .embeddings import get_embeddings
from .gate import Gate, GateRequest

BENCH_SCHEMA = "ASOF_CONNBENCH"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m asof.connbench", description=__doc__.split("\n\n")[0])
    parser.add_argument("--rounds", type=int, default=3, choices=range(1, 11), metavar="1-10")
    args = parser.parse_args(argv)
    try:
        settings = get_settings()
        recording = replay.Recording.load()
        emb = get_embeddings(settings.embedding_model)
        cases = [c for c in recording.scenarios["checks"] if c["draft"]]
        with db.connection(settings, "admin") as admin:
            schema.drop(admin, BENCH_SCHEMA)
            schema.install(admin, BENCH_SCHEMA)
            seed.seed_policy(admin, emb, BENCH_SCHEMA)
            seed.seed_chain_head(admin, BENCH_SCHEMA)
            seed.seed_faq(admin, emb, BENCH_SCHEMA)
            schema.apply_grants(admin, settings.asof_app_user, settings.asof_editor_user, BENCH_SCHEMA)
    except (ConfigError, db.DatabaseError) as exc:
        print(f"cannot set up the benchmark: {exc}")
        return 2
    pool = db.ConnectionPool(settings, "app")
    try:
        for label, connect in (("fresh connection per use", lambda: db.connect(settings, "app")),
                               ("connection pool", pool.connect)):
            gate = Gate(replay.ReplayLLM(recording), emb, connect, BENCH_SCHEMA)
            times, same = [], 0
            for _ in range(args.rounds):
                for c in cases:
                    started = time.perf_counter()
                    r = gate.check(GateRequest(c["question"], c["draft"], date.fromisoformat(c["as_of"]), c["doc_id"], "eval"))
                    times.append((time.perf_counter() - started) * 1000)
                    same += r.decision == c["decision"]
            print(f"{label:26} median {statistics.median(times):7.0f} ms, mean {statistics.mean(times):7.0f} ms per check "
                  f"over {len(times)} checks; {same} of {len(times)} decisions as recorded", flush=True)
        print(f"the pool opened {pool.opened} connection(s) in all")
    finally:
        pool.close()
        with db.connection(settings, "admin") as admin:
            schema.drop(admin, BENCH_SCHEMA)
    return 0


if __name__ == "__main__":
    sys.exit(main())
