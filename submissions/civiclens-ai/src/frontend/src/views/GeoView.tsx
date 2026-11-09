import { ChevronDown, Crosshair, Layers, MapPin, RotateCcw, SlidersHorizontal, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useComplaints, useHotspots, useOverview } from '../api/queries'
import type { Complaint, Hotspot } from '../api/schemas'
import { SeverityDots, SyntheticBadge } from '../components/Badges'
import { ComplaintDetail } from '../components/ComplaintDetail'
import { MapLegend } from '../components/MapLegend'
import { ErrorNotice, InfoNotice, SyntheticBanner } from '../components/Notices'
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  LoadingBlock,
  PageHeader,
  SelectInput,
  ToggleChip,
} from '../components/ui'
import { cn } from '../lib/cn'
import { CATEGORIES, CATEGORY_LABEL, type Category } from '../lib/domain'
import { formatRelative, formatInt, pluralise } from '../lib/format'
import { CELL_METERS, hotspotKey } from '../map/geo'
import { MapView } from '../map/MapView'

type Provenance = 'all' | 'synthetic' | 'real'
const WINDOWS = [7, 30, 90, 365]
const MIN_COUNTS = [2, 3, 5, 8]

const numberParam = (value: string | null): number | null => {
  const n = value === null ? NaN : Number(value)
  return Number.isInteger(n) && n > 0 ? n : null
}

