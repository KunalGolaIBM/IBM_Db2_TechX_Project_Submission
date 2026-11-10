import * as L from 'leaflet'
import { useEffect, useRef } from 'react'
import type { Complaint, Hotspot } from '../api/schemas'
import { severityColor } from '../lib/domain'
import { cellBounds, cellCenter, hotspotKey } from './geo'
import { complaintTooltip, hotspotLabel, hotspotTooltip } from './popup'

// OpenStreetMap standard tiles. Usage policy: https://operations.osmfoundation.org/policies/tiles/
// (light, human-driven use only; automated tests stub the tile requests).
const TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright" rel="noreferrer">OpenStreetMap</a> contributors'

const INK_DARK = '#0e0f12'
const INK_LIGHT = '#eceef2'
const COPPER_200 = '#f7cfb2'
const COPPER_300 = '#f2b184'
const COPPER_500 = '#cc7233'

export interface MapViewProps {
  complaints: Complaint[]
  hotspots: Hotspot[]
  selectedComplaintId: number | null
  selectedHotspotKey: string | null
  onSelectComplaint: (id: number) => void
  onSelectHotspot: (key: string) => void
  /** Increment to re-fit the viewport to the visible data. */
  fitSignal: number
  onTileStatus?: (status: 'ok' | 'unavailable') => void
}

const prefersReducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

