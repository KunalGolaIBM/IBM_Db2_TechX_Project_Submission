import { useEffect, useState } from 'react';
import { api, Shipment, SensorReading } from '../api';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import Badge from '../components/SeverityBadge';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { ChevronDown, ChevronUp } from 'lucide-react';

export default function ShipmentsPage() {
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [readings, setReadings] = useState<Record<number, SensorReading[]>>({});
  const [readingsLoading, setReadingsLoading] = useState<number | null>(null);
  const [readingsError, setReadingsError] = useState<Record<number, string>>({});

  useEffect(() => {
    setLoading(true);
    api.getShipments()
      .then(setShipments)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false));
  }, []);

  const loadReadings = async (id: number) => {
    setReadingsLoading(id);
    setReadingsError(prev => ({ ...prev, [id]: '' }));
    try {
      const r = await api.getShipmentReadings(id);
      setReadings(prev => ({ ...prev, [id]: r }));
    } catch (e: unknown) {
      setReadingsError(prev => ({ ...prev, [id]: e instanceof Error ? e.message : 'Failed to load readings' }));
    } finally {
      setReadingsLoading(null);
    }
  };

  const toggleExpand = async (id: number) => {
    if (expanded === id) { setExpanded(null); return; }
    setExpanded(id);
    if (!readings[id]) await loadReadings(id);
  };

  if (loading) return <LoadingSpinner text="Loading shipments..." />;
  if (error) return <div className="p-6"><ErrorMessage message={error} /></div>;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Shipment Monitoring</h1>
        <p className="text-slate-400 text-sm mt-1">{shipments.length} shipments tracked</p>
      </div>

      <div className="space-y-3">
        {shipments.length === 0 ? (
          <div className="bg-navy-800 border border-navy-600 rounded-xl p-12 text-center text-slate-500">
            No shipments found
          </div>
        ) : shipments.map(s => {
          const isOpen = expanded === s.shipment_id;
          const rds = readings[s.shipment_id] || [];
          return (
            <div key={s.shipment_id} className="bg-navy-800 border border-navy-600 rounded-xl overflow-hidden">
              <button
                className="w-full flex items-center justify-between p-5 text-left hover:bg-navy-700/50 transition-colors"
                onClick={() => toggleExpand(s.shipment_id)}
              >
                <div className="flex items-center gap-4">
                  <div>
                    <p className="text-white font-semibold">Shipment #{s.shipment_id} — {s.product_name}</p>
                    <p className="text-slate-400 text-xs mt-0.5">
                      {s.source_location} → {s.destination_location} · Vehicle: {s.vehicle_id}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3 sm:gap-4">
                  <div className="text-right hidden sm:block">
                    <p className={`text-sm font-semibold ${s.temperature_violation ? 'text-red-400' : 'text-teal-400'}`}>
                      {s.latest_temperature != null ? `${s.latest_temperature}°C` : '—'}
                    </p>
                    <p className="text-slate-500 text-xs">
                      {s.min_temperature != null && s.max_temperature != null ? `range ${s.min_temperature}–${s.max_temperature}°C` : 'no range'}
                    </p>
                  </div>
                  {s.temperature_violation === true && <Badge label="VIOLATION" />}
                  {s.temperature_violation === false && <Badge label="NORMAL" />}
                  <Badge label={s.shipment_status} />
                  {isOpen
                    ? <ChevronUp className="w-4 h-4 text-slate-400" />
                    : <ChevronDown className="w-4 h-4 text-slate-400" />
                  }
                </div>
              </button>

              {isOpen && (
                <div className="border-t border-navy-600 p-5">
                  {readingsLoading === s.shipment_id ? (
                    <LoadingSpinner text="Loading sensor readings..." />
                  ) : readingsError[s.shipment_id] ? (
                    <div className="text-center py-4">
                      <p className="text-red-400 text-sm mb-2">{readingsError[s.shipment_id]}</p>
                      <button onClick={() => loadReadings(s.shipment_id)} className="text-teal-400 text-sm hover:underline">Retry</button>
                    </div>
                  ) : rds.length === 0 ? (
                    <p className="text-slate-500 text-sm text-center py-4">No sensor readings available</p>
                  ) : (
                    <div>
                      <p className="text-slate-400 text-xs mb-3 uppercase tracking-wide">{rds.length} sensor readings — Temperature (°C)</p>
                      <ResponsiveContainer width="100%" height={160}>
                        <LineChart data={rds}>
                          <XAxis dataKey="reading_id" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                          <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                          {s.min_temperature != null && (
                            <ReferenceLine y={s.min_temperature} stroke="#22c55e" strokeDasharray="4 4" />
                          )}
                          {s.max_temperature != null && (
                            <ReferenceLine y={s.max_temperature} stroke="#ef4444" strokeDasharray="4 4" />
                          )}
                          <Tooltip
                            contentStyle={{
                              backgroundColor: '#0d1526',
                              border: '1px solid #1a2235',
                              borderRadius: '8px',
                              color: '#e2e8f0',
                              fontSize: 12,
                            }}
                          />
                          <Line
                            type="monotone"
                            dataKey="temperature"
                            stroke="#14b8a6"
                            strokeWidth={2}
                            dot={false}
                            name="Temp (°C)"
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
