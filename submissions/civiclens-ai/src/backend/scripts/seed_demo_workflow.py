"""Create a believable demo workflow THROUGH THE REAL API (nothing is inserted into Db2 directly).

It signs in with the analyst and two reviewer tokens from CIVICLENS_AUTH_TOKENS, then runs the actual
workflow on the SYNTHETIC complaint data: investigations in every lifecycle state, rule-based and manual
recommendations, and review decisions by two different reviewers. Every title is marked "(SYNTHETIC demo)".
No language model is used or implied: runs use the rule-based fallback and are labelled so by the API.

Usage (API must be running):  python scripts/seed_demo_workflow.py [--base http://127.0.0.1:8000] [--if-empty]
"""

import os
import sys

import _bootstrap  # noqa: F401
import httpx
from civiclens.auth import parse_tokens

BASE = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else "http://127.0.0.1:8000"


def main() -> int:
    people: dict[str, list[tuple[str, str]]] = {}
    for token, principal in parse_tokens(os.environ.get("CIVICLENS_AUTH_TOKENS", "")).items():
        people.setdefault(principal.role, []).append((principal.user_id, token))
    analyst, reviewers = people["analyst"][0], people["reviewer"]
    client = httpx.Client(base_url=BASE, timeout=120)

    def call(who: tuple[str, str], method: str, path: str, **kw):
        r = client.request(method, path, headers={"Authorization": f"Bearer {who[1]}"}, **kw)
        if r.status_code >= 400:
            raise SystemExit(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
        return r.json()

    if "--if-empty" in sys.argv and call(analyst, "GET", "/api/investigations", params={"limit": 1}):
        print("investigations already exist: skipping (--if-empty)")
        return 0

    complaints = call(analyst, "GET", "/api/complaints", params={"limit": 200, "synthetic": "true"})
    by_cat: dict[str, list[int]] = {}
    for c in complaints:
        by_cat.setdefault(c["category"], []).append(c["complaint_id"])

    def new(title: str, question: str) -> int:
        return call(analyst, "POST", "/api/investigations", json={"title": title, "question": question})[
            "investigation_id"
        ]

    def run(inv: int, **params) -> dict:
        return call(
            analyst, "POST", f"/api/investigations/{inv}/run", json={"mode": "fallback", "days": 90, **params}
        )

    # A: three recommendations; one approved, one rejected, one still pending (PENDING_REVIEW)
    a = new(
        "Citywide hotspot triage (SYNTHETIC demo)",
        "Which neighbourhoods should repair crews visit first this week?",
    )
    ra = run(a, max_hotspots=3)
    recs = sorted(ra["recommendation_ids"])
    call(
        reviewers[0],
        "POST",
        f"/api/recommendations/{recs[0]}/decision",
        json={"decision": "APPROVED", "comment": "Cluster is dense and recent. Dispatch crew 4."},
    )
    if len(recs) > 1:
        call(
            reviewers[-1],
            "POST",
            f"/api/recommendations/{recs[1]}/decision",
            json={"decision": "REJECTED", "comment": "Already scheduled under the ward 2 maintenance round."},
        )

    # B: one recommendation, approved, so the investigation closes
    b = new(
        "Water leak clusters (SYNTHETIC demo)", "Are there repeat water leaks that point to a failing main?"
    )
    rb = run(b, category="WATER_LEAK", max_hotspots=1)
    for rid in rb["recommendation_ids"]:
        call(
            reviewers[0],
            "POST",
            f"/api/recommendations/{rid}/decision",
            json={"decision": "APPROVED", "comment": "Evidence is consistent across several dates."},
        )

    # C: evidence attached by the analyst but not run yet (OPEN)
    c = new("Garbage collection gaps (SYNTHETIC demo)", "Where are collection rounds being missed?")
    call(
        analyst,
        "POST",
        f"/api/investigations/{c}/evidence",
        json={"complaint_ids": by_cat.get("GARBAGE", [])[:4], "note": "Selected by the analyst"},
    )

    # D: manual analysis, a recommendation written by a person (PENDING_REVIEW, generator MANUAL)
    d = new(
        "Streetlight outages: manual analysis (SYNTHETIC demo)",
        "Do the streetlight complaints near the school need an urgent fix?",
    )
    ids = by_cat.get("STREETLIGHT", [])[:3]
    call(analyst, "POST", f"/api/investigations/{d}/evidence", json={"complaint_ids": ids})
    call(analyst, "POST", f"/api/investigations/{d}/recommendations", json={
        "summary": "Prioritise streetlight repairs on the school approach road",
        "rationale": "Three streetlight complaints were filed on the route children use in the evening. "
                     "Written by an analyst from the attached complaints; no automated analysis was used.",
        "priority": 2, "confidence": 0.7, "evidence_ids": ids})  # fmt: skip

    for label, inv in (("A", a), ("B", b), ("C", c), ("D", d)):
        info = call(analyst, "GET", f"/api/investigations/{inv}")
        print(f"investigation {label}: #{inv} {info['status']:<15} {info['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
