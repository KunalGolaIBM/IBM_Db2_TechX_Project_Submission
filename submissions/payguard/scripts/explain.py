"""Collect real Db2 EXPLAIN operators for the repository's hot SQL.

python scripts/explain.py --output docs/results/explain.json
Creates EXPLAIN tables if needed and refreshes statistics; changes no app rows.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from adapters.db2 import Db2Repository  # noqa: E402
from adapters.embeddings import get_embedder  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(".artifacts/explain.json"))
    args = parser.parse_args()
    repo = Db2Repository()
    try:
        schema = repo.query("SELECT CURRENT SCHEMA AS NAME FROM SYSIBM.SYSDUMMY1")[0]["name"].strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", schema):
            raise ValueError("Unexpected schema identifier")
        exists = repo.query("SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = ?",
                            (schema, "EXPLAIN_INSTANCE"))
        if not exists:
            repo.execute("CALL SYSPROC.SYSINSTALLOBJECTS(?, ?, CAST(NULL AS VARCHAR(128)), ?)",
                         ("EXPLAIN", "C", schema))
        for table in ("PG_ENTITIES", "PG_REPORTS", "PG_SCAM_PATTERNS", "PG_SCREENINGS", "SCAM_EXAMPLES"):
            repo.execute("CALL SYSPROC.ADMIN_CMD(?)", (f"RUNSTATS ON TABLE {schema}.{table} AND INDEXES ALL",))

        # Capture the actual parameterized statements from the production repository.
        statements = []
        query = repo.query

        def capture(sql, params=()):
            statements.append((sql, params))
            return [{"attempts": 0, "blocked": 0, "distance": 0}]

        repo.query = capture
        repo.lookup_entities([("account", "0000012345")])
        repo.payee_velocity("fastdeals.ng@mail.example")
        repo.search_patterns(get_embedder().embed(["Send your OTP"], task="query")[0], region="NG", k=3)
        repo.query = query
        plans = []
        for number, (name, statement) in enumerate(zip(("entity_lookup", "velocity", "vector_patterns"), statements), 1):
            sql, params = statement
            repo.execute(f"EXPLAIN PLAN SET QUERYNO = {number} FOR {sql}", params)
            operators = repo.query("""SELECT OPERATOR_ID, OPERATOR_TYPE, TOTAL_COST FROM EXPLAIN_OPERATOR
                WHERE EXPLAIN_TIME = (SELECT MAX(EXPLAIN_TIME) FROM EXPLAIN_OPERATOR) ORDER BY OPERATOR_ID""")
            objects = repo.query("""SELECT OBJECT_TYPE, OBJECT_SCHEMA, OBJECT_NAME FROM EXPLAIN_OBJECT
                WHERE EXPLAIN_TIME = (SELECT MAX(EXPLAIN_TIME) FROM EXPLAIN_OBJECT)""")
            plans.append({"query": name, "sql": sql, "operators": operators, "objects": objects})
        output = {"server": repo.query("SELECT SERVICE_LEVEL FROM TABLE(SYSPROC.ENV_GET_INST_INFO()) AS I")[0],
                  "vector_index_capability": repo.get_meta("capability:vector_indexes"),
                  "plans": plans, "indexes": repo.query("""SELECT INDNAME, TABNAME, INDEXTYPE FROM SYSCAT.INDEXES
                    WHERE TABSCHEMA = CURRENT SCHEMA AND (INDNAME LIKE 'PG_%' OR TABNAME = 'PG_ENTITIES')
                    ORDER BY TABNAME, INDNAME""")}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(output, indent=2))
    finally:
        repo.close()


if __name__ == "__main__":
    main()