export function GeoView() {
  const [params] = useSearchParams()
  const [selected, setSelected] = useState<Set<Category>>(new Set())
  const [provenance, setProvenance] = useState<Provenance>('all')
  const [days, setDays] = useState(30)
  const [minCount, setMinCount] = useState(3)
  const [complaintId, setComplaintId] = useState<number | null>(() => numberParam(params.get('complaint')))
  const [hotspotId, setHotspotId] = useState<string | null>(() => params.get('hotspot'))
  const [fitSignal, setFitSignal] = useState(0)
  const [tiles, setTiles] = useState<'pending' | 'ok' | 'unavailable'>('pending')
  const [panel, setPanel] = useState<'hotspots' | 'complaints'>(() => (params.get('complaint') ? 'complaints' : 'hotspots'))
  // On phones the filters would push the map below the fold, so they start collapsed (desktop always shows them).
  const [filtersOpen, setFiltersOpen] = useState(false)

  const complaintsQ = useComplaints({ limit: 200 })
  const hotspotsQ = useHotspots({ days, minCount, limit: 100 })
  const overviewQ = useOverview()

  const byProvenance = useMemo(
    () =>
      (complaintsQ.data ?? []).filter((c) =>
        provenance === 'all' ? true : provenance === 'synthetic' ? c.is_synthetic : !c.is_synthetic,
      ),
    [complaintsQ.data, provenance],
  )
  const visibleComplaints = useMemo(
    () => (selected.size === 0 ? byProvenance : byProvenance.filter((c) => selected.has(c.category))),
    [byProvenance, selected],
  )
  const visibleHotspots = useMemo(
    () => (hotspotsQ.data ?? []).filter((h) => selected.size === 0 || selected.has(h.category)),
    [hotspotsQ.data, selected],
  )
  const countByCategory = useMemo(() => {
    const counts = new Map<Category, number>()
    for (const c of byProvenance) counts.set(c.category, (counts.get(c.category) ?? 0) + 1)
    return counts
  }, [byProvenance])

  const activeFilters = selected.size + (provenance !== 'all' ? 1 : 0) + (days !== 30 ? 1 : 0) + (minCount !== 3 ? 1 : 0)
  const selectedComplaint: Complaint | undefined = complaintsQ.data?.find((c) => c.complaint_id === complaintId)
  const syntheticVisible = visibleComplaints.filter((c) => c.is_synthetic).length
  const total = overviewQ.data?.complaints.total

  const toggle = (category: Category) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(category)) next.delete(category)
      else next.add(category)
      return next
    })
  const resetFilters = () => {
    setSelected(new Set())
    setProvenance('all')
    setDays(30)
    setMinCount(3)
    setComplaintId(null)
    setHotspotId(null)
    setFitSignal((n) => n + 1)
  }
  const pickComplaint = (id: number) => {
    setComplaintId(id)
    setHotspotId(null)
    setPanel('complaints')
  }
  const pickHotspot = (key: string) => {
    setHotspotId(key)
    setComplaintId(null)
    setPanel('hotspots')
  }

  // wait for both data sets so the first map view can focus on the hotspots rather than on whatever arrived first
  if (complaintsQ.isPending || hotspotsQ.isPending) return <LoadingBlock label="Loading the map data" className="min-h-96" />
  if (!complaintsQ.data) return <ErrorNotice error={complaintsQ.error} onRetry={() => void complaintsQ.refetch()} />

  const allComplaints = complaintsQ.data
  return (
    <div className="flex flex-col gap-4" data-testid="geo-view">
      <PageHeader
        title="Geographic intelligence"
        description="Where complaints are, and where Db2 found clusters. Filters apply to the map and both lists at once."
        actions={
          <Button size="sm" onClick={() => setFitSignal((n) => n + 1)} icon={<Crosshair className="size-3.5" aria-hidden />}>
            Fit to data
          </Button>
        }
      />
      <SyntheticBanner synthetic={allComplaints.filter((c) => c.is_synthetic).length} total={allComplaints.length} />
      {hotspotsQ.isError && <ErrorNotice error={hotspotsQ.error} onRetry={() => void hotspotsQ.refetch()} />}
      {tiles === 'unavailable' && (
        <InfoNotice title="Basemap tiles are unavailable">
          OpenStreetMap tiles could not be loaded (offline or blocked). Complaints and hotspot cells are still plotted at their
          real coordinates.
        </InfoNotice>
      )}

      {/* one filter panel above everything it scopes */}
      <Card data-testid="map-filters">
        <CardBody className="flex flex-col gap-3 py-3.5">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <Button
              size="sm"
              className="md:hidden"
              aria-expanded={filtersOpen}
              aria-controls="map-filter-fields"
              onClick={() => setFiltersOpen((open) => !open)}
              icon={<SlidersHorizontal className="size-3.5" aria-hidden />}
              data-testid="filters-toggle"
            >
              Filters
              {activeFilters > 0 && (
                <span className="rounded-full bg-copper-500/25 px-1.5 text-xs text-fg tabular-nums" aria-label={`${activeFilters} active`}>
                  {activeFilters}
                </span>
              )}
              <ChevronDown className={cn('size-3.5 transition-transform', filtersOpen && 'rotate-180')} aria-hidden />
            </Button>
            <span className="hidden text-[13px] font-medium text-fg md:inline">Filters</span>
            <p className="text-[13px] text-fg-2" data-testid="map-count" aria-live="polite">
              Showing <strong className="font-semibold text-fg">{formatInt(visibleComplaints.length)}</strong>{' '}
              {pluralise(visibleComplaints.length, 'complaint')} and{' '}
              <strong className="font-semibold text-fg">{formatInt(visibleHotspots.length)}</strong>{' '}
              {pluralise(visibleHotspots.length, 'hotspot')}
              {total !== undefined && total > allComplaints.length && (
                <> (latest {formatInt(allComplaints.length)} of {formatInt(total)} complaints loaded)</>
              )}
            </p>
          </div>
          <div id="map-filter-fields" className={cn('flex-col gap-3 md:flex', filtersOpen ? 'flex' : 'hidden')}>
            <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by category">
              <span className="mr-1 text-[13px] font-medium text-fg-2">Category</span>
              <ToggleChip pressed={selected.size === 0} onToggle={() => setSelected(new Set())}>
                All
              </ToggleChip>
              {CATEGORIES.map((category) => (
                <ToggleChip
                  key={category}
                  pressed={selected.has(category)}
                  onToggle={() => toggle(category)}
                  count={countByCategory.get(category) ?? 0}
                >
                  {CATEGORY_LABEL[category]}
                </ToggleChip>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2.5">
              <SelectInput inline label="Records" value={provenance} onChange={(e) => setProvenance(e.target.value as Provenance)} className="w-52">
                <option value="all">All records</option>
                <option value="synthetic">Synthetic only</option>
                <option value="real">Real reports only</option>
              </SelectInput>
              <SelectInput inline label="Hotspot window" value={days} onChange={(e) => setDays(Number(e.target.value))} className="w-60">
                {WINDOWS.map((d) => (
                  <option key={d} value={d}>
                    Last {d} days
                  </option>
                ))}
              </SelectInput>
              <SelectInput inline label="Min. cluster" value={minCount} onChange={(e) => setMinCount(Number(e.target.value))} className="w-56">
                {MIN_COUNTS.map((n) => (
                  <option key={n} value={n}>
                    {n}+ complaints
                  </option>
                ))}
              </SelectInput>
              <Button variant="ghost" size="sm" onClick={resetFilters} icon={<RotateCcw className="size-3.5" aria-hidden />}>
                Reset
              </Button>
            </div>
          </div>
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_400px]">
        <div className="flex min-w-0 flex-col gap-4">
          <div className="h-[min(62dvh,600px)] min-h-[380px]">
            <MapView
              complaints={visibleComplaints}
              hotspots={visibleHotspots}
              selectedComplaintId={complaintId}
              selectedHotspotKey={hotspotId}
              onSelectComplaint={pickComplaint}
              onSelectHotspot={pickHotspot}
              fitSignal={fitSignal}
              onTileStatus={setTiles}
            />
          </div>
          <Card>
            <CardBody className="pt-4">
              <MapLegend
                synthetic={syntheticVisible}
                real={visibleComplaints.length - syntheticVisible}
                cellMeters={CELL_METERS}
              />
            </CardBody>
          </Card>
        </div>

        <Card className="flex min-h-0 flex-col" data-testid="map-panel">
          <CardHeader title="Browse the map" subtitle="Select an item to centre the map on it." />
          <div role="tablist" aria-label="List" className="mx-5 flex gap-1 rounded-lg bg-ink-900 p-1">
            {(
              [
                ['hotspots', `Hotspots (${visibleHotspots.length})`, <Layers key="h" className="size-3.5" aria-hidden />],
                ['complaints', `Complaints (${visibleComplaints.length})`, <MapPin key="c" className="size-3.5" aria-hidden />],
              ] as const
            ).map(([key, label, icon]) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={panel === key}
                onClick={() => setPanel(key)}
                className={cn(
                  'flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors',
                  panel === key ? 'bg-ink-750 text-fg' : 'text-fg-2 hover:text-fg',
                )}
              >
                {icon}
                {label}
              </button>
            ))}
          </div>

          <div className="mt-3 max-h-[540px] min-h-0 flex-1 overflow-y-auto px-3 pb-4">
            {selectedComplaint && panel === 'complaints' && (
              <div className="mb-3 rounded-xl border border-copper-500/50 bg-ink-850 p-4" data-testid="selected-complaint">
                <div className="mb-2 flex justify-end">
                  <Button size="sm" variant="ghost" onClick={() => setComplaintId(null)} icon={<X className="size-3.5" aria-hidden />}>
                    Clear
                  </Button>
                </div>
                <ComplaintDetail
                  complaint={selectedComplaint}
                  actions={
                    <Link
                      to={`/complaints?q=${selectedComplaint.complaint_id}`}
                      className="text-[13px] font-medium text-copper-400 hover:text-copper-300"
                    >
                      Open in complaint browser
                    </Link>
                  }
                />
              </div>
            )}
            {panel === 'hotspots' ? (
              <HotspotList hotspots={visibleHotspots} selectedKey={hotspotId} onPick={pickHotspot} windowDays={days} />
            ) : (
              <ComplaintList complaints={visibleComplaints} selectedId={complaintId} onPick={pickComplaint} />
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}

function HotspotList({
  hotspots,
  selectedKey,
  onPick,
  windowDays,
}: {
  hotspots: Hotspot[]
  selectedKey: string | null
  onPick: (key: string) => void
  windowDays: number
}) {
  if (hotspots.length === 0) {
    return (
      <EmptyState icon={<Layers />} title="No hotspots match">
        No cell has enough complaints in the last {windowDays} days for the selected categories. Try a longer window or a smaller
        minimum.
      </EmptyState>
    )
  }
  return (
    <ul className="flex flex-col gap-1.5" data-testid="hotspot-list">
      {hotspots.map((h) => {
        const key = hotspotKey(h)
        return (
          <li key={key}>
            <button
              type="button"
              aria-pressed={key === selectedKey}
              onClick={() => onPick(key)}
              data-testid="hotspot-item"
              className={cn(
                'flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors',
                key === selectedKey ? 'border-copper-400 bg-copper-500/14' : 'border-ink-700 bg-ink-850 hover:border-ink-600',
              )}
            >
              <span className="flex size-9 shrink-0 items-center justify-center rounded-full border-2 border-copper-300 bg-ink-900 text-sm font-semibold text-copper-200 tabular-nums">
                {h.complaint_count}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium text-fg">{CATEGORY_LABEL[h.category]}</span>
                <span className="block truncate font-mono text-xs text-fg-3">cell {h.geo_cell}</span>
              </span>
              <span className="flex shrink-0 flex-col items-end gap-1">
                <SeverityDots severity={Math.round(h.avg_severity)} />
                <span className="text-xs text-fg-3">{formatRelative(h.last_reported_at)}</span>
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}

function ComplaintList({
  complaints,
  selectedId,
  onPick,
}: {
  complaints: Complaint[]
  selectedId: number | null
  onPick: (id: number) => void
}) {
  if (complaints.length === 0) {
    return (
      <EmptyState icon={<MapPin />} title="No complaints match">
        Clear a filter to see more records.
      </EmptyState>
    )
  }
  return (
    <ul className="flex flex-col gap-1.5" data-testid="complaint-list">
      {complaints.map((c) => (
        <li key={c.complaint_id}>
          <button
            type="button"
            aria-pressed={c.complaint_id === selectedId}
            onClick={() => onPick(c.complaint_id)}
            data-testid="complaint-item"
            data-complaint-id={c.complaint_id}
            className={cn(
              'flex w-full flex-col gap-1 rounded-lg border px-3 py-2 text-left transition-colors',
              c.complaint_id === selectedId ? 'border-copper-400 bg-copper-500/14' : 'border-ink-700 bg-ink-850 hover:border-ink-600',
            )}
          >
            <span className="line-clamp-1 text-sm font-medium text-fg">{c.title}</span>
            <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-2">
              <span className="font-mono text-fg-3">#{c.complaint_id}</span>
              {CATEGORY_LABEL[c.category]}
              {c.ward && <span>· {c.ward}</span>}
              <SeverityDots severity={c.severity} />
              {c.is_synthetic && <SyntheticBadge />}
            </span>
          </button>
        </li>
      ))}
    </ul>
  )
}
