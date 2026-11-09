import React, { useEffect, useState } from 'react';
import { History, Clock, CheckCircle, RefreshCw, Filter, Cpu } from 'lucide-react';
import { apiClient } from '../api/client';

export default function AuditLogs() {
  const [logs, setLogs] = useState([]);
  const [filteredLogs, setFilteredLogs] = useState([]);
  const [agentFilter, setAgentFilter] = useState('ALL');
  const [loading, setLoading] = useState(true);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const res = await apiClient.getAuditLogs(100);
      setLogs(res.data);
      setFilteredLogs(res.data);
    } catch (err) {
      console.error('Failed to load audit logs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  useEffect(() => {
    if (agentFilter === 'ALL') {
      setFilteredLogs(logs);
    } else {
      setFilteredLogs(logs.filter((l) => l.agent_name === agentFilter));
    }
  }, [agentFilter, logs]);

  const agents = [
    'ALL',
    'DOCUMENT_AGENT',
    'DATABASE_AGENT',
    'FRAUD_AGENT',
    'DECISION_AGENT',
    'SUPERVISOR_AGENT',
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-[#E0E0E0]">
        <div>
          <div className="flex items-center space-x-2">
            <div className="p-1.5 bg-[#EDF5FF] text-[#0F62FE] rounded">
              <History className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-[#161616]">Immutable Audit & Verification Logs</h1>
              <p className="text-xs text-[#525252]">
                Chronological execution records from IBM Db2 VERIFICATION_LOGS
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={fetchLogs}
          className="flex items-center space-x-1 px-3 py-1.5 text-xs bg-white border border-[#E0E0E0] hover:bg-gray-50 text-[#161616] rounded-sm transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter Chips */}
      <div className="bg-white border border-[#E0E0E0] p-3 rounded-sm shadow-sm flex items-center space-x-1 overflow-x-auto">
        <span className="text-[11px] font-mono uppercase text-gray-500 mr-2 shrink-0">Filter Agent:</span>
        {agents.map((ag) => (
          <button
            key={ag}
            onClick={() => setAgentFilter(ag)}
            className={`px-2.5 py-1 text-xs font-semibold rounded-sm uppercase font-mono transition-colors shrink-0 ${
              agentFilter === ag
                ? 'bg-[#0F62FE] text-white'
                : 'bg-gray-100 text-[#525252] hover:bg-gray-200'
            }`}
          >
            {ag.replace('_AGENT', '')}
          </button>
        ))}
      </div>

      {/* Logs Table */}
      <div className="bg-white border border-[#E0E0E0] rounded-sm shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-[#F4F4F4] text-[#525252] border-b border-[#E0E0E0] uppercase text-[10px]">
              <tr>
                <th className="py-3 px-3">Log ID</th>
                <th className="py-3 px-3">Agent</th>
                <th className="py-3 px-3">Claim ID</th>
                <th className="py-3 px-3">Action Executed</th>
                <th className="py-3 px-3">Status</th>
                <th className="py-3 px-3">Audit Details</th>
                <th className="py-3 px-3">Latency</th>
                <th className="py-3 px-3 text-right">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 text-[11px]">
              {filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan="8" className="py-8 text-center text-gray-400 font-sans">
                    No logs matching your selection.
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => (
                  <tr key={log.log_id} className="hover:bg-gray-50">
                    <td className="py-2.5 px-3 font-semibold text-gray-700">{log.log_id}</td>
                    <td className="py-2.5 px-3 font-bold text-[#0F62FE]">{log.agent_name}</td>
                    <td className="py-2.5 px-3 text-gray-800">{log.claim_id}</td>
                    <td className="py-2.5 px-3 font-sans text-gray-900">{log.action}</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          log.status === 'SUCCESS'
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {log.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-sans text-gray-600 max-w-sm truncate" title={log.details}>
                      {log.details || 'N/A'}
                    </td>
                    <td className="py-2.5 px-3 text-gray-500">{log.execution_time_ms}ms</td>
                    <td className="py-2.5 px-3 text-right text-gray-400">
                      {log.created_at?.slice(0, 19)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
