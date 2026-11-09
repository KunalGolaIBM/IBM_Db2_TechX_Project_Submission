/**
 * Interactive sensor chart — timestamps, units, metric filters.
 * Multi-series line chart over /readings data with:
 *  - toggleable metrics (checkbox chips with units)
 *  - timestamped tooltips including unit + data source
 *  - "no data" and error states handled by callers
 */
import React, { useMemo, useState } from 'react';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  Tooltip as RechartsTooltip, CartesianGrid, Legend,
} from 'recharts';

const fmtTime = (iso) => {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
};

const MetricChart = ({ readings = [], metrics = [], defaultSelected = [], height = 300 }) => {
  const selectable = metrics.length ? metrics : [];
  const [selected, setSelected] = useState(() =>
    defaultSelected.length ? defaultSelected : selectable.slice(0, 3).map((m) => m.key)
  );

  const toggle = (key) => {
    setSelected((prev) => {
      if (prev.includes(key)) return prev.filter((k) => k !== key);
      if (prev.length >= 5) return prev; // keep chart readable
      return [...prev, key];
    });
  };

  const chartData = useMemo(
    () => readings.map((r) => ({
      t: r.recorded_at,
      label: fmtTime(r.recorded_at),
      source: r.is_simulated ? 'simulated' : r.data_source,
      ...(r.values || {}),
    })),
    [readings]
  );

  if (selectable.length === 0) return null;

  const activeMetrics = selectable.filter((m) => selected.includes(m.key));

  return (
    <div className="w-full">
      {/* Metric toggle chips with units */}
      <div className="flex flex-wrap gap-2 mb-4" role="group" aria-label="Chart metric filters">
        {selectable.map((m) => {
          const on = selected.includes(m.key);
          return (
            <button
              key={m.key}
              type="button"
              onClick={() => toggle(m.key)}
              aria-pressed={on}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                on
                  ? 'bg-dark-700 text-gray-100 border-carbon-600/60'
                  : 'bg-dark-900/50 text-gray-500 border-carbon-800/40 hover:text-gray-300'
              }`}
            >
              <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: on ? m.color : '#374151' }} />
              {m.label}
              <span className="text-[10px] text-gray-500">({m.unit})</span>
            </button>
          );
        })}
      </div>

      {activeMetrics.length === 0 ? (
        <p className="text-sm text-gray-500 py-10 text-center">Select at least one metric to display.</p>
      ) : (
        <div style={{ height }} className="-ml-2">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 6, right: 12, left: 0, bottom: 4 }}>
              <CartesianGrid stroke="#12271b" strokeDasharray="3 3" />
              <XAxis
                dataKey="label"
                stroke="#374151"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                minTickGap={48}
              />
              <YAxis
                stroke="#374151"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                width={54}
                yAxisId={0}
                scale="auto"
              />
              <RechartsTooltip
                contentStyle={{ backgroundColor: '#071a10', borderColor: '#1d3025', borderRadius: '12px', color: '#fff', fontSize: 12 }}
                labelFormatter={(label) => `Time: ${label}`}
                formatter={(value, name, entry) => {
                  const metric = selectable.find((m) => m.key === name);
                  const src = entry.payload?.source;
                  return [`${value} ${metric?.unit || ''} · ${src === 'simulated' ? 'SIMULATED' : src}`, metric?.label || name];
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {activeMetrics.map((m) => (
                <Line
                  key={m.key}
                  type="monotone"
                  dataKey={m.key}
                  name={m.label}
                  stroke={m.color}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                  isAnimationActive={false}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      <p className="text-[11px] text-gray-500 mt-3 flex items-center gap-2 flex-wrap">
        <span>Timestamps: local time · tooltip shows unit + data source</span>
        {readings.length > 0 && (
          <span className="text-gray-600">({readings.length} readings from {fmtTime(readings[0].recorded_at)} to {fmtTime(readings[readings.length - 1].recorded_at)})</span>
        )}
      </p>
    </div>
  );
};

export default MetricChart;
