"""Export a read-only snapshot of the live Db2 audit to web/data/ for static hosting (GitHub Pages).
Every number in the snapshot comes from the Db2 run; nothing is recomputed here.
Usage: DB2_PASSWORD=... python scripts/export_snapshot.py [--llm-days N]"""
import argparse, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import app as A
from db import rows
import explain as ex

OUT = os.path.join(os.path.dirname(__file__), "..", "web", "data")
FEATURED = [(11603, "2025-10-23"), (5613, "2025-10-21"), (11603, "2025-10-27"), (235, "2025-11-01"), (11603, "2025-10-20")]

def dump(name, obj):
    path = os.path.join(OUT, name); os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w"), default=str, separators=(",", ":"))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--llm-days", type=int, default=len(FEATURED)); a = ap.parse_args()
    c = A.conn()
    dump("stats.json", A.stats()); dump("stations.json", A.stations()); dump("calendar.json", A.calendar())
    picks = list(FEATURED)
    picks += [(r[0], str(r[1])) for r in rows(c, "SELECT STATION_ID, DAY FROM AQ.V_DAY WHERE STATION_ID <> 8118 AND STATUS <> 'VALID'")]
    picks += [(r[0], "2025-10-21") for r in rows(c, "SELECT STATION_ID FROM AQ.STATION WHERE STATION_ID <> 8118")]
    last = rows(c, "SELECT MAX(DAY) FROM AQ.V_DAY")[0][0]      # the landing day of the latest period, for every station
    if str(last) > "2025-12-31":
        picks += [(r[0], str(last)) for r in rows(c, "SELECT STATION_ID FROM AQ.STATION WHERE STATION_ID <> 8118")]
    seen, n = set(), 0
    for i, (s, d) in enumerate(picks):
        if (s, d) in seen: continue
        seen.add((s, d))
        run = rows(c, "SELECT RUN_ID FROM AQ.V_DAY WHERE STATION_ID=? AND DAY=?", (s, d))
        if not run: continue
        has = rows(c, "SELECT COUNT(*) FROM AQ.EXPLANATION WHERE RUN_ID=?", (run[0][0],))[0][0]
        if not has:
            ex.explain(c, run[0][0], use_llm=i < a.llm_days)
        dump(f"day/{s}_{d}.json", A.day_payload(s, d, False)); n += 1
    print(f"snapshot: {n} station-days")

if __name__ == "__main__":
    main()
