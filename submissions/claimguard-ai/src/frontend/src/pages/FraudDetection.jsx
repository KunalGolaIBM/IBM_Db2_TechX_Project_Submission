import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ShieldAlert,
  AlertTriangle,
  CheckCircle,
  Hash,
  FileText,
  Calendar,
  RefreshCw,
  Search,
  ExternalLink,
  Check
} from 'lucide-react';
import { apiClient } from '../api/client';

export default function FraudDetection() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterResolved, setFilterResolved] = useState('UNRESOLVED');
  const [search, setSearch] = useState('');
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [resolutionNotes, setResolutionNotes] = useState('');
  const [resolving, setResolving] = useState(false);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const param = filterResolved === 'ALL' ? undefined : filterResolved === 'RESOLVED';
      const res = await apiClient.getFraudAlerts(param);
      setAlerts(res.data);
    } catch (err) {
      console.error('Failed to fetch fraud alerts:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [filterResolved]);

  const handleResolveAlert = async (alertId) => {
    if (!resolutionNotes.trim()) {
      alert('Please enter investigation resolution notes.');
      return;
    }
    setResolving(true);
    try {
      await apiClient.resolveAlert(alertId, resolutionNotes);
      setSelectedAlert(null);
      setResolutionNotes('');
      await fetchAlerts();
    } catch (err) {
      alert(err.message || 'Failed to resolve alert.');
    } finally {
      setResolving(false);
    }
  };

  const filteredAlerts = alerts.filter((a) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      a.alert_type.toLowerCase().includes(q) ||
      a.claim_id.toLowerCase().includes(q) ||
      a.description.toLowerCase().includes(q)
    );
  });

  const criticalCount = alerts.filter((a) => a.severity === 'CRITICAL').length;
  const highCount = alerts.filter((a) => a.severity === 'HIGH').length;
  const mediumCount = alerts.filter((a) => a.severity === 'MEDIUM').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-[#E0E0E0]">
        <div>
          <div className="flex items-center space-x-2">
            <div className="p-1.5 bg-red-100 text-[#DA1E28] rounded">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-[#161616]">Enterprise Fraud Detection Center</h1>
              <p className="text-xs text-[#525252]">
                Automated detection of duplicate hashes, invoice collisions, and date anomalies via IBM Db2
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={fetchAlerts}
          className="flex items-center space-x-1.5 px-3 py-1.5 text-xs bg-white border border-[#E0E0E0] hover:bg-gray-50 text-[#161616] rounded-sm transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Alerts</span>
        </button>
      </div>

      {/* Summary KPI Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        <div className="bg-white border border-[#E0E0E0] p-4 rounded-sm shadow-sm">
          <p className="text-[11px] font-mono text-gray-500 uppercase">Total Logged Alerts</p>
          <h3 className="text-2xl font-bold text-gray-900 mt-1">{alerts.length}</h3>
          <p className="text-[11px] text-gray-400 mt-0.5">Persisted in Db2 FRAUD_ALERTS</p>
        </div>
        <div className="bg-white border border-red-200 bg-red-50/30 p-4 rounded-sm shadow-sm">
          <p className="text-[11px] font-mono text-red-700 uppercase font-semibold">Critical Severity</p>
          <h3 className="text-2xl font-bold text-red-700 mt-1">{criticalCount}</h3>
          <p className="text-[11px] text-red-600 mt-0.5">Hash / Invoice collisions</p>
        </div>
        <div className="bg-white border border-amber-200 bg-amber-50/30 p-4 rounded-sm shadow-sm">
          <p className="text-[11px] font-mono text-amber-800 uppercase font-semibold">High Severity</p>
          <h3 className="text-2xl font-bold text-amber-800 mt-1">{highCount}</h3>
          <p className="text-[11px] text-amber-700 mt-0.5">Date & policy inconsistencies</p>
        </div>
        <div className="bg-white border border-gray-200 p-4 rounded-sm shadow-sm">
          <p className="text-[11px] font-mono text-gray-600 uppercase font-semibold">Medium / Low</p>
          <h3 className="text-2xl font-bold text-gray-800 mt-1">{mediumCount}</h3>
          <p className="text-[11px] text-gray-500 mt-0.5">Abnormal diagnosis amounts</p>
        </div>
      </div>

      {/* Controls Bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-white border border-[#E0E0E0] p-3 rounded-sm shadow-sm">
        <div className="flex items-center space-x-1">
          {['UNRESOLVED', 'RESOLVED', 'ALL'].map((f) => (
            <button
              key={f}
              onClick={() => setFilterResolved(f)}
              className={`px-3 py-1 text-xs font-semibold rounded-sm transition-colors uppercase font-mono ${
                filterResolved === f
                  ? 'bg-[#DA1E28] text-white'
                  : 'bg-gray-100 text-[#525252] hover:bg-gray-200'
              }`}
            >
              {f}
            </button>
          ))}
        </div>

        <div className="relative w-full md:w-72">
          <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search alert type, claim ID, text..."
            className="w-full pl-9 pr-3 py-1.5 bg-[#F4F4F4] border border-[#E0E0E0] text-xs text-[#161616] rounded-sm focus:outline-none focus:border-[#DA1E28] focus:bg-white"
          />
        </div>
      </div>

      {/* Alerts Table */}
      <div className="bg-white border border-[#E0E0E0] rounded-sm shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F4F4F4] text-[#525252] border-b border-[#E0E0E0] uppercase font-mono text-[10px]">
              <tr>
                <th className="py-3 px-3">Severity</th>
                <th className="py-3 px-3">Alert Classification</th>
                <th className="py-3 px-3">Associated Claim</th>
                <th className="py-3 px-3">Indicator Description</th>
                <th className="py-3 px-3">Status</th>
                <th className="py-3 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredAlerts.length === 0 ? (
                <tr>
                  <td colSpan="6" className="py-10 text-center text-gray-400 text-xs">
                    <CheckCircle className="w-8 h-8 text-emerald-500 mx-auto mb-2 opacity-60" />
                    <span>No fraud alerts matching this filter.</span>
                  </td>
                </tr>
              ) : (
                filteredAlerts.map((alt) => (
                  <tr key={alt.alert_id} className="hover:bg-gray-50 transition-colors">
                    <td className="py-3 px-3">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                          alt.severity === 'CRITICAL'
                            ? 'bg-red-100 text-red-900 border border-red-300'
                            : alt.severity === 'HIGH'
                            ? 'bg-orange-100 text-orange-900 border border-orange-300'
                            : 'bg-amber-100 text-amber-900 border border-amber-300'
                        }`}
                      >
                        {alt.severity}
                      </span>
                    </td>
                    <td className="py-3 px-3 font-semibold text-gray-900 font-mono">
                      {alt.alert_type}
                    </td>
                    <td className="py-3 px-3 font-mono">
                      <Link to={`/claims/${alt.claim_id}`} className="text-[#0F62FE] hover:underline">
                        {alt.claim_id}
                      </Link>
                    </td>
                    <td className="py-3 px-3 text-gray-700 max-w-md">
                      <p className="line-clamp-2">{alt.description}</p>
                      {alt.evidence_details && (
                        <span className="text-[10px] text-gray-500 font-mono block mt-0.5">
                          Evidence: {alt.evidence_details}
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      {alt.is_resolved ? (
                        <span className="inline-flex items-center space-x-1 text-emerald-700 text-[11px] font-semibold">
                          <Check className="w-3 h-3" />
                          <span>Resolved</span>
                        </span>
                      ) : (
                        <span className="text-red-700 text-[11px] font-semibold">
                          Unresolved
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-right">
                      {!alt.is_resolved ? (
                        <button
                          onClick={() => setSelectedAlert(alt)}
                          className="px-2.5 py-1 bg-red-600 hover:bg-red-700 text-white text-[11px] font-medium rounded transition-colors"
                        >
                          Resolve
                        </button>
                      ) : (
                        <span className="text-gray-400 text-[11px]">By {alt.resolved_by || 'Examiner'}</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Resolve Alert Modal */}
      {selectedAlert && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white border border-[#E0E0E0] shadow-xl rounded-sm max-w-md w-full p-6 text-left">
            <h3 className="font-bold text-base text-[#161616]">
              Resolve Fraud Alert: <span className="text-[#DA1E28]">{selectedAlert.alert_type}</span>
            </h3>
            <p className="text-xs text-gray-500 mt-1">
              Record investigation resolution notes in IBM Db2 FRAUD_ALERTS table.
            </p>

            <div className="mt-3 p-2.5 bg-gray-50 border border-gray-100 rounded text-xs space-y-1">
              <p className="font-semibold text-gray-800">Alert Details:</p>
              <p className="text-gray-600">{selectedAlert.description}</p>
            </div>

            <div className="mt-4">
              <label className="block text-xs font-semibold text-[#161616] uppercase font-mono">
                Investigation Resolution Narrative
              </label>
              <textarea
                rows="3"
                value={resolutionNotes}
                onChange={(e) => setResolutionNotes(e.target.value)}
                placeholder="Details of investigation and verification with hospital or claimant..."
                className="mt-1 w-full p-2 bg-[#F4F4F4] border border-[#E0E0E0] text-xs text-[#161616] rounded-sm focus:outline-none focus:border-[#DA1E28]"
              ></textarea>
            </div>

            <div className="mt-5 flex justify-end space-x-2">
              <button
                onClick={() => setSelectedAlert(null)}
                className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100 rounded-sm"
              >
                Cancel
              </button>
              <button
                onClick={() => handleResolveAlert(selectedAlert.alert_id)}
                disabled={resolving}
                className="px-4 py-1.5 bg-[#DA1E28] text-white text-xs font-medium hover:bg-[#B81922] rounded-sm shadow-sm"
              >
                {resolving ? 'Persisting...' : 'Confirm Resolution'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
