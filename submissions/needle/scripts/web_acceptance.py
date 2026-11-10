"""Acceptance checks for the web UI's API (needle.api) against the live Db2. Prints evidence; never a password.

Run with the API up (PYTHONPATH=src python -m needle.api) and the tunnel open:
    PYTHONPATH=src python scripts/web_acceptance.py [--base http://127.0.0.1:8600] [--memo]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

from needle.sbom import password_for

PYYAML = ("heads up from #platform-sec: someone says the yaml loader we use in a few python services can run "
          "arbitrary code when it parses an untrusted config file. no CVE number in the thread. are we exposed?")
FLASHPIX = "heap overflow in the image library's FlashPix JPEG decoder can lead to code execution, no CVE yet"
EMBARGOED = "GHSA-5x8w-8jj5-q52h"


def post(base: str, path: str, body: dict, token: str | None = None) -> tuple[int, dict, str]:
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw), raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        return e.code, json.loads(raw or "{}"), raw


def login(base: str, user: str) -> str:
    code, body, raw = post(base, "/api/login", {"user": user, "password": password_for(user)})
    assert code == 200, f"login {user}: HTTP {code} {body}"
    assert password_for(user) not in raw
    print(f"login {user}: ok, {body['visible_docs']:,} advisories visible")
    return body["token"]


def triage(base: str, token: str, query: str) -> tuple[dict, str]:
    t0 = time.perf_counter()
    code, body, raw = post(base, "/api/triage", {"query": query, "k": 10}, token)
    assert code == 200 and not body.get("fatal"), f"triage: HTTP {code} {body.get('fatal')}"
    print(f"  triage {time.perf_counter() - t0:.1f} s; router: {body['router']['line']}")
    print("  rows per leg: " + ", ".join(f"{m} {len(body['rankings'][m])}" for m in ("keyword", "vector", "hybrid")))
    return body, raw


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8600")
    ap.add_argument("--memo", action="store_true", help="also generate a memo as NDL_JUNIOR (needs the LLM)")
    a = ap.parse_args()
    ok = True

    def check(cond: bool, label: str) -> None:
        nonlocal ok
        ok &= cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    print(f"== {time.strftime('%Y-%m-%d %H:%M:%S %Z')} against {a.base}")
    code, body, _ = post(a.base, "/api/login", {"user": "NDL_JUNIOR", "password": "definitely-wrong"})
    check(code == 401 and body["detail"]["kind"] == "login", f"wrong password -> HTTP {code} {body['detail']['kind']}")

    print("\n== 1. Pillow FlashPix prompt as NDL_SENIOR")
    s = login(a.base, "NDL_SENIOR")
    r, raw = triage(a.base, s, FLASHPIX)
    hyb = [x["id"] for x in r["rankings"]["hybrid"]]
    print("  hybrid top 10: " + ", ".join(hyb))
    check(EMBARGOED in raw, f"{EMBARGOED} returned to NDL_SENIOR (hybrid rank "
                            f"{hyb.index(EMBARGOED) + 1 if EMBARGOED in hyb else '-'})")
    check(bool(r["docs"].get(EMBARGOED, {}).get("embargoed")), f"{EMBARGOED} flagged embargoed in the senior view")
    aff = sorted({x["SERVICE"] for x in r["exposure"] if x["STATUS"] == "AFFECTED" and x["ADV_ID"] in hyb})
    print(f"  AFFECTED services (hybrid top 10): {aff}")

    print("\n== 2. Same prompt as NDL_JUNIOR")
    j = login(a.base, "NDL_JUNIOR")
    r, raw = triage(a.base, j, FLASHPIX)
    print("  hybrid top 10: " + ", ".join(x["id"] for x in r["rankings"]["hybrid"]))
    check(EMBARGOED not in raw and EMBARGOED.lower() not in raw.lower(),
          f"{EMBARGOED} absent from the whole junior response (rankings, docs, exposure, SQL params)")
    check(not any(d["embargoed"] for d in r["docs"].values()), "no embargoed advisory in the junior view")
    if a.memo:
        t0 = time.perf_counter()
        code, m, mraw = post(a.base, "/api/memo", {"mode": "hybrid"}, j)
        check(code == 200, f"junior memo HTTP {code} in {time.perf_counter() - t0:.1f} s ({m.get('model')})")
        if code == 200:
            check(EMBARGOED.lower() not in mraw.lower(), f"{EMBARGOED} absent from the junior memo (verified and raw)")
            print(f"  memo: kept {m['kept']} sentences, removed {len(m['removed'])}")

    print("\n== 3. PyYAML chat message as NDL_JUNIOR")
    r, raw = triage(a.base, j, PYYAML)
    hyb = [x["id"] for x in r["rankings"]["hybrid"]]
    rows = [x for x in r["exposure"] if x["STATUS"] == "AFFECTED" and x["ADV_ID"] in hyb]
    for x in rows:
        print(f"  AFFECTED {x['SERVICE']} {x['PACKAGE']}=={x['VERSION_NOW']} since {x['EXPOSED_SINCE']} "
              f"({x['DAYS_EXPOSED']:,} days) {x['ADV_ID']}")
    check(any(x["SERVICE"] == "legacy-reporting" for x in rows), "legacy-reporting is AFFECTED")
    check("safe" not in json.dumps(r["exposure"]).lower(), "no 'safe' status in the exposure rows")

    print("\n== 4. PyYAML chat message as NDL_P10 (10% visibility)")
    p = login(a.base, "NDL_P10")
    r, raw = triage(a.base, p, PYYAML)
    check(r["router"]["how"] == "exact scan", f"router chose: {r['router']['how']}")
    check(all(len(r["rankings"][m]) == 10 for m in ("keyword", "vector", "hybrid")), "10 of 10 rows in every leg")
    print(f"  exposure: {r['exposure_error']['kind'] if r['exposure_error'] else 'granted'}")

    print(f"\n== RESULT: {'ALL PASS' if ok else 'FAILURES ABOVE'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
