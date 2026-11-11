"""Db2 Error Doctor command line.

    python src/main.py ingest
    python src/main.py ask "SQL0204N \"DB2INST1.ORDERS\" is an undefined name. SQLSTATE=42704"
    python src/main.py stats
"""

from __future__ import annotations

import argparse
import sys

import db
import doctor
from config import ConfigError, load_settings
from kb import InputError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="db2-error-doctor", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ingest", help="load the SQLCODE knowledge base into Db2")
    ask = sub.add_parser("ask", help="diagnose a Db2 error message")
    ask.add_argument("error", help="the error text, in quotes")
    ask.add_argument("-k", type=int, default=3, help="number of vector matches (1-10)")
    stats = sub.add_parser("stats", help="show the most frequently diagnosed errors")
    stats.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    try:
        conn = db.connect(settings)
    except Exception as exc:
        print(f"Could not connect to Db2 at {settings.host}:{settings.port}: {exc}", file=sys.stderr)
        return 3

    try:
        if args.command == "ingest":
            count = doctor.ingest(conn, settings, doctor.build_embeddings(settings))
            print(f"Loaded {count} entries into {settings.kb_table} and {settings.vector_table}.")
        elif args.command == "ask":
            db.ensure_schema(conn, settings)
            embeddings = doctor.build_embeddings(settings)
            store = doctor.open_store(conn, settings, embeddings)
            result = doctor.diagnose(
                conn, settings, store, args.error, k=args.k, explain=doctor.make_explainer(settings)
            )
            print(doctor.format_diagnosis(result))
        else:
            db.ensure_schema(conn, settings)
            rows = db.top_errors(conn, settings, args.limit)
            if not rows:
                print("No diagnoses logged yet.")
            for code, title, hits, last_seen in rows:
                print(f"{hits:>4}  SQLCODE {code:<8} {title or '(unknown)'}  last seen {last_seen}")
    except InputError as exc:
        print(f"Invalid input: {exc}", file=sys.stderr)
        return 2
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
