"use client";

import { Bar, BarChart, CartesianGrid, LabelList, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ChartSeries, ChartSpec } from "@/lib/api/types";
import { formatAxis, formatCategory, formatValue } from "@/lib/formatters";

/** Fixed categorical order (validated palette). Color follows the series, never its rank. */
export const SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];

interface Row { x: string; [key: string]: string | number | null }

/** Merge series points by x, exactly as returned by the API. No values are invented. */
export function toRows(series: ChartSeries[]): Row[] {
  const order: string[] = [];
  const byX = new Map<string, Row>();
  for (const s of series) {
    for (const p of s.points) {
      const x = p.x ?? "";
      if (!byX.has(x)) { byX.set(x, { x }); order.push(x); }
      byX.get(x)![s.key] = p.y;
    }
  }
  return order.map((x) => byX.get(x)!);
}

function ChartTooltip({ active, payload, label, series }: { active?: boolean; payload?: { dataKey?: string | number; value?: number | string | null; color?: string }[]; label?: string; series: ChartSeries[] }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-line bg-white px-3 py-2 text-[13px] shadow-lg">
      <p className="mb-1 font-semibold text-ink">{formatCategory(label)}</p>
      <ul className="space-y-0.5">
        {payload.map((p) => {
          const s = series.find((x) => x.key === p.dataKey);
          return (
            <li key={String(p.dataKey)} className="flex items-center gap-2 text-ink-2">
              <span aria-hidden className="size-2.5 rounded-full" style={{ background: p.color }} />
              <span>{s?.label ?? String(p.dataKey)}</span>
              <span className="tabular ml-auto pl-4 font-semibold text-ink">{formatValue(typeof p.value === "number" ? p.value : null, s?.unit)}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function ResultChart({ chart }: { chart: ChartSpec }) {
  const series = chart.series.filter((s) => s.points.length > 0);
  if (chart.type === "kpi" || chart.type === "table" || series.length === 0) return null;
  const rows = toRows(series);
  if (rows.length === 0) return null;

  const unit = series[0]!.unit;
  const multi = series.length > 1;
  const colorOf = (i: number) => SERIES_COLORS[i % SERIES_COLORS.length]!;
  const axisTick = { fill: "#6b6a63", fontSize: 12 };
  const tooltip = <Tooltip cursor={{ stroke: "#cfcdc5" }} content={<ChartTooltip series={series} />} />;
  const legend = multi ? <Legend verticalAlign="top" align="left" height={32} iconType="circle" iconSize={9} formatter={(v) => <span style={{ color: "#4a4944", fontSize: 13 }}>{series.find((s) => s.key === v)?.label ?? v}</span>} /> : null;
  const alt = `${chart.title}. ${rows.length} ${rows.length === 1 ? "point" : "points"}, ${series.length} ${series.length === 1 ? "series" : "series"}. Values are listed in the data table.`;

  // Horizontal bars for single-dimension category comparisons (long labels stay readable).
  if (chart.type === "bar") {
    const s = series[0]!;
    const height = Math.max(180, rows.length * 44 + 40);
    return (
      <figure data-testid="chart" data-chart-type="bar" role="img" aria-label={alt}>
        <ResponsiveContainer width="100%" height={height} minWidth={0}>
          <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 72, bottom: 4, left: 8 }} barCategoryGap={10}>
            <CartesianGrid horizontal={false} stroke="#e8e6e0" />
            <XAxis type="number" tick={axisTick} tickFormatter={(v: number) => formatAxis(v, unit)} axisLine={false} tickLine={false} />
            <YAxis type="category" dataKey="x" tick={{ ...axisTick, fill: "#4a4944", fontSize: 13 }} tickFormatter={formatCategory} width={120} axisLine={false} tickLine={false} />
            {tooltip}
            <Bar dataKey={s.key} fill={colorOf(0)} maxBarSize={24} radius={[0, 4, 4, 0]} isAnimationActive={false}>
              <LabelList dataKey={s.key} position="right" formatter={(v: unknown) => formatValue(typeof v === "number" ? v : null, s.unit)} style={{ fill: "#14130f", fontSize: 12, fontWeight: 600 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </figure>
    );
  }

  if (chart.type === "grouped_bar") {
    return (
      <figure data-testid="chart" data-chart-type="grouped_bar" role="img" aria-label={alt}>
        <ResponsiveContainer width="100%" height={320} minWidth={0}>
          <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 4, left: 0 }} barGap={2}>
            <CartesianGrid vertical={false} stroke="#e8e6e0" />
            <XAxis dataKey="x" tick={axisTick} tickFormatter={formatCategory} axisLine={{ stroke: "#cfcdc5" }} tickLine={false} />
            <YAxis tick={axisTick} tickFormatter={(v: number) => formatAxis(v, unit)} width={56} axisLine={false} tickLine={false} />
            {tooltip}{legend}
            {series.map((s, i) => (
              <Bar key={s.key} dataKey={s.key} fill={colorOf(i)} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </figure>
    );
  }

  // line
  const lastIndex = rows.length - 1;
  return (
    <figure data-testid="chart" data-chart-type="line" role="img" aria-label={alt}>
      <ResponsiveContainer width="100%" height={320} minWidth={0}>
        <LineChart data={rows} margin={{ top: 8, right: 56, bottom: 4, left: 0 }}>
          <CartesianGrid vertical={false} stroke="#e8e6e0" />
          <XAxis dataKey="x" tick={axisTick} tickFormatter={formatCategory} axisLine={{ stroke: "#cfcdc5" }} tickLine={false} padding={{ left: 16, right: 16 }} />
          <YAxis tick={axisTick} tickFormatter={(v: number) => formatAxis(v, unit)} width={56} axisLine={false} tickLine={false} domain={[0, "auto"]} />
          {tooltip}{legend}
          {series.map((s, i) => (
            <Line
              key={s.key} dataKey={s.key} type="monotone" stroke={colorOf(i)} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
              dot={{ r: 4, fill: colorOf(i), stroke: "#ffffff", strokeWidth: 2 }} activeDot={{ r: 5, stroke: "#ffffff", strokeWidth: 2 }}
              isAnimationActive={false} connectNulls={false}
            >
              {!multi && (
                <LabelList
                  dataKey={s.key} position="top" offset={10}
                  content={({ x, y, value, index }) => index === lastIndex && typeof value === "number" && typeof x === "number" && typeof y === "number"
                    ? <text x={x} y={y - 10} textAnchor="middle" fontSize={12} fontWeight={600} fill="#14130f">{formatValue(value, s.unit)}</text>
                    : null}
                />
              )}
            </Line>
          ))}
        </LineChart>
      </ResponsiveContainer>
    </figure>
  );
}
