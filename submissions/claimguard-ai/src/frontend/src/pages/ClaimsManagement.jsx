import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Files,
  Search,
  Filter,
  RefreshCw,
  FilePlus,
  Play,
  ArrowRight,
  ExternalLink
} from 'lucide-react';
import { apiClient } from '../api/client';
import RiskScoreBadge from '../components/RiskScoreBadge';

export default function ClaimsManagement() {
  const [claims, setClaims] = useState([]);
  const [filteredClaims, setFilteredClaims] = useState([]);
  const [activeFilter, setActiveFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [verifyingId, setVerifyingId] = useState(null);

  const fetchClaims = async () => {
    setLoading(true);
    try {
      const res = await apiClient.getClaims();
      setClaims(res.data);
      setFilteredClaims(res.data);
    } catch (err) {
      console.error('Failed to fetch claims:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClaims();
  }, []);

  useEffect(() => {
    let result = claims;
    if (activeFilter !== 'ALL') {
      result = result.filter((c) => c.status === activeFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (c) =>
          c.claim_number.toLowerCase().includes(q) ||
          c.claim_id.toLowerCase().includes(q) ||
          (c.hospital_name && c.hospital_name.toLowerCase().includes(q)) ||
          c.customer_id.toLowerCase().includes(q)
      );
    }
    setFilteredClaims(result);
  }, [activeFilter, searchQuery, claims]);

  const handleRunVerification = async (claimId, e) => {
    e.stopPropagation();
    setVerifyingId(claimId);
    try {
      await apiClient.triggerVerification(claimId);
      await fetchClaims();
    } catch (err) {
      console.error('Verification failed:', err);
    } finally {
      setVerifyingId(null);
    }
  };

  const statusFilters = ['ALL', 'PENDING', 'APPROVED', 'REJECTED', 'FLAGGED'];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-[#E0E0E0]">
        <div>
          <h1 className="text-xl font-bold text-[#161616]">Claims Management Repository</h1>
          <p className="text-xs text-[#525252]">
            Track, filter, and inspect claims synchronized with IBM Db2 CLAIM_RECORDS
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={fetchClaims}
            className="flex items-center space-x-1 px-3 py-1.5 text-xs bg-white border border-[#E0E0E0] hover:bg-gray-50 text-[#161616] rounded-sm transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <Link
            to="/submit-claim"
            className="flex items-center space-x-1 px-3 py-1.5 text-xs bg-[#0F62FE] hover:bg-[#0353E9] text-white font-medium rounded-sm shadow-sm transition-colors"
          >
            <FilePlus className="w-3.5 h-3.5" />
            <span>New Claim</span>
          </Link>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-white border border-[#E0E0E0] p-3 rounded-sm shadow-sm">
        <div className="flex items-center space-x-1 overflow-x-auto">
          {statusFilters.map((st) => (
            <button
              key={st}
              onClick={() => setActiveFilter(st)}
              className={`px-3 py-1 text-xs font-semibold rounded-sm transition-colors uppercase font-mono ${
                activeFilter === st
                  ? 'bg-[#0F62FE] text-white'
                  : 'bg-gray-100 text-[#525252] hover:bg-gray-200'
              }`}
            >
              {st}
            </button>
          ))}
        </div>

        <div className="relative w-full md:w-72">
          <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search claim #, customer, hospital..."
            className="w-full pl-9 pr-3 py-1.5 bg-[#F4F4F4] border border-[#E0E0E0] text-xs text-[#161616] rounded-sm focus:outline-none focus:border-[#0F62FE] focus:bg-white"
          />
        </div>
      </div>

      {/* Claims Table */}
      <div className="bg-white border border-[#E0E0E0] rounded-sm shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F4F4F4] text-[#525252] border-b border-[#E0E0E0] uppercase font-mono text-[10px]">
              <tr>
                <th className="py-3 px-3">Claim # / ID</th>
                <th className="py-3 px-3">Customer ID</th>
                <th className="py-3 px-3">Hospital Provider</th>
                <th className="py-3 px-3">Claim Amount</th>
                <th className="py-3 px-3">Risk Assessment</th>
                <th className="py-3 px-3">Status</th>
                <th className="py-3 px-3">Submitted At</th>
                <th className="py-3 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredClaims.length === 0 ? (
                <tr>
                  <td colSpan="8" className="py-8 text-center text-gray-400 text-xs">
                    No claims match your current filter criteria.
                  </td>
                </tr>
              ) : (
                filteredClaims.map((c) => (
                  <tr key={c.claim_id} className="hover:bg-gray-50 transition-colors">
                    <td className="py-3 px-3 font-mono font-medium">
                      <Link to={`/claims/${c.claim_id}`} className="text-[#0F62FE] hover:underline">
                        {c.claim_number}
                      </Link>
                      <span className="block text-[10px] text-gray-400 font-mono">{c.claim_id}</span>
                    </td>
                    <td className="py-3 px-3 font-mono text-gray-700">{c.customer_id}</td>
                    <td className="py-3 px-3 font-medium text-[#161616] max-w-[180px] truncate">
                      {c.hospital_name || 'N/A'}
                    </td>
                    <td className="py-3 px-3 font-mono font-semibold text-[#161616]">
                      ₹{parseFloat(c.claim_amount).toLocaleString('en-IN')}
                    </td>
                    <td className="py-3 px-3">
                      <RiskScoreBadge score={c.risk_score} level={c.risk_level} />
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                          c.status === 'APPROVED'
                            ? 'bg-emerald-100 text-emerald-800'
                            : c.status === 'REJECTED'
                            ? 'bg-red-100 text-red-800'
                            : c.status === 'FLAGGED'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-blue-100 text-blue-800'
                        }`}
                      >
                        {c.status}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-gray-500 font-mono text-[11px]">
                      {c.submitted_at?.slice(0, 10)}
                    </td>
                    <td className="py-3 px-3 text-right space-x-2">
                      <button
                        onClick={(e) => handleRunVerification(c.claim_id, e)}
                        disabled={verifyingId === c.claim_id}
                        className="px-2 py-1 bg-gray-100 hover:bg-[#0F62FE] hover:text-white text-[#161616] text-[11px] font-medium rounded transition-colors"
                        title="Run LangGraph Verification Agents"
                      >
                        {verifyingId === c.claim_id ? 'Running...' : 'Run Agents'}
                      </button>
                      <Link
                        to={`/claims/${c.claim_id}`}
                        className="px-2 py-1 text-[#0F62FE] hover:underline font-medium text-xs"
                      >
                        Inspect
                      </Link>
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
