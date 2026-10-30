"""Runbook lifecycle management using Db2 metadata operations (no re-embedding).

Examples:
    python manage.py stats
    python manage.py list --env prod
    python manage.py list --all
    python manage.py deprecate RB-001
    python manage.py restore RB-001
    python manage.py purge
"""
import argparse
from typing import Any

from config import get_document_store


def eq(field: str, value: str) -> dict[str, Any]:
    return {"field": f"meta.{field}", "operator": "==", "value": value}


def cmd_stats(store, args) -> None:
    print(f"Total chunks: {store.count_documents()}")
    print(f"  active:     {store.count_documents_by_filter(eq('status', 'active'))}")
    print(f"  deprecated: {store.count_documents_by_filter(eq('status', 'deprecated'))}")
    print(f"Services:     {store.get_metadata_field_unique_values('service')}")
    envs = store.get_metadata_field_unique_values("environment")
    print(f"Environments: {envs}")
    print("Active chunks per environment:")
    # get_metadata_field_unique_values may return (values, total) or just values.
    env_values = envs[0] if isinstance(envs, tuple) else envs
    for env in env_values:
        n = store.count_documents_by_filter(
            {"operator": "AND", "conditions": [eq("status", "active"), eq("environment", env)]}
        )
        print(f"  {env}: {n}")


def cmd_list(store, args) -> None:
    conditions = []
    if args.env:
        conditions.append(eq("environment", args.env))
    if args.service:
        conditions.append(eq("service", args.service))
    if not args.all:
        conditions.append(eq("status", "active"))
    filters = {"operator": "AND", "conditions": conditions} if conditions else None
    docs = store.filter_documents(filters=filters)
    # Chunks share meta; collapse to one line per runbook.
    seen: dict[str, dict] = {}
    chunks: dict[str, int] = {}
    for d in docs:
        rid = d.meta["runbook_id"]
        seen[rid] = d.meta
        chunks[rid] = chunks.get(rid, 0) + 1
    for rid in sorted(seen):
        m = seen[rid]
        print(f"{rid}  {m['environment']:<5} {m['service']:<14} {m['severity']:<9} "
              f"{m['status']:<10} {chunks[rid]} chunk(s)  {m['title']}")
    if not seen:
        print("No runbooks found.")


def set_status(store, runbook_id: str, status: str) -> None:
    # update_by_filter patches metadata in place, so no re-embedding is needed.
    n = store.update_by_filter(filters=eq("runbook_id", runbook_id), meta={"status": status})
    print(f"{runbook_id}: set status={status} on {n} chunk(s)")


def cmd_deprecate(store, args) -> None:
    set_status(store, args.runbook_id, "deprecated")


def cmd_restore(store, args) -> None:
    set_status(store, args.runbook_id, "active")


def cmd_purge(store, args) -> None:
    n = store.delete_by_filter(eq("status", "deprecated"))
    print(f"Deleted {n} deprecated chunk(s)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("stats").set_defaults(func=cmd_stats)

    p = sub.add_parser("list")
    p.add_argument("--env", choices=["dev", "uat", "prod"])
    p.add_argument("--service")
    p.add_argument("--all", action="store_true", help="include deprecated runbooks")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("deprecate")
    p.add_argument("runbook_id")
    p.set_defaults(func=cmd_deprecate)

    p = sub.add_parser("restore")
    p.add_argument("runbook_id")
    p.set_defaults(func=cmd_restore)

    sub.add_parser("purge").set_defaults(func=cmd_purge)

    args = parser.parse_args()
    args.func(get_document_store(), args)


if __name__ == "__main__":
    main()
