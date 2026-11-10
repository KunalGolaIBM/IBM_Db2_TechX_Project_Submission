import React, { useState } from 'react';
import { 
  LogIn, 
  FileKey, 
  ShieldAlert, 
  Users, 
  Search, 
  Filter, 
  CheckCircle, 
  XCircle,
  Laptop,
  Globe,
  Lock
} from 'lucide-react';

export default function MonitoringPage({ logins = [], accessLogs = [], alerts = [], users = [], onInvestigateUser }) {
  const [activeTab, setActiveTab] = useState('logins');
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  // Filter logins
  const filteredLogins = logins.filter(l => {
    const matchesSearch = 
      (l.user_id?.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (l.full_name?.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (l.ip_address?.includes(searchTerm)) ||
      (l.device_name?.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesStatus = statusFilter === 'ALL' || l.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // Filter access logs
  const filteredAccess = accessLogs.filter(a => {
    const matchesSearch = 
      (a.user_id?.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (a.resource_name?.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (a.resource_id?.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesClass = statusFilter === 'ALL' || a.classification_level === statusFilter;
    return matchesSearch && matchesClass;
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-xl font-bold font-tech text-white uppercase tracking-wide flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400"></span>
            <span>Live Telemetry & User Activity Monitoring</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time authentication records, resource access audits, and directory status from IBM Db2
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex bg-[#070d18] border border-[#1a2f55] p-1 rounded-lg text-xs font-medium">
          <button
            onClick={() => { setActiveTab('logins'); setStatusFilter('ALL'); }}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md transition-all ${
              activeTab === 'logins' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            <LogIn className="w-3.5 h-3.5" />
            <span>Login Events ({logins.length})</span>
          </button>
          <button
            onClick={() => { setActiveTab('access'); setStatusFilter('ALL'); }}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md transition-all ${
              activeTab === 'access' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            <FileKey className="w-3.5 h-3.5" />
            <span>Access Logs ({accessLogs.length})</span>
          </button>
          <button
            onClick={() => { setActiveTab('alerts'); setStatusFilter('ALL'); }}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md transition-all ${
              activeTab === 'alerts' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Alerts ({alerts.length})</span>
          </button>
          <button
            onClick={() => { setActiveTab('users'); setStatusFilter('ALL'); }}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md transition-all ${
              activeTab === 'users' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            <span>Personnel ({users.length})</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between bg-[#0b1528] p-3 rounded-lg border border-[#1a2f55]">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by user, IP, device, resource..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 bg-[#070d18] border border-[#1a2f55] rounded text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
          />
        </div>

        {/* Filter Dropdown */}
        {activeTab === 'logins' && (
          <div className="flex items-center space-x-2 text-xs">
            <span className="text-slate-400">Status:</span>
            {['ALL', 'SUCCESS', 'FAILURE'].map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-2.5 py-1 rounded text-xs font-mono-code transition-all ${
                  statusFilter === s ? 'bg-blue-600 text-white' : 'bg-[#070d18] text-slate-400 hover:text-white'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {activeTab === 'access' && (
          <div className="flex items-center space-x-2 text-xs">
            <span className="text-slate-400">Classification:</span>
            {['ALL', 'TOP_SECRET', 'SECRET', 'CONFIDENTIAL'].map((c) => (
              <button
                key={c}
                onClick={() => setStatusFilter(c)}
                className={`px-2 py-0.5 rounded text-[10px] font-mono-code transition-all ${
                  statusFilter === c ? 'bg-purple-600 text-white' : 'bg-[#070d18] text-slate-400 hover:text-white'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Content Tables */}
      <div className="cyber-card bg-[#0b1528] border border-[#1a2f55] overflow-hidden">
        {activeTab === 'logins' && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#070d18] border-b border-[#1a2f55] text-[10px] font-mono-code text-slate-400 uppercase">
                <tr>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Personnel / User ID</th>
                  <th className="py-2.5 px-3">IP Address</th>
                  <th className="py-2.5 px-3">Device & Type</th>
                  <th className="py-2.5 px-3">Location</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3 text-right">Investigation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#152642]">
                {filteredLogins.map((l) => (
                  <tr key={l.event_id} className="hover:bg-[#0f1f3d] transition-colors">
                    <td className="py-2.5 px-3">
                      {l.status === 'SUCCESS' ? (
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-800 text-[10px] font-mono-code font-bold">
                          <CheckCircle className="w-3 h-3 text-emerald-400" />
                          <span>SUCCESS</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded bg-rose-950/80 text-rose-300 border border-rose-800 text-[10px] font-mono-code font-bold">
                          <XCircle className="w-3 h-3 text-rose-400" />
                          <span>FAILURE</span>
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="font-semibold text-slate-200">{l.full_name || l.user_id}</div>
                      <div className="text-[10px] font-mono-code text-slate-400">{l.email || l.user_id}</div>
                    </td>
                    <td className="py-2.5 px-3 font-mono-code text-cyan-300">
                      {l.ip_address}
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="flex items-center space-x-1.5 text-slate-300">
                        <Laptop className="w-3.5 h-3.5 text-slate-500" />
                        <span>{l.device_name || 'Standard Terminal'}</span>
                      </div>
                      <div className="text-[10px] text-slate-500">{l.device_type}</div>
                    </td>
                    <td className="py-2.5 px-3 text-slate-400">
                      {l.location || 'Internal Garrison'}
                    </td>
                    <td className="py-2.5 px-3 font-mono-code text-slate-400 text-[11px]">
                      {l.timestamp ? l.timestamp.replace('T', ' ').slice(0, 19) : ''}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <button
                        onClick={() => onInvestigateUser(l.user_id)}
                        className="px-2 py-1 rounded bg-blue-600/20 hover:bg-blue-600/40 text-blue-300 border border-blue-500/30 text-[10px] font-mono-code transition-all"
                      >
                        Investigate
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'access' && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#070d18] border-b border-[#1a2f55] text-[10px] font-mono-code text-slate-400 uppercase">
                <tr>
                  <th className="py-2.5 px-3">Classification</th>
                  <th className="py-2.5 px-3">Resource Target</th>
                  <th className="py-2.5 px-3">Target Personnel</th>
                  <th className="py-2.5 px-3">Operation Type</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#152642]">
                {filteredAccess.map((a) => (
                  <tr key={a.log_id} className="hover:bg-[#0f1f3d] transition-colors">
                    <td className="py-2.5 px-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono-code font-bold border ${
                        a.classification_level === 'TOP_SECRET' 
                          ? 'bg-rose-950/80 text-rose-300 border-rose-700' 
                          : a.classification_level === 'SECRET'
                          ? 'bg-purple-950/80 text-purple-300 border-purple-700'
                          : 'bg-blue-950/80 text-blue-300 border-blue-700'
                      }`}>
                        {a.classification_level}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="font-semibold text-slate-100">{a.resource_name}</div>
                      <div className="text-[10px] font-mono-code text-cyan-400">{a.resource_id} ({a.resource_type})</div>
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="font-semibold text-slate-200">{a.full_name || a.user_id}</div>
                      <div className="text-[10px] text-slate-400">{a.security_clearance}</div>
                    </td>
                    <td className="py-2.5 px-3 font-mono-code text-slate-300">
                      {a.access_type}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono-code ${
                        a.status === 'ALLOWED' ? 'text-emerald-400 bg-emerald-950/40' : 'text-rose-400 bg-rose-950/40'
                      }`}>
                        {a.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-mono-code text-slate-400 text-[11px]">
                      {a.timestamp ? a.timestamp.replace('T', ' ').slice(0, 19) : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'alerts' && (
          <div className="p-4 space-y-3">
            {alerts.map((alt) => (
              <div key={alt.alert_id} className="p-3 rounded-lg bg-[#070d18] border border-[#152642] flex items-center justify-between">
                <div>
                  <div className="flex items-center space-x-2 mb-1">
                    <span className="font-mono-code text-xs font-bold text-cyan-400">{alt.alert_id}</span>
                    <span className="text-[10px] font-mono-code px-1.5 py-0.2 rounded bg-rose-950 text-rose-300 border border-rose-800">
                      {alt.severity}
                    </span>
                    <span className="text-slate-400 font-mono-code text-[11px]">| {alt.event_type}</span>
                  </div>
                  <p className="text-xs text-slate-200">{alt.description}</p>
                </div>
                <div className="text-right text-[11px] font-mono-code text-slate-400">
                  <p>{alt.full_name || alt.user_id}</p>
                  <p>{alt.timestamp ? alt.timestamp.slice(11, 19) : ''}</p>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'users' && (
          <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {users.map((u) => (
              <div key={u.user_id} className="p-4 rounded-lg bg-[#070d18] border border-[#152642] space-y-2">
                <div className="flex justify-between items-start">
                  <div>
                    <h4 className="font-semibold text-slate-100">{u.full_name}</h4>
                    <p className="text-xs text-slate-400 font-mono-code">{u.email}</p>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono-code font-bold ${
                    u.status === 'ACTIVE' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-rose-950 text-rose-400 border border-rose-800'
                  }`}>
                    {u.status}
                  </span>
                </div>
                <div className="text-xs text-slate-300">
                  <p><span className="text-slate-500">Department:</span> {u.department}</p>
                  <p><span className="text-slate-500">Role:</span> {u.role}</p>
                  <p><span className="text-slate-500">Clearance:</span> <span className="font-mono-code text-cyan-400 font-bold">{u.security_clearance}</span></p>
                </div>
                <button
                  onClick={() => onInvestigateUser(u.user_id)}
                  className="w-full mt-2 py-1.5 rounded bg-blue-600/30 hover:bg-blue-600/50 text-blue-300 border border-blue-500/40 text-xs font-semibold font-tech transition-all"
                >
                  Run Agentic AI Investigation →
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

