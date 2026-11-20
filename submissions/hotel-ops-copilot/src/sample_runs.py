"""Export / load recorded agent runs, so the Audit tab is populated without an LLM key.

    python src/sample_runs.py export   # after real runs: AGENT_RUNS + AGENT_STEPS -> data/sample_runs.json
    python src/sample_runs.py load     # insert them into a fresh database (setup_db.py does this automatically)

Recorded runs are marked with MODEL '<model> (recorded)' so they are never mistaken for live ones.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hotelops.config import PROJECT_ROOT  # noqa: E402
from hotelops.db import get_db  # noqa: E402

SAMPLE_FILE = PROJECT_ROOT / "data" / "sample_runs.json"
MAX_TEXT = 30000  # keeps CLOB binds well inside driver limits


def export(path: Path = SAMPLE_FILE) -> int:
    db = get_db("admin")
    runs = db.query("SELECT RUN_ID, THREAD_ID, USER_QUESTION, ROUTE, FINAL_ANSWER, MODEL, STATUS, LLM_CALLS, "
                    "VARCHAR(STARTED_AT) AS STARTED_AT, VARCHAR(FINISHED_AT) AS FINISHED_AT "
                    "FROM AGENT_RUNS WHERE STATUS = 'DONE' ORDER BY STARTED_AT")
    for run in runs:
        run["steps"] = db.query(
            "SELECT AGENT, TOOL_NAME, TOOL_INPUT, TOOL_OUTPUT, OK, LATENCY_MS, VARCHAR(CREATED_AT) AS CREATED_AT "
            "FROM AGENT_STEPS WHERE RUN_ID = ? ORDER BY STEP_ID", (run["RUN_ID"],))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(runs, indent=1, default=str, ensure_ascii=False), encoding="utf-8")
    return len(runs)


def load(path: Path = SAMPLE_FILE) -> int:
    if not path.exists():
        return 0
    runs = json.loads(path.read_text(encoding="utf-8"))
    db = get_db("admin")
    for r in runs:
        if db.scalar("SELECT COUNT(*) FROM AGENT_RUNS WHERE RUN_ID = ?", (r["RUN_ID"],)):
            continue
        model = r["MODEL"] if (r["MODEL"] or "").endswith("(recorded)") else f"{r['MODEL']} (recorded)"
        db.execute("INSERT INTO AGENT_RUNS (RUN_ID, THREAD_ID, USER_QUESTION, ROUTE, FINAL_ANSWER, MODEL, STATUS, "
                   "LLM_CALLS, STARTED_AT, FINISHED_AT) "
                   "VALUES (?,?,?,?,?,?,?,?, CAST(? AS TIMESTAMP), CAST(? AS TIMESTAMP))",
                   (r["RUN_ID"], r["THREAD_ID"], r["USER_QUESTION"], r["ROUTE"], (r["FINAL_ANSWER"] or "")[:MAX_TEXT],
                    model[:60], r["STATUS"], r.get("LLM_CALLS"), r["STARTED_AT"], r["FINISHED_AT"]))
        for s in r["steps"]:
            db.execute("INSERT INTO AGENT_STEPS (RUN_ID, AGENT, TOOL_NAME, TOOL_INPUT, TOOL_OUTPUT, OK, LATENCY_MS, "
                       "CREATED_AT) VALUES (?,?,?,?,?,?,?, CAST(? AS TIMESTAMP))",
                       (r["RUN_ID"], s["AGENT"], s["TOOL_NAME"], (s["TOOL_INPUT"] or "")[:MAX_TEXT],
                        (s["TOOL_OUTPUT"] or "")[:MAX_TEXT], s["OK"], s["LATENCY_MS"], s["CREATED_AT"]))
    return len(runs)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["export", "load"])
    cmd = ap.parse_args().cmd
    n = export() if cmd == "export" else load()
    print(f"{n} run(s) {'written to' if cmd == 'export' else 'loaded from'} {SAMPLE_FILE}")
