"""Geographic helpers. Cell ids are used for GROUP BY hotspot queries in Db2."""

from __future__ import annotations

import math

CELL_SIZE_DEG = 0.005  # ~550 m north-south; adequate for city-block hotspots
EARTH_RADIUS_M = 6_371_000.0


def geo_cell(lat: float, lon: float, size: float = CELL_SIZE_DEG) -> str:
    """Deterministic grid cell id, e.g. ``C5490_15536`` for (27.49, 77.68)."""
    return f"C{math.floor(lat / size)}_{math.floor(lon / size)}"


def cell_center(cell: str, size: float = CELL_SIZE_DEG) -> tuple[float, float]:
    lat_idx, lon_idx = (int(p) for p in cell[1:].split("_"))
    return ((lat_idx + 0.5) * size, (lon_idx + 0.5) * size)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def bounding_box(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    """(min_lat, max_lat, min_lon, max_lon) enclosing a circle; used to hit indexes."""
    dlat = math.degrees(radius_m / EARTH_RADIUS_M)
    dlon = math.degrees(radius_m / (EARTH_RADIUS_M * max(math.cos(math.radians(lat)), 1e-6)))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon
