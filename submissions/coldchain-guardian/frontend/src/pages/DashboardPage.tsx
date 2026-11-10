import { useEffect, useState } from 'react';
import { api, DashboardStats, Incident } from '../api';
import StatCard from '../components/StatCard';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import Badge from '../components/SeverityBadge';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend, LineChart, Line, XAxis, YAxis, CartesianGrid } from 'recharts';
import { Package2, Ship, AlertTriangle, Clock, ThermometerSun } from 'lucide-react';

const RISK_COLORS: Record<string, string> = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#eab308',
  LOW: '#22c55e',
};

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getDashboard();
      setStats(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <LoadingSpinner text="Loading dashboard..." />;
  if (error) return <div className="p-6"><ErrorMessage message={error} onRetry={load} /></div>;
  if (!stats) return null;

  const riskData = Object.entries(stats.risk_distribution || {}).map(([name, value]) => ({ name, value }));
  const recentIncidents = stats.recent_incidents || [];
  const recentShipments = stats.recent_shipments || [];
  const temperatureTrends = stats.temperature_trends || [];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-slate-400 text-sm mt-1">Real-time cold-chain monitoring overview</p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatCard label="Products" value={stats.products} icon={<Package2 className="w-5 h-5"/>} color="text-teal-400" />
        <StatCard label="Shipments" value={stats.shipments} icon={<Ship className="w-5 h-5"/>} color="text-cyan-400" />
        <StatCard label="In Transit" value={stats.shipments_in_transit} icon={<Ship className="w-5 h-5"/>} color="text-blue-400" />
        <StatCard label="Open Incidents" value={stats.open_incidents} icon={<AlertTriangle className="w-5 h-5"/>} color="text-orange-400" />
        <StatCard label="Pending Recs" value={stats.pending_recommendations} icon={<Clock className="w-5 h-5"/>} color="text-yellow-400" />
        <StatCard label="Violations" value={stats.temperature_violations} icon={<ThermometerSun className="w-5 h-5"/>} color="text-red-400" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Risk distribution chart */}
        <div className="bg-navy-800 border border-navy-600 rounded-xl p-6">
          <h2 className="text-white font-semibold mb-4">Risk Distribution</h2>
          {riskData.length === 0 ? (
            <div className="flex items-center justify-center h-48 text-slate-500 text-sm">No risk assessments yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={riskData}
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  dataKey="value"
                  label={({ name, percent }: { name: string; percent: number }) => `${name} ${(percent * 100).toFixed(0)}%`}
                >
                  {riskData.map((entry) => (
                    <Cell key={entry.name} fill={RISK_COLORS[entry.name] || '#6b7280'} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0d1526',
                    border: '1px solid #1a2235',
                    borderRadius: '8px',
                    color: '#e2e8f0',
                  }}
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Recent incidents */}
        <div className="bg-navy-800 border border-navy-600 rounded-xl p-6">
          <h2 className="text-white font-semibold mb-4">Recent Incidents</h2>
          {recentIncidents.length === 0 ? (
            <div className="flex items-center justify-center h-48 text-slate-500 text-sm">No incidents yet</div>
          ) : (
            <div className="space-y-3">
              {recentIncidents.map((inc: Incident) => (
                <div key={inc.incident_id} className="flex items-center justify-between py-2 border-b border-navy-600 last:border-0">
                  <div>
                    <p className="text-white text-sm font-medium">Incident #{inc.incident_id}</p>
                    <p className="text-slate-400 text-xs">Shipment {inc.shipment_id} · {inc.incident_type}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge label={inc.severity} />
                    <Badge label={inc.status} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Temperature trends */}
      <div className="bg-navy-800 border border-navy-600 rounded-xl p-6">
        <h2 className="text-white font-semibold mb-4">Temperature Trends</h2>
        {temperatureTrends.length === 0 ? (
          <div className="flex items-center justify-center h-48 text-slate-500 text-sm">No sensor readings yet</div>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={temperatureTrends} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a2235" />
              <XAxis
                dataKey="recorded_at"
                tickFormatter={(v: string) => (v ? new Date(v).toLocaleDateString() : '')}
                stroke="#64748b"
                fontSize={11}
              />
              <YAxis stroke="#64748b" fontSize={11} unit="°C" />
              <Tooltip
                contentStyle={{ backgroundColor: '#0d1526', border: '1px solid #1a2235', borderRadius: '8px', color: '#e2e8f0' }}
                labelFormatter={(v: string) => (v ? new Date(v).toLocaleString() : '')}
                formatter={(value, _name, item) => [
                  `${value}°C`,
                  (item?.payload as { product_name?: string } | undefined)?.product_name || 'Temperature',
                ]}
              />
              <Line type="monotone" dataKey="temperature" stroke="#2dd4bf" strokeWidth={2} dot={{ r: 2, fill: '#2dd4bf' }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Recent shipment activity */}
      <div className="bg-navy-800 border border-navy-600 rounded-xl p-6">
        <h2 className="text-white font-semibold mb-4">Recent Shipment Activity</h2>
        {recentShipments.length === 0 ? (
          <div className="flex items-center justify-center h-24 text-slate-500 text-sm">No shipments yet</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-navy-600">
                <tr>
                  {['Shipment', 'Product', 'Route', 'Vehicle', 'Status', 'Departure'].map(h => (
                    <th key={h} className="text-left text-xs text-slate-400 uppercase tracking-wide px-3 py-2">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recentShipments.map(s => (
                  <tr key={s.shipment_id} className="border-b border-navy-600/50 last:border-0">
                    <td className="px-3 py-2 text-white font-medium">#{s.shipment_id}</td>
                    <td className="px-3 py-2 text-slate-300">{s.product_name}</td>
                    <td className="px-3 py-2 text-slate-400 text-xs">{s.source_location} → {s.destination_location}</td>
                    <td className="px-3 py-2 text-slate-300">{s.vehicle_id}</td>
                    <td className="px-3 py-2"><Badge label={s.shipment_status} /></td>
                    <td className="px-3 py-2 text-slate-400 text-xs">{s.departure_time ? new Date(s.departure_time).toLocaleString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
