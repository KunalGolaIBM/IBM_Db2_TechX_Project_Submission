"""Remove rows created by automated tests so they do not pollute a demo database.

Default (dry run): count what would be removed. Add --yes to delete.

  * marker rows: investigations and complaints whose TITLE starts with "[E2E]" or "[CONTRACT]"
    (the Playwright and live-contract suites mark everything they create), plus their audit rows.
  * --workflow : ALSO delete every investigation, recommendation, review decision and audit row, i.e. reset
    the demo workflow state. Refuses to run if any complaint is not marked synthetic (possible real data).

Complaints and their synthetic seed data are never touched except marker rows.

Usage:  python scripts/cleanup_test_data.py [--workflow] [--yes]
"""

import sys

import _bootstrap  # noqa: F401
from civiclens.db.connection import session

MARKERS = ("[E2E]%", "[CONTRACT]%")


def count(db, sql: str, params=()) -> int:
    return int(db.fetch_one(sql, params)["n"])


def main() -> int:
    workflow = "--workflow" in sys.argv
    apply = "--yes" in sys.argv
    with session() as db:
        like = "TITLE LIKE ? OR TITLE LIKE ?"
        inv_marked = count(db, f"SELECT COUNT(*) AS N FROM {{schema}}.INVESTIGATIONS WHERE {like}", MARKERS)
        cmp_marked = count(db, f"SELECT COUNT(*) AS N FROM {{schema}}.COMPLAINTS WHERE {like}", MARKERS)
        inv_all = count(db, "SELECT COUNT(*) AS N FROM {schema}.INVESTIGATIONS")
        audit_all = count(db, "SELECT COUNT(*) AS N FROM {schema}.AUDIT_LOG")
        real = count(
            db,
            "SELECT COUNT(*) AS N FROM {schema}.COMPLAINTS WHERE IS_SYNTHETIC = 0 AND NOT (" + like + ")",
            MARKERS,
        )
        print(f"marker investigations: {inv_marked}, marker complaints: {cmp_marked}")
        print(f"all investigations: {inv_all}, audit rows: {audit_all}")
        print(f"complaints not marked synthetic (excluding markers): {real}")
        if workflow and real:
            print("REFUSING --workflow: some complaints are not synthetic, so this may be real data.")
            return 2
        if not apply:
            print("dry run: nothing deleted (add --yes to delete)")
            return 0
        with db.transaction():
            db.execute(
                "DELETE FROM {schema}.AUDIT_LOG WHERE INVESTIGATION_ID IN "
                f"(SELECT INVESTIGATION_ID FROM {{schema}}.INVESTIGATIONS WHERE {like})",
                MARKERS,
            )
            db.execute(f"DELETE FROM {{schema}}.INVESTIGATIONS WHERE {like}", MARKERS)
            db.execute(f"DELETE FROM {{schema}}.COMPLAINTS WHERE {like}", MARKERS)
            if workflow:
                db.execute(
                    "DELETE FROM {schema}.INVESTIGATIONS"
                )  # cascades evidence, recommendations, decisions
                db.execute("DELETE FROM {schema}.AUDIT_LOG")
        print(
            "deleted. now: investigations="
            f"{count(db, 'SELECT COUNT(*) AS N FROM {schema}.INVESTIGATIONS')}, "
            f"audit rows={count(db, 'SELECT COUNT(*) AS N FROM {schema}.AUDIT_LOG')}, "
            f"complaints={count(db, 'SELECT COUNT(*) AS N FROM {schema}.COMPLAINTS')}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
