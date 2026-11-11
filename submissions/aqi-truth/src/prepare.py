"""Normalise OpenAQ archive CSVs into Db2 load files.
Usage: python src/prepare.py RAW_DIR OUT_DIR
Writes stations.del and readings.del (comma-delimited, Db2 LOAD/IMPORT friendly)."""
import csv, glob, gzip, os, re, sys

def operator(name):
    m = re.search(r"-\s*(DPCC|CPCB|IMD|IITM|MHUA)\b", name)
    return m.group(1) if m else ("US-DoS" if "Embassy" in name or name.startswith("New Delhi-") else None)

def main(raw, out):
    os.makedirs(out, exist_ok=True)
    stations, n = {}, 0
    with open(os.path.join(out, "readings.del"), "w", newline="") as f:
        w = csv.writer(f)
        for path in sorted(glob.glob(os.path.join(raw, "loc*.csv")) + glob.glob(os.path.join(raw, "loc*.csv.gz"))):
            opener = gzip.open if path.endswith(".gz") else open
            for r in csv.reader(opener(path, "rt", encoding="utf-8")):
                if len(r) < 9 or r[0] == "location_id":
                    continue
                lid, _sensor, name, dt, lat, lon, param, unit, val = r[:9]
                name = re.sub(r"-\d+$", "", name).strip()
                stations.setdefault(int(lid), (name, operator(name), lat, lon))
                ts = dt[:19].replace("T", " ")          # IST wall clock, end of hour
                w.writerow([lid, param, ts, val, unit.replace("µ", "u").replace("³", "3")])
                n += 1
    with open(os.path.join(out, "stations.del"), "w", newline="") as f:
        w = csv.writer(f)
        for lid, (name, op, lat, lon) in sorted(stations.items()):
            w.writerow([lid, name, op or "", lat, lon])
    print(f"{len(stations)} stations, {n} readings")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
