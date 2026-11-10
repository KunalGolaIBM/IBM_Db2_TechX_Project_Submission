"""Create the PayGuard schema in Db2 and load the knowledge base.

Usage:  python src/seed.py            (create if missing, load if empty)
        python src/seed.py --reset    (drop and rebuild everything)
"""
from __future__ import annotations

import argparse
import datetime as dt
import random
import sys

from config import settings
from db import Db2Repository
from embeddings import get_embedder
from risk import RiskEngine, ScreenRequest
from seed_data import ENTITIES, HISTORY, PATTERNS, REPORTS


def pattern_text(p: dict) -> str:
    return f'{p["title"]}. {p["description"]} Red flags: {p.get("red_flags", "")}'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="drop and recreate all PayGuard tables")
    args = ap.parse_args()

    embedder = get_embedder()
    repo = Db2Repository()
    print(f"Connected to Db2 {settings.db2_host}:{settings.db2_port}/{settings.db2_database}")
    print(f"Embedder: {embedder.name} ({settings.embed_dim} dims)")

    reset = args.reset
    try:
        stored = repo.get_meta("embedder")
        if stored and stored != embedder.name:
            print(f"Embedder changed ({stored} -> {embedder.name}); rebuilding vectors.")
            reset = True
    except Exception:
        pass  # schema does not exist yet

    repo.init_schema(settings.embed_dim, reset=reset)
    repo.set_meta("embedder", embedder.name)

    if repo.count_patterns() > 0:
        print("Knowledge base already loaded. Use --reset to rebuild.")
        return 0

    vecs = embedder.embed([pattern_text(p) for p in PATTERNS])
    for p, v in zip(PATTERNS, vecs):
        repo.insert_pattern(p, v)
    print(f"Inserted {len(PATTERNS)} scam patterns with VECTOR({settings.embed_dim}) embeddings")

    for etype, value, status, notes in ENTITIES:
        repo.upsert_entity(etype, value, status, notes, count_report=False)
    report_vecs = embedder.embed([r[5] for r in REPORTS])
    for (etype, value, cat, amount, cur, text), v in zip(REPORTS, report_vecs):
        eid = repo.upsert_entity(etype, value, "SUSPECT", count_report=True)
        repo.add_report(eid, "seed", cat, amount, cur, text, v)
    print(f"Inserted {len(ENTITIES)} entities and {len(REPORTS)} community reports")

    # Demo history goes through the real engine, then is spread over the last 14 days.
    engine = RiskEngine(repo, embedder)
    rng = random.Random(7)
    n = 0
    for _ in range(3):
        for merchant, email, amount, method, msg in HISTORY:
            amt = round(amount * rng.uniform(0.8, 1.2), 2) if amount else 0
            res = engine.screen(ScreenRequest(merchant, email, amt, "USD", method, msg, "NG"))
            when = dt.datetime.now() - dt.timedelta(hours=rng.randint(25, 14 * 24))
            repo.execute("UPDATE PG_SCREENINGS SET CREATED_AT = ? WHERE ID = ?",
                         (when.replace(microsecond=0), res.screening_id))
            n += 1
    print(f"Screened {n} historical payments through the engine")
    print("Done. Start the app:  uvicorn main:app --app-dir src --reload")
    return 0


if __name__ == "__main__":
    sys.exit(main())
