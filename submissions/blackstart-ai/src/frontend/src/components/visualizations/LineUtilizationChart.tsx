import {
  Bar,
  BarChart,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { TransmissionLine } from '../../types/api';
import { formatNumber, utilizationBand, utilizationOf } from '../../lib/format';
import { EmptyState } from '../ui/states';
import { Cable } from 'lucide-react';

interface ChartRow {
  id: number;
  name: string;
  utilization: number;
  load: number;
  capacity: number;
  bandLabel: string;
  color: string;
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: ChartRow }>;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-lg border border-white/10 bg-ink-900/95 px-3 py-2 shadow-panel backdrop-blur">
      <p className="text-xs font-semibold text-slate-200">{row.name}</p>
      <p className="mt-1 font-mono text-[11px] text-slate-400">
        {formatNumber(row.load)} / {formatNumber(row.capacity)} MW
      </p>
      <p
        className="mt-1 font-mono text-[11px] font-semibold"
        style={{ color: row.color }}
      >
        {formatNumber(row.utilization, 1)}% · {row.bandLabel}
      </p>
    </div>
  );
}

export function LineUtilizationChart({
  lines,
  height = 236,
}: {
  lines: TransmissionLine[];
  height?: number;
}) {
  if (!lines.length) {
    return (
      <EmptyState
        icon={<Cable className="h-5 w-5" />}
        title="No transmission lines"
        description="The TRANSMISSION_LINE table in IBM Db2 returned no rows for this view."
      />
    );
  }

  const rows: ChartRow[] = lines
    .map((line) => {
      const utilization = utilizationOf(line.current_load_mw, line.capacity_mw);
      const band = utilizationBand(utilization);
      return {
        id: line.line_id,
        name: line.line_name,
        utilization: Math.round(utilization * 10) / 10,
        load: Number(line.current_load_mw),
        capacity: Number(line.capacity_mw),
        bandLabel: band.label,
        color: band.color,
      };
    })
    .sort((a, b) => b.utilization - a.utilization);

  const maxUtil = Math.max(...rows.map((row) => row.utilization), 100);
  const domainMax = Math.ceil(Math.max(maxUtil + 8, 110) / 10) * 10;

  return (
    <div className="w-full">
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={rows}
          layout="vertical"
          margin={{ top: 4, right: 26, bottom: 4, left: 4 }}
          barCategoryGap="26%"
        >
          <XAxis
            type="number"
            domain={[0, domainMax]}
            tick={{ fill: '#64748B', fontSize: 10, fontFamily: 'JetBrains Mono' }}
            tickLine={false}
            axisLine={{ stroke: 'rgba(148,163,184,0.15)' }}
            unit="%"
          />
          <YAxis
            type="category"
            dataKey="name"
            width={116}
            tick={{ fill: '#94A3B8', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            cursor={{ fill: 'rgba(148,163,184,0.06)' }}
            content={<ChartTooltip />}
          />
          <ReferenceLine
            x={80}
            stroke="#F59E0B"
            strokeDasharray="4 4"
            strokeWidth={1}
          />
          <ReferenceLine
            x={90}
            stroke="#EF4444"
            strokeDasharray="4 4"
            strokeWidth={1}
          />
          <ReferenceLine
            x={100}
            stroke="#E11D48"
            strokeDasharray="2 3"
            strokeWidth={1}
          />
          <Bar
            dataKey="utilization"
            radius={[0, 5, 5, 0]}
            maxBarSize={22}
            isAnimationActive={false}
          >
            {rows.map((row) => (
              <Cell key={row.id} fill={row.color} fillOpacity={0.9} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

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
        <span className="normal-case tracking-normal text-slate-600">
          Demonstration thresholds only
        </span>
      </div>
    </div>
  );
}
