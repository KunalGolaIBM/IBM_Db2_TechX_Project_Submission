import type { Hotspot } from '../api/schemas'

/** Must match CELL_SIZE_DEG in the backend (civiclens/domain/geo.py). */
export const CELL_SIZE_DEG = 0.005
/** Approximate cell edge in metres (one degree of latitude is about 111.3 km). */
export const CELL_METERS = Math.round(CELL_SIZE_DEG * 111_320)

type LatLng = [number, number]

/** South-west and north-east corners of a geo-cell id such as "C5499_15535". */
export function cellBounds(cell: string): [LatLng, LatLng] | null {
  const m = /^C(-?\d+)_(-?\d+)$/.exec(cell)
  if (!m) return null
  const round = (v: number) => Math.round(v * 1e6) / 1e6
  const lat = Number(m[1])
  const lon = Number(m[2])
  return [
    [round(lat * CELL_SIZE_DEG), round(lon * CELL_SIZE_DEG)],
    [round((lat + 1) * CELL_SIZE_DEG), round((lon + 1) * CELL_SIZE_DEG)],
  ]
}

export const hotspotKey = (h: Pick<Hotspot, 'geo_cell' | 'category'>): string => `${h.geo_cell}|${h.category}`

export function cellCenter(cell: string): LatLng | null {
  const b = cellBounds(cell)
  const round = (v: number) => Math.round(v * 1e6) / 1e6
  return b ? [round((b[0][0] + b[1][0]) / 2), round((b[0][1] + b[1][1]) / 2)] : null
}