export function MapView(props: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const complaintLayer = useRef<L.LayerGroup | null>(null)
  const hotspotLayer = useRef<L.LayerGroup | null>(null)
  const markers = useRef(new Map<number, L.CircleMarker>())
  const rects = useRef(new Map<string, L.Rectangle>())
  const callbacks = useRef(props)
  const fitted = useRef(false)
  useEffect(() => {
    callbacks.current = props
  })

  // ---- create the map once ---------------------------------------------------------------------------
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const map = L.map(el, { minZoom: 3, zoomSnap: 0.5 }).setView([27.4924, 77.6737], 12)
    const tiles = L.tileLayer(TILE_URL, { maxZoom: 19, attribution: ATTRIBUTION })
    let loaded = 0
    let failed = 0
    tiles.on('tileload', () => {
      loaded += 1
      if (loaded === 1) callbacks.current.onTileStatus?.('ok')
    })
    tiles.on('tileerror', () => {
      failed += 1
      if (loaded === 0 && failed >= 3) callbacks.current.onTileStatus?.('unavailable')
    })
    tiles.addTo(map)
    hotspotLayer.current = L.layerGroup().addTo(map)
    complaintLayer.current = L.layerGroup().addTo(map)
    mapRef.current = map
    const markerStore = markers.current
    const rectStore = rects.current
    return () => {
      map.remove()
      mapRef.current = null
      complaintLayer.current = null
      hotspotLayer.current = null
      markerStore.clear()
      rectStore.clear()
      fitted.current = false
    }
  }, [])

  // ---- hotspot cells ---------------------------------------------------------------------------------
  useEffect(() => {
    const layer = hotspotLayer.current
    const container = containerRef.current
    if (!layer || !container) return
    layer.clearLayers()
    rects.current.clear()
    let drawn = 0
    for (const h of props.hotspots) {
      const bounds = cellBounds(h.geo_cell)
      const center = cellCenter(h.geo_cell)
      if (!bounds || !center) continue
      const key = hotspotKey(h)
      const selected = key === props.selectedHotspotKey
      const rect = L.rectangle(bounds, {
        className: 'cl-hotspot',
        color: selected ? COPPER_200 : COPPER_300,
        weight: selected ? 3 : 2,
        fillColor: COPPER_500,
        fillOpacity: selected ? 0.26 : 0.13,
      })
      rect.bindTooltip(hotspotTooltip(h), { sticky: true, opacity: 1 })
      rect.on('click', () => callbacks.current.onSelectHotspot(key))
      rect.on('add', () => {
        const node = rect.getElement()
        node?.setAttribute('data-hotspot', key)
      })
      layer.addLayer(rect)
      rects.current.set(key, rect)

      const count = document.createElement('span')
      count.className = 'cl-hotspot-count'
      count.textContent = String(h.complaint_count)
      const badge = L.marker(center, {
        icon: L.divIcon({ className: 'cl-hotspot-label', html: count, iconSize: [0, 0] }),
        keyboard: true,
        title: hotspotLabel(h),
        alt: hotspotLabel(h),
      })
      badge.on('click', () => callbacks.current.onSelectHotspot(key))
      badge.on('add', () => {
        const node = badge.getElement()
        node?.setAttribute('role', 'button')
        node?.setAttribute('aria-label', hotspotLabel(h))
        node?.setAttribute('data-hotspot-label', key)
      })
      layer.addLayer(badge)
      drawn += 1
    }
    container.dataset.hotspotCount = String(drawn)
  }, [props.hotspots, props.selectedHotspotKey])

  // ---- complaint markers -----------------------------------------------------------------------------
  useEffect(() => {
    const layer = complaintLayer.current
    const container = containerRef.current
    if (!layer || !container) return
    layer.clearLayers()
    markers.current.clear()
    for (const c of props.complaints) {
      const selected = c.complaint_id === props.selectedComplaintId
      // size and brightness encode severity (ordinal ramp); a dashed light ring marks SYNTHETIC records
      const marker = L.circleMarker([c.latitude, c.longitude], {
        className: 'cl-marker',
        radius: 5 + c.severity + (selected ? 3 : 0),
        fillColor: severityColor(c.severity),
        fillOpacity: 0.95,
        color: selected ? COPPER_200 : c.is_synthetic ? INK_LIGHT : INK_DARK,
        weight: selected ? 3 : 2,
        dashArray: c.is_synthetic ? '2 3' : undefined,
      })
      marker.bindTooltip(complaintTooltip(c), { direction: 'top', offset: [0, -4], opacity: 1 })
      marker.on('click', () => callbacks.current.onSelectComplaint(c.complaint_id))
      marker.on('add', () => {
        const node = marker.getElement()
        node?.setAttribute('data-complaint-id', String(c.complaint_id))
        node?.setAttribute('data-category', c.category)
        node?.setAttribute('data-synthetic', String(c.is_synthetic))
      })
      layer.addLayer(marker)
      markers.current.set(c.complaint_id, marker)
    }
    container.dataset.markerCount = String(props.complaints.length)
    markers.current.get(props.selectedComplaintId ?? -1)?.bringToFront()
  }, [props.complaints, props.selectedComplaintId])

  // ---- viewport ----------------------------------------------------------------------------------------
  const hasData = props.complaints.length > 0 || props.hotspots.length > 0
  useEffect(() => {
    const map = mapRef.current
    if (!map || !hasData) return
    const explicit = props.fitSignal > 0
    // fit on first data, and again whenever the user asks (the filters changing must not yank the view)
    if (fitted.current && !explicit) return
    const cellCorners: L.LatLngExpression[] = []
    for (const h of props.hotspots) {
      const b = cellBounds(h.geo_cell)
      if (b) cellCorners.push(b[0], b[1])
    }
    // The first view focuses on the clusters Db2 found: one stray (or mistyped) coordinate must not zoom the map out
    // until every cell is sub-pixel. "Fit to data" is the explicit way to see everything.
    const points: L.LatLngExpression[] =
      !explicit && cellCorners.length > 0
        ? cellCorners
        : [...props.complaints.map((c): L.LatLngExpression => [c.latitude, c.longitude]), ...cellCorners]
    if (points.length === 0) return
    fitted.current = true
    map.fitBounds(L.latLngBounds(points), { padding: [48, 48], maxZoom: 15, animate: !prefersReducedMotion() })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.fitSignal, hasData])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const target =
      props.selectedComplaintId !== null
        ? markers.current.get(props.selectedComplaintId)?.getLatLng()
        : props.selectedHotspotKey
          ? (() => {
              const c = cellCenter(props.selectedHotspotKey.split('|')[0])
              return c ? L.latLng(c[0], c[1]) : undefined
            })()
          : undefined
    if (target) map.setView(target, Math.max(map.getZoom(), 14), { animate: !prefersReducedMotion() })
  }, [props.selectedComplaintId, props.selectedHotspotKey])

  return (
    <div
      ref={containerRef}
      data-testid="map"
      role="region"
      aria-label="Map of complaints and hotspots. The lists beside the map contain the same information."
      className="cl-map h-full min-h-[360px] w-full overflow-hidden rounded-xl border border-ink-700"
    />
  )
}
