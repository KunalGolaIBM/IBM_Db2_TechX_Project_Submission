/** Geospatial helpers for persisted parcel outlines. Coordinates use [latitude, longitude]. */
const EARTH_RADIUS_M = 6378137;

export function measureParcel(coordinates) {
  if (!Array.isArray(coordinates) || coordinates.length < 3 || coordinates.length > 500) {
    throw new Error('A parcel boundary must contain between 3 and 500 vertices.');
  }
  const points = coordinates.map((point) => {
    if (!Array.isArray(point) || point.length !== 2) throw new Error('Each vertex must be [latitude, longitude].');
    const [lat, lng] = point.map(Number);
    if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) {
      throw new Error('Boundary coordinates must be valid latitude/longitude values.');
    }
    return [lat, lng];
  });

  const unique = new Set(points.map(([lat, lng]) => `${lat.toFixed(8)},${lng.toFixed(8)}`));
  if (unique.size < 3) throw new Error('A parcel boundary needs at least 3 distinct vertices.');

  // A simple planar intersection check catches common invalid bow-tie polygons.
  const cross = (a, b, c) => (b[1] - a[1]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[1] - a[1]);
  const intersects = (a, b, c, d) => {
    const abC = cross(a, b, c), abD = cross(a, b, d);
    const cdA = cross(c, d, a), cdB = cross(c, d, b);
    return abC * abD < 0 && cdA * cdB < 0;
  };
  for (let i = 0; i < points.length; i += 1) {
    const a = points[i], b = points[(i + 1) % points.length];
    for (let j = i + 1; j < points.length; j += 1) {
      if (j === i || j === (i + 1) % points.length || (j + 1) % points.length === i) continue;
      if (intersects(a, b, points[j], points[(j + 1) % points.length])) {
        throw new Error('Boundary edges cross; redraw a non-self-intersecting polygon.');
      }
    }
  }

  let signedArea = 0;
  for (let i = 0; i < points.length; i += 1) {
    const [lat1, lng1] = points[i].map((value) => value * Math.PI / 180);
    const [lat2, lng2] = points[(i + 1) % points.length].map((value) => value * Math.PI / 180);
    signedArea += (lng2 - lng1) * (2 + Math.sin(lat1) + Math.sin(lat2));
  }
  const areaM2 = Math.abs(signedArea * EARTH_RADIUS_M * EARTH_RADIUS_M / 2);
  if (!Number.isFinite(areaM2) || areaM2 < 1) throw new Error('Boundary area is too small to be a valid parcel.');
  return {
    coordinates: points,
    area_m2: Number(areaM2.toFixed(2)),
    area_hectares: Number((areaM2 / 10000).toFixed(4)),
    area_acres: Number((areaM2 / 4046.8564224).toFixed(4)),
  };
}
