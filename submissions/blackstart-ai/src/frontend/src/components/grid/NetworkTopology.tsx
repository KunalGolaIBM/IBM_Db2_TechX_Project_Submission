import { useMemo, useState } from 'react';
import type { PowerPlant, Substation, TransmissionLine } from '../../types/api';
import {
  formatNumber,
  utilizationBand,
  utilizationOf,
} from '../../lib/format';
import { EmptyState } from '../ui/states';
import { Network } from 'lucide-react';

interface Point {
  x: number;
  y: number;
}

const VIEW_W = 760;
const VIEW_H = 440;
const CENTER_X = VIEW_W / 2;
const CENTER_Y = 205;

function layoutSubstations(count: number): Point[] {
  const rx = 240;
  const ry = 138;
  return Array.from({ length: count }, (_, index) => {
    const angle = (-90 + (360 / count) * index) * (Math.PI / 180);
    return {
      x: CENTER_X + Math.cos(angle) * rx,
      y: CENTER_Y + Math.sin(angle) * ry,
    };
  });
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}…`;
}

function curvePath(from: Point, to: Point): { d: string; mid: Point } {
  const midX = (from.x + to.x) / 2;
  const midY = (from.y + to.y) / 2;
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.hypot(dx, dy) || 1;
  const offset = Math.min(46, length * 0.16);
  const controlX = midX + (-dy / length) * offset;
  const controlY = midY + (dx / length) * offset;
  return {
    d: `M ${from.x} ${from.y} Q ${controlX} ${controlY} ${to.x} ${to.y}`,
    mid: {
      x: 0.25 * from.x + 0.5 * controlX + 0.25 * to.x,
      y: 0.25 * from.y + 0.5 * controlY + 0.25 * to.y,
    },
  };
}

export function NetworkTopology({
  substations,
  lines,
  plants,
  selectedLineId,
  onSelectLine,
}: {
  substations: Substation[];
  lines: TransmissionLine[];
  plants: PowerPlant[];
  selectedLineId: number | null;
  onSelectLine: (lineId: number | null) => void;
}) {
  const [hoveredLineId, setHoveredLineId] = useState<number | null>(null);

  const positions = useMemo(() => {
    const points = layoutSubstations(Math.max(substations.length, 1));
    const map = new Map<number, Point>();
    substations.forEach((substation, index) => {
      map.set(substation.substation_id, points[index] ?? points[0]);
    });
    return map;
  }, [substations]);

  const plantPositions = useMemo(() => {
    const map = new Map<number, Point>();
    plants.forEach((plant, index) => {
      const host = substations.find(
        (substation) => substation.region === plant.region,
      );
      const base = host ? positions.get(host.substation_id) : undefined;
      if (base) {
        const dx = base.x - CENTER_X;
        const dy = base.y - CENTER_Y;
        const length = Math.hypot(dx, dy) || 1;
        map.set(plant.plant_id, {
          x: Math.min(VIEW_W - 74, Math.max(74, base.x + (dx / length) * 88)),
          y: Math.min(VIEW_H - 34, Math.max(30, base.y + (dy / length) * 74)),
        });
      } else {
        const angle = ((index / Math.max(plants.length, 1)) * 360 + 20) * (Math.PI / 180);
        map.set(plant.plant_id, {
          x: CENTER_X + Math.cos(angle) * 320,
          y: CENTER_Y + Math.sin(angle) * 190,
        });
      }
    });
    return map;
  }, [plants, positions, substations]);

  if (!substations.length && !lines.length) {
    return (
      <EmptyState
        icon={<Network className="h-5 w-5" />}
        title="No topology available"
        description="IBM Db2 returned no substations or transmission lines to map."
      />
    );
  }

  const activeLineId = hoveredLineId ?? selectedLineId;

  return (
    <div className="relative">
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
          className="h-auto w-full min-w-[640px]"
          role="img"
          aria-label="Network topology of substations and transmission lines"
        >
          <defs>
            <radialGradient id="topologyGlow" cx="50%" cy="40%" r="65%">
              <stop offset="0%" stopColor="#22D3EE" stopOpacity="0.07" />
              <stop offset="100%" stopColor="#22D3EE" stopOpacity="0" />
            </radialGradient>
            <filter id="nodeShadow" x="-30%" y="-30%" width="160%" height="160%">
              <feDropShadow dx="0" dy="6" stdDeviation="8" floodColor="#000000" floodOpacity="0.55" />
            </filter>
          </defs>

          <rect width={VIEW_W} height={VIEW_H} fill="url(#topologyGlow)" />
          <g opacity="0.35">
            {Array.from({ length: 12 }).map((_, index) => (
              <line
                key={`v-${index}`}
                x1={index * 64}
                y1={0}
                x2={index * 64}
                y2={VIEW_H}
                stroke="rgba(148,163,184,0.06)"
              />
            ))}
            {Array.from({ length: 8 }).map((_, index) => (
              <line
                key={`h-${index}`}
                x1={0}
                y1={index * 64}
                x2={VIEW_W}
                y2={index * 64}
                stroke="rgba(148,163,184,0.06)"
              />
            ))}
          </g>

          {plants.map((plant) => {
            const host = substations.find(
              (substation) => substation.region === plant.region,
            );
            const plantPoint = plantPositions.get(plant.plant_id);
            const hostPoint = host ? positions.get(host.substation_id) : undefined;
            if (!plantPoint || !hostPoint) return null;
            return (
              <g key={`plant-link-${plant.plant_id}`}>
                <line
                  x1={plantPoint.x}
                  y1={plantPoint.y}
                  x2={hostPoint.x}
                  y2={hostPoint.y}
                  stroke="rgba(148,163,184,0.35)"
                  strokeWidth="1.5"
                  strokeDasharray="5 5"
                />
              </g>
            );
          })}

          {lines.map((line) => {
            const from = positions.get(line.from_substation);
            const to = positions.get(line.to_substation);
            if (!from || !to) return null;
            const utilization = utilizationOf(line.current_load_mw, line.capacity_mw);
            const band = utilizationBand(utilization);
            const curve = curvePath(from, to);
            const active = activeLineId === line.line_id;
            return (
              <g
                key={line.line_id}
                tabIndex={0}
                role="button"
                aria-label={`${line.line_name}, ${formatNumber(utilization, 1)} percent utilization`}
                className="cursor-pointer outline-none"
                onMouseEnter={() => setHoveredLineId(line.line_id)}
                onMouseLeave={() => setHoveredLineId(null)}
                onFocus={() => setHoveredLineId(line.line_id)}
                onBlur={() => setHoveredLineId(null)}
                onClick={() =>
                  onSelectLine(selectedLineId === line.line_id ? null : line.line_id)
                }
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    onSelectLine(
                      selectedLineId === line.line_id ? null : line.line_id,
                    );
                  }
                }}
              >
                <path
                  d={curve.d}
                  fill="none"
                  stroke="transparent"
                  strokeWidth="22"
                />
                <path
                  d={curve.d}
                  fill="none"
                  stroke={band.color}
                  strokeWidth={active ? 7 : 5}
                  strokeLinecap="round"
                  opacity={active ? 1 : 0.8}
                  style={{ transition: 'stroke-width 160ms ease, opacity 160ms ease' }}
                />
                <path
                  d={curve.d}
                  fill="none"
                  stroke="#03050A"
                  strokeWidth="1.5"
                  strokeDasharray="1 9"
                  strokeLinecap="round"
                  opacity="0.7"
                />
                <g transform={`translate(${curve.mid.x - 27} ${curve.mid.y - 11})`}>
                  <rect
                    width="54"
                    height="22"
                    rx="7"
                    fill="#05070E"
                    stroke={band.color}
                    strokeWidth="1"
                    opacity={active ? 1 : 0.9}
                  />
                  <text
                    x="27"
                    y="15"
                    textAnchor="middle"
                    fontFamily="JetBrains Mono, monospace"
                    fontSize="11"
                    fontWeight="600"
                    fill={band.color}
                  >
                    {formatNumber(utilization, 0)}%
                  </text>
                </g>
              </g>
            );
          })}

          {substations.map((substation) => {
            const point = positions.get(substation.substation_id);
            if (!point) return null;
            const online = substation.status.toUpperCase() === 'ONLINE';
            const stroke = online ? 'rgba(52,211,153,0.55)' : 'rgba(248,113,113,0.6)';
            return (
              <g key={substation.substation_id} filter="url(#nodeShadow)">
                <rect
                  x={point.x - 84}
                  y={point.y - 42}
                  width="168"
                  height="84"
                  rx="14"
                  fill="#0A0F1B"
                  stroke={stroke}
                  strokeWidth="1.5"
                />
                <rect
                  x={point.x - 84}
                  y={point.y - 42}
                  width="168"
                  height="4"
                  rx="2"
                  fill={online ? '#34D399' : '#F87171'}
                  opacity="0.85"
                />
                <circle
                  cx={point.x - 68}
                  cy={point.y - 22}
                  r="4"
                  fill={online ? '#34D399' : '#F87171'}
                />
                <text
                  x={point.x - 58}
                  y={point.y - 18}
                  fontFamily="Space Grotesk, sans-serif"
                  fontSize="12.5"
                  fontWeight="600"
                  fill="#E2E8F0"
                >
                  {truncate(substation.substation_name.replace(' Grid Substation', ''), 20)}
                </text>
                <text
                  x={point.x}
                  y={point.y + 6}
                  textAnchor="middle"
                  fontFamily="JetBrains Mono, monospace"
                  fontSize="11"
                  fill="#7DD3FC"
                >
                  {formatNumber(Number(substation.voltage_kv), 0)} kV
                </text>
                <text
                  x={point.x}
                  y={point.y + 24}
                  textAnchor="middle"
                  fontFamily="JetBrains Mono, monospace"
                  fontSize="10.5"
                  fill="#64748B"
                >
                  {formatNumber(Number(substation.load_mw), 0)} MW load ·{' '}
                  {truncate(substation.region, 7)}
                </text>
              </g>
            );
          })}

          {plants.map((plant) => {
            const point = plantPositions.get(plant.plant_id);
            if (!point) return null;
            return (
              <g key={plant.plant_id}>
                <rect
                  x={point.x - 62}
                  y={point.y - 19}
                  width="124"
                  height="38"
                  rx="10"
                  fill="#0E1524"
                  stroke="rgba(34,211,238,0.35)"
                  strokeWidth="1.2"
                />
                <text
                  x={point.x}
                  y={point.y - 3}
                  textAnchor="middle"
                  fontFamily="Inter, sans-serif"
                  fontSize="10.5"
                  fontWeight="600"
                  fill="#A5F3FC"
                >
                  {truncate(plant.plant_name.replace(' Plant', ''), 17)}
                </text>
                <text
                  x={point.x}
                  y={point.y + 11}
                  textAnchor="middle"
                  fontFamily="JetBrains Mono, monospace"
                  fontSize="9.5"
                  fill="#64748B"
                >
                  {plant.plant_type} · {formatNumber(Number(plant.capacity_mw), 0)} MW
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-white/[0.06] pt-3 text-[10px] uppercase tracking-[0.12em] text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm bg-emerald-400" /> &lt;80% normal
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm bg-amber-400" /> 80–89% warning
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm bg-red-500" /> 90–99% critical
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm bg-rose-600" /> ≥100% overcapacity
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm border border-dashed border-slate-500" />{' '}
          plant ↔ substation by region
        </span>
        <span className="normal-case tracking-normal text-slate-600">
          click a line for detail
        </span>
      </div>
    </div>
  );
}
