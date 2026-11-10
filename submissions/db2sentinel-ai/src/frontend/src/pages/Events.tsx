import React, { useEffect, useState } from 'react';
import { Database, Search, Filter, Eye, RefreshCw } from 'lucide-react';
import { SeverityBadge } from '../components/SeverityBadge';
import { SentinelApi } from '../services/api';
import { SecurityEvent } from '../types';

export const Events: React.FC = () => {
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchUser, setSearchUser] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [selectedEvent, setSelectedEvent] = useState<SecurityEvent | null>(null);

  const fetchEvents = async () => {
    setLoading(true);
    try {
      const res = await SentinelApi.getEvents({
        username: searchUser || undefined,
        event_type: typeFilter || undefined,
        limit: 100
      });
      setEvents(res.events || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, [typeFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchEvents();
  };

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white">Database Security Events</h2>
          <p className="text-xs text-slate-400 mt-1">
            Normalized telemetry from IBM Db2 Audit Facility and Activity Event Monitors
          </p>
        </div>
        <button
          onClick={fetchEvents}
          className="flex items-center gap-2 px-3 py-1.5 bg-[#132238] hover:bg-[#1C2E4A] text-slate-300 rounded-lg text-xs font-medium border border-[#1E3A5F] transition-all self-start"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh Feed
        </button>
      </div>

      {/* Filter Bar */}
      <div className="bg-[#132238] border border-[#1E3A5F] rounded-xl p-4 flex flex-col md:flex-row gap-4 justify-between items-center">
        <form onSubmit={handleSearchSubmit} className="relative w-full md:w-80">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search by username..."
            value={searchUser}
            onChange={(e) => setSearchUser(e.target.value)}
            className="w-full bg-[#0D182E] border border-[#1E3A5F] rounded-lg pl-9 pr-4 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
          />
        </form>

        <div className="flex items-center gap-3 w-full md:w-auto">
          <Filter className="w-4 h-4 text-slate-400 shrink-0" />
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="bg-[#0D182E] border border-[#1E3A5F] rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-cyan-500"
          >
            <option value="">All Event Types</option>
            <option value="AUTHENTICATION">AUTHENTICATION</option>
            <option value="QUERY_EXECUTION">QUERY_EXECUTION</option>
            <option value="SENSITIVE_ACCESS">SENSITIVE_ACCESS</option>
            <option value="PRIVILEGE_RECON">PRIVILEGE_RECON</option>
          </select>
        </div>
      </div>

      {/* Events Table */}
      <div className="bg-[#132238] border border-[#1E3A5F] rounded-2xl p-6 shadow-lg">
        {loading ? (
          <div className="py-12 text-center text-cyan-400 text-xs">Loading telemetry records...</div>
        ) : events.length === 0 ? (
          <div className="py-12 text-center text-slate-500 text-xs">No matching events recorded in database.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#0D182E] text-slate-400 uppercase font-semibold">
                <tr>
                  <th className="p-3 rounded-l-lg">ID</th>
                  <th className="p-3">Timestamp</th>
                  <th className="p-3">Type</th>
                  <th className="p-3">User</th>
                  <th className="p-3">Source IP</th>
                  <th className="p-3">Operation / Target</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Severity</th>
                  <th className="p-3 rounded-r-lg text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1E3A5F]/40 text-slate-200">
                {events.map((ev) => (
                  <tr key={ev.event_id} className="hover:bg-[#1C2E4A]/40 transition-colors">
                    <td className="p-3 font-mono text-cyan-400 font-semibold">#{ev.event_id}</td>
                    <td className="p-3 font-mono text-slate-400">{ev.event_timestamp}</td>
                    <td className="p-3 font-bold text-white">{ev.event_type}</td>
                    <td className="p-3 font-mono text-slate-300">{ev.username}</td>
                    <td className="p-3 font-mono text-slate-400">{ev.source_ip}</td>
                    <td className="p-3 font-mono text-slate-200">
                      {ev.sql_operation} {ev.object_name ? `• ${ev.object_name}` : ''}
                    </td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                        ev.status === 'SUCCESS' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
                      }`}>
                        {ev.status}
                      </span>
                    </td>
                    <td className="p-3"><SeverityBadge severity={ev.severity} /></td>
                    <td className="p-3 text-right">
                      <button
                        onClick={() => setSelectedEvent(ev)}
                        className="p-1.5 bg-[#0D182E] hover:bg-cyan-500 hover:text-black rounded text-slate-300 transition-all"
                        title="View Raw Evidence"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Raw Event Detail Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-[#132238] border border-[#1E3A5F] rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#1E3A5F] pb-3">
              <div>
                <h3 className="text-base font-bold text-white">Event #{selectedEvent.event_id} Details</h3>
                <span className="text-xs text-cyan-400 font-mono">Source: {selectedEvent.event_source}</span>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div><span className="text-slate-400">Username:</span> <span className="font-mono text-white">{selectedEvent.username}</span></div>
              <div><span className="text-slate-400">Source IP:</span> <span className="font-mono text-white">{selectedEvent.source_ip}</span></div>
              <div><span className="text-slate-400">Timestamp:</span> <span className="font-mono text-white">{selectedEvent.event_timestamp}</span></div>
              <div><span className="text-slate-400">Database:</span> <span className="font-mono text-white">{selectedEvent.database_name}</span></div>
            </div>

            <div>
              <span className="text-xs text-slate-400 block mb-1">Raw Telemetry Payload:</span>
              <pre className="bg-[#0D182E] border border-[#1E3A5F] rounded-xl p-4 text-xs font-mono text-cyan-300 overflow-x-auto max-h-60">
                {selectedEvent.raw_details || 'No additional payload stored.'}
              </pre>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setSelectedEvent(null)}
                className="px-4 py-1.5 bg-[#1C2E4A] hover:bg-slate-700 text-white rounded-lg text-xs font-medium"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
