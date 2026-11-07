#!/usr/bin/env python3
"""End-to-end smoke check of a running AsOf: real checks through the HTTP API, decisions in Db2.

    python scripts/smoke_check.py                  # http://127.0.0.1:8000
    python scripts/smoke_check.py http://host:port

1. /healthz: Db2 reachable as the runtime user, a model (or replay mode) configured.
2. The Moffatt question for a March booking, through the demo assistant and the check. With a live
   model it must not be released as written; in replay mode (what ./quickstart.sh picks without a key)
   the decision must equal the recorded one, and the ledger row must say "replay:".
3. Replay mode only: a draft that was never recorded must be held for a specialist (fail closed).
4. VERIFY_CHAIN over the whole ledger must report OK.

Prints each result and exits non-zero on the first mismatch. CI runs it after ./quickstart.sh.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
MOFFATT = "My grandmother just died. Can I get the bereavement fare after I travel?"
MARCH = "2026-03-10"


def fail(msg: str) -> int:
    print(f"FAIL: {msg}")
    return 1


def main(base: str) -> int:
    token = os.environ.get("ASOF_API_TOKEN", "")  # only needed when the API token is switched on
    client = httpx.Client(base_url=base, timeout=httpx.Timeout(360.0, connect=10.0),
                          headers={"Authorization": f"Bearer {token}"} if token else {})
    health = client.get("/healthz").json()
    print("healthz:", {k: health.get(k) for k in ("status", "db2", "llm", "llm_ready", "replay", "replay_model")})
    if health.get("db2") != "ok" or not health.get("llm_ready"):
        return fail("Db2 is not reachable as the runtime user, or no model is configured")
    replay = bool(health.get("replay"))

    body = client.post("/api/assistant/ask", json={"question": MOFFATT, "as_of_date": MARCH}).json()
    if "decision" not in body:
        return fail(f"the check did not run: {json.dumps(body)[:300]}")
    claims = [(c["verdict"], c.get("clause_id"), c.get("clause_version")) for c in body["claims"] if c["pass_no"] == 1]
    print(f"Moffatt, March booking: {body['decision']} ({body['reason_code']}), ledger #{body['ledger_id']}, "
          f"model {body['model']}, claims {claims}")
    if replay:
        recording = json.loads((ROOT / "src/asof/data/replay.json").read_text(encoding="utf-8"))
        expected = next(c for c in recording["scenarios"]["checks"]
                        if c["question"] == MOFFATT and c["as_of"] == MARCH and c["draft"] is None)
        if (body["decision"], body["reason_code"]) != (expected["decision"], expected["reason_code"]):
            return fail(f"replay gave {body['decision']}/{body['reason_code']}, the recording says "
                        f"{expected['decision']}/{expected['reason_code']}")
        if not body["model"].startswith("replay:"):
            return fail(f"a replayed decision must be labelled replay: in the ledger, got {body['model']}")
        held = client.post("/api/gate", json={"question": "Can I bring my bike?", "as_of_date": "2026-05-05",
                                              "draft_answer": "Yes, bikes fly free on every Aurelia Air flight."}).json()
        print(f"Unrecorded draft in replay mode: {held['decision']} ({held['reason_code']})")
        if (held["decision"], held["reason_code"]) != ("ESCALATED", "ERROR_FAIL_CLOSED"):
            return fail("an unrecorded draft must be held for a specialist in replay mode")
    elif body["decision"] == "PASS":
        return fail("the stale retroactive-refund promise was released as written")

    chain = client.get("/api/chain/verify").json()
    print(f"VERIFY_CHAIN: {chain['status']} over {chain['rows_checked']} rows")
    if chain["status"] != "OK":
        return fail(f"hash chain broken at #{chain['first_bad_ledger_id']}: {chain['detail']}")
    print("smoke check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"))
