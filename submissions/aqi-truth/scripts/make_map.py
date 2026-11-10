"""Build web/data/map.json: the Delhi NCT outline as an SVG path plus every station's position, in one projection.
Outline: Delhi_Boundary.geojson by DataMeet India (github.com/datameet/Municipal_Spatial_Data, CC BY 4.0).
Station positions: AQ.STATION.LAT / LON (from the OpenAQ archive).
Usage: python scripts/make_map.py"""
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from db import connect, rows
ROOT = os.path.join(os.path.dirname(__file__), "..")
W = 600
ring = json.load(open(os.path.join(ROOT, "data", "geo", "Delhi_Boundary.geojson")))["features"][0]["geometry"]["coordinates"][0]
lons = [p[0] for p in ring]; lats = [p[1] for p in ring]
k = math.cos(math.radians(sum(lats) / len(lats)))            # equirectangular, scaled for Delhi's latitude
x0, x1, y0, y1 = min(lons), max(lons), min(lats), max(lats)
s = W / ((x1 - x0) * k); H = round((y1 - y0) * s)
proj = lambda lon, lat: (round((lon - x0) * k * s, 1), round((y1 - lat) * s, 1))
pts = [proj(*p) for p in ring[::3]]
path = "M" + " L".join(f"{x},{y}" for x, y in pts) + " Z"
st = rows(connect(), "SELECT STATION_ID, LAT, LON FROM AQ.STATION WHERE STATION_ID <> 8118 AND LAT IS NOT NULL")
out = dict(w=W, h=H, outline=path, credit="Delhi boundary: DataMeet India, CC BY 4.0",
           stations={str(i): proj(float(lon), float(lat)) for i, lat, lon in st})
json.dump(out, open(os.path.join(ROOT, "web", "data", "map.json"), "w"))
print(f"{len(pts)} outline points, {len(st)} stations, {W}x{H}")
