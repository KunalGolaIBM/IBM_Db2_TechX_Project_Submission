import { SEVERITY_COLORS, SEVERITY_LABEL } from '../lib/domain'

/** Explains every visual channel on the map, including which records are synthetic. */
export function MapLegend({ synthetic, real, cellMeters }: { synthetic: number; real: number; cellMeters: number }) {
  return (
    <div className="grid grid-cols-1 gap-x-8 gap-y-3 text-[13px] text-fg-2 sm:grid-cols-2 xl:grid-cols-3" data-testid="map-legend">
      <div>
        <p className="mb-1.5 font-medium text-fg">Severity (size and brightness)</p>
        <ul className="flex items-end gap-3" aria-label="Severity scale">
          {SEVERITY_COLORS.map((color, i) => (
            <li key={color} className="flex flex-col items-center gap-1">
              <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden>
                <circle cx="13" cy="13" r={4 + i + 1} fill={color} stroke="#0e0f12" strokeWidth="2" />
              </svg>
              <span className="text-xs">{i + 1}</span>
              <span className="sr-only">{SEVERITY_LABEL[i + 1]}</span>
            </li>
          ))}
        </ul>
        <p className="mt-1 text-xs text-fg-3">1 minor to 5 critical</p>
      </div>
      <div>
        <p className="mb-1.5 font-medium text-fg">Record type (ring)</p>
        <ul className="flex flex-col gap-1.5">
          <li className="flex items-center gap-2" data-testid="legend-synthetic">
            <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden>
              <circle cx="11" cy="11" r="7" fill="#d67f46" stroke="#eceef2" strokeWidth="2" strokeDasharray="2 3" />
            </svg>
            Dashed ring: SYNTHETIC demonstration record
            <span className="text-fg-3 tabular-nums">({synthetic})</span>
          </li>
          <li className="flex items-center gap-2" data-testid="legend-real">
            <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden>
              <circle cx="11" cy="11" r="7" fill="#d67f46" stroke="#0e0f12" strokeWidth="2" />
            </svg>
            Solid dark ring: real report
            <span className="text-fg-3 tabular-nums">({real})</span>
          </li>
        </ul>
      </div>
      <div>
        <p className="mb-1.5 font-medium text-fg">Hotspot cell</p>
        <div className="flex items-center gap-2">
          <svg width="34" height="22" viewBox="0 0 34 22" aria-hidden>
            <rect x="2" y="2" width="30" height="18" rx="2" fill="#cc7233" fillOpacity="0.13" stroke="#f2b184" strokeWidth="2" />
            <text x="17" y="15.5" textAnchor="middle" fontSize="10" fontWeight="650" fill="#f7cfb2">7</text>
          </svg>
          <span>
            One grid cell (about {cellMeters} m across) that Db2 found with several complaints in the same category; the badge is the count.
          </span>
        </div>
      </div>
    </div>
  )
}
