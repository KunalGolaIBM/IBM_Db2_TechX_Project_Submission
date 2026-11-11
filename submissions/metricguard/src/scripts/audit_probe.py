"""Bounded reproduction probe for the intermittent GET /api/audit 503.

Read-only: only GET requests against a running API. Small by design (default 60 sequential + 5 rounds x 8
concurrent requests); it is not a load test. Writes nothing to Db2.

    .venv/bin/python scripts/audit_probe.py --base http://localhost:8000 --out evaluation/live-checks/audit-probe.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def get(base: str, path: str) -> dict:
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(base + path, timeout=30) as r:
            status, body = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read()
    except Exception as e:  # network-level failure
        return {"path": path, "status": None, "error": type(e).__name__, "ms": round((time.perf_counter() - t0) * 1000, 1)}
    ms = round((time.perf_counter() - t0) * 1000, 1)
    out = {"path": path, "status": status, "ms": ms}
    if status >= 400:
        try:
            err = json.loads(body).get("error") or {}
            out["error"] = {"code": err.get("code"), "sqlstate": err.get("sqlstate")}
        except Exception:
            out["error"] = "unparseable body"
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--sequential", type=int, default=60)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--out")
    a = ap.parse_args()

    first = json.loads(urllib.request.urlopen(a.base + "/api/audit?limit=1", timeout=30).read())
    rid = first["items"][0]["request_id"]
    seq_paths = ["/api/audit?limit=20", "/api/audit?limit=20&status=BLOCKED", f"/api/audit/{rid}"]
    results = [get(a.base, seq_paths[i % 3]) for i in range(a.sequential)]
    # Mirrors the UI: the audit page, a status filter, a detail view and the 30 s health poll at once.
    mix = ["/api/audit?limit=20", "/api/audit?limit=20&offset=20", "/api/audit?limit=20&status=VERIFIED",
           f"/api/audit/{rid}", "/api/health", "/api/metrics", "/api/audit?limit=100", "/api/audit?limit=20&status=AMBIGUOUS"]
    conc = []
    with ThreadPoolExecutor(max_workers=a.concurrency) as pool:
        for _ in range(a.rounds):
            conc += list(pool.map(lambda p: get(a.base, p), mix[: a.concurrency]))
    allr = results + conc
    bad = [r for r in allr if r["status"] != 200]
    summary = {
        "requests": len(allr), "sequential": len(results), "concurrent": len(conc), "non_200": len(bad),
        "failures": bad,
        "ms_median": statistics.median(r["ms"] for r in allr), "ms_max": max(r["ms"] for r in allr),
        "audit_ms_max_concurrent": max(r["ms"] for r in conc if r["path"].startswith("/api/audit")),
    }
    print(json.dumps(summary, indent=1))
    if a.out:
        with open(a.out, "w") as f:
            json.dump({"summary": summary, "results": allr}, f, indent=1)


if __name__ == "__main__":
    main()
