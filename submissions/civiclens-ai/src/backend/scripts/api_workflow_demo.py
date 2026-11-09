"""Drive the complete investigation workflow over real HTTP against a running API + Db2.

Requires the API to be running (uvicorn) and CIVICLENS_AUTH_TOKENS to contain an analyst and two
reviewers. Authorization headers are never printed. Output is a transcript suitable for
docs/evidence/.

Usage:  python scripts/api_workflow_demo.py [--base http://127.0.0.1:8000]
"""

import json
import os
import sys

import _bootstrap  # noqa: F401
import httpx
from civiclens.auth import parse_tokens

BASE = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else "http://127.0.0.1:8000"


def main() -> int:
    raw = os.environ.get("CIVICLENS_AUTH_TOKENS", "")
    by_role: dict[str, list[tuple[str, str]]] = {}
    for token, principal in parse_tokens(raw).items():
        by_role.setdefault(principal.role, []).append((principal.user_id, token))
    analyst, reviewers = by_role["analyst"][0], by_role["reviewer"]
    client = httpx.Client(base_url=BASE, timeout=60)

    def call(who: tuple[str, str] | None, method: str, path: str, **kw):
        headers = {"Authorization": f"Bearer {who[1]}"} if who else {}
        r = client.request(method, path, headers=headers, **kw)
        label = who[0] if who else "anonymous"
        body = r.text if len(r.text) < 700 else r.text[:700] + " ...[trimmed]"
        print(
            f"\n### {label}: {method} {path}" + (f"  body={json.dumps(kw['json'])}" if "json" in kw else "")
        )
        print(f"HTTP {r.status_code}\n{body}")
        return r

    call(None, "POST", "/api/investigations", json={"title": "x", "question": "y y y"})
    call(reviewers[0], "POST", "/api/investigations", json={"title": "x", "question": "y y y"})
    inv = call(
        analyst,
        "POST",
        "/api/investigations",
        json={"title": "Pothole hotspots (SYNTHETIC demo data)", "question": "Where should crews go first?"},
    ).json()
    inv_id = inv["investigation_id"]
    call(analyst, "POST", f"/api/investigations/{inv_id}/run", json={"mode": "llm"})
    run = call(
        analyst, "POST", f"/api/investigations/{inv_id}/run", json={"mode": "auto", "max_hotspots": 2}
    ).json()
    call(analyst, "POST", f"/api/investigations/{inv_id}/run", json={"mode": "auto"})
    call(reviewers[0], "GET", f"/api/investigations/{inv_id}/evidence")
    recs = call(reviewers[0], "GET", f"/api/investigations/{inv_id}/recommendations").json()
    first, second = recs[0]["recommendation_id"], recs[1]["recommendation_id"]
    call(analyst, "POST", f"/api/recommendations/{first}/decision", json={"decision": "APPROVED"})
    call(
        reviewers[0],
        "POST",
        f"/api/recommendations/{first}/decision",
        json={"decision": "APPROVED", "comment": "Crew assigned"},
    )
    call(
        reviewers[-1],
        "POST",
        f"/api/recommendations/{first}/decision",
        json={"decision": "REJECTED", "comment": "conflicting attempt"},
    )
    call(
        reviewers[-1],
        "POST",
        f"/api/recommendations/{second}/decision",
        json={"decision": "REJECTED", "comment": "Cluster already scheduled"},
    )
    call(analyst, "GET", f"/api/investigations/{inv_id}")
    audit = call(analyst, "GET", f"/api/investigations/{inv_id}/audit").json()
    print("\n### audit actions in order:", [f"{a['actor_id']}:{a['action']}" for a in audit])
    print(f"\nrun generator={run['generator']} llm_configured={run['llm_configured']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
