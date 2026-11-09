import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  FileText,
  Clock,
  CheckCircle2,
  AlertTriangle,
  DollarSign,
  ShieldAlert,
  ArrowRight,
  TrendingUp,
  FilePlus,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import { apiClient } from '../api/client';
import StatCard from '../components/StatCard';
import RiskScoreBadge from '../components/RiskScoreBadge';

export default function Dashboard({ dbHealth }) {
  const [stats, setStats] = useState(null);
  const [recentClaims, setRecentClaims] = useState([]);
  const [recentAlerts, setRecentAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchDashboardData = async () => {
    try {
      setRefreshing(true);
      const [statsRes, claimsRes, alertsRes] = await Promise.all([
        apiClient.getDashboardStats(),
        apiClient.getClaims(),
        apiClient.getFraudAlerts(false),
      ]);
      setStats(statsRes.data);
      setRecentClaims(claimsRes.data.slice(0, 6));
      setRecentAlerts(alertsRes.data.slice(0, 4));
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const monthlyTrendsData = [
    { month: 'Jun', submitted: 4, verified: 3, fraudFlagged: 1 },
    { month: 'Jul', submitted: 7, verified: 6, fraudFlagged: 0 },
    { month: 'Aug', submitted: 9, verified: 7, fraudFlagged: 2 },
    { month: 'Sep', submitted: 12, verified: 10, fraudFlagged: 1 },
    { month: 'Oct', submitted: 15, verified: 12, fraudFlagged: 3 },
    { month: 'Nov', submitted: stats?.total_claims || 6, verified: stats?.approved_claims || 4, fraudFlagged: stats?.flagged_claims || 1 },
  ];

  const statusDistribution = [
    { name: 'Approved', value: stats?.approved_claims || 1, color: '#198038' },
    { name: 'Pending', value: stats?.pending_claims || 1, color: '#0F62FE' },
    { name: 'Flagged / Review', value: stats?.flagged_claims || 1, color: '#F1C21B' },
    { name: 'Rejected', value: stats?.rejected_claims || 0, color: '#DA1E28' },
  ];

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-2 border-b border-[#E0E0E0]">
        <div>
          <h1 className="text-xl font-bold text-[#161616] tracking-tight">Claims Adjudication Dashboard</h1>
          <p className="text-xs text-[#525252] mt-0.5">
            Agentic AI verification and enterprise fraud detection powered by IBM Db2
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={fetchDashboardData}
            disabled={refreshing}
            className="flex items-center space-x-1 px-3 py-1.5 text-xs bg-white border border-[#E0E0E0] hover:bg-gray-50 text-[#161616] font-medium transition-colors rounded-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <Link
            to="/submit-claim"
            className="flex items-center space-x-1 px-3 py-1.5 text-xs bg-[#0F62FE] hover:bg-[#0353E9] text-white font-medium transition-colors rounded-sm shadow-sm"
          >
            <FilePlus className="w-3.5 h-3.5" />
            <span>Submit Claim</span>
          </Link>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard
          title="Total Claims"
          value={stats?.total_claims ?? '...'}
          subtitle="All submissions"
          icon={FileText}
          color="blue"
        />
        <StatCard
          title="Pending"
          value={stats?.pending_claims ?? '...'}
          subtitle="Awaiting review"
          icon={Clock}
          color="amber"
        />
        <StatCard
          title="Approved"
          value={stats?.approved_claims ?? '...'}
          subtitle="Adjudicated"
          icon={CheckCircle2}
          color="green"
        />
        <StatCard
          title="Flagged / Review"
          value={stats?.flagged_claims ?? '...'}
          subtitle="Requires attention"
          icon={AlertTriangle}
          color="amber"
        />
        <StatCard
          title="Total Claimed"
          value={`₹${((stats?.total_claimed_amount || 0) / 1000).toFixed(0)}k`}
          subtitle="Gross volume"
          icon={DollarSign}
          color="purple"
        />
        <StatCard
          title="Fraud Alerts"
          value={stats?.active_alerts ?? '...'}
          subtitle="Active anomalies"
          icon={ShieldAlert}
          color="red"
        />
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Monthly Submission Trends */}
        <div className="lg:col-span-2 bg-white border border-[#E0E0E0] p-4 rounded-sm shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-gray-100 mb-3">
            <div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-[#161616] font-mono">
                Claims Verification Trends (2026)
              </h2>
              <p className="text-[11px] text-[#525252]">Monthly submissions vs automated verifications</p>
            </div>
            <TrendingUp className="w-4 h-4 text-[#0F62FE]" />
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={monthlyTrendsData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F0F0F0" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#161616', color: '#fff', fontSize: '11px', borderRadius: '2px' }}
                />
                <Bar dataKey="submitted" fill="#0F62FE" name="Submitted" radius={[2, 2, 0, 0]} />
                <Bar dataKey="verified" fill="#198038" name="Approved" radius={[2, 2, 0, 0]} />
                <Bar dataKey="fraudFlagged" fill="#DA1E28" name="Flagged" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Claim Status Breakdown */}
        <div className="bg-white border border-[#E0E0E0] p-4 rounded-sm shadow-sm flex flex-col justify-between">
          <div className="pb-3 border-b border-gray-100">
            <h2 className="text-xs font-bold uppercase tracking-wider text-[#161616] font-mono">
              Status Breakdown
            </h2>
            <p className="text-[11px] text-[#525252]">Current adjudication pipeline</p>
          </div>

          <div className="h-56 w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={statusDistribution}
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={75}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {statusDistribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#161616', color: '#fff', fontSize: '11px', borderRadius: '2px' }}
                />
                <Legend iconSize={8} wrapperStyle={{ fontSize: '11px' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="pt-2 border-t border-gray-100 text-[11px] text-[#525252] flex justify-between">
            <span>Average Risk Score:</span>
            <span className="font-semibold text-gray-900">{stats?.average_risk_score || '0.0'} / 100</span>
          </div>
        </div>
      </div>

      {/* Bottom Tables: Recent Claims & Fraud Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Recent Claims Table */}
        <div className="lg:col-span-2 bg-white border border-[#E0E0E0] rounded-sm shadow-sm overflow-hidden">
          <div className="p-3 bg-[#FAFAFA] border-b border-[#E0E0E0] flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <FileText className="w-4 h-4 text-[#0F62FE]" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-[#161616] font-mono">
                Recent Insurance Claims
              </h2>
            </div>
            <Link to="/claims" className="text-xs text-[#0F62FE] hover:underline flex items-center space-x-1">
              <span>View all</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#F4F4F4] text-[#525252] border-b border-[#E0E0E0] uppercase font-mono text-[10px]">
                <tr>
                  <th className="py-2.5 px-3">Claim #</th>
                  <th className="py-2.5 px-3">Hospital / Provider</th>
                  <th className="py-2.5 px-3">Amount</th>
                  <th className="py-2.5 px-3">Risk Score</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {recentClaims.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="py-6 text-center text-gray-400 text-xs">
                      No claims recorded yet. Click "Submit Claim" to create one.
                    </td>
                  </tr>
                ) : (
                  recentClaims.map((c) => (
                    <tr key={c.claim_id} className="hover:bg-gray-50 transition-colors">
                      <td className="py-2.5 px-3 font-mono font-medium text-[#0F62FE]">
                        <Link to={`/claims/${c.claim_id}`}>{c.claim_number}</Link>
                      </td>
                      <td className="py-2.5 px-3 text-[#161616] max-w-[160px] truncate">
                        {c.hospital_name || 'N/A'}
                      </td>
                      <td className="py-2.5 px-3 font-medium text-[#161616]">
                        ₹{parseFloat(c.claim_amount).toLocaleString('en-IN')}
                      </td>
                      <td className="py-2.5 px-3">
                        <RiskScoreBadge score={c.risk_score} level={c.risk_level} />
                      </td>
                      <td className="py-2.5 px-3">
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
                      <td className="py-2.5 px-3 text-right">
                        <Link
                          to={`/claims/${c.claim_id}`}
                          className="text-[#0F62FE] hover:underline font-medium text-xs"
                        >
                          Details
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Active Fraud Alerts */}
        <div className="bg-white border border-[#E0E0E0] rounded-sm shadow-sm overflow-hidden flex flex-col justify-between">
          <div>
            <div className="p-3 bg-[#FFF1F1] border-b border-[#FFD7D7] flex items-center justify-between">
              <div className="flex items-center space-x-2 text-[#DA1E28]">
                <ShieldAlert className="w-4 h-4" />
                <h2 className="text-xs font-bold uppercase tracking-wider font-mono">
                  Active Fraud Alerts
                </h2>
              </div>
              <Link to="/fraud-detection" className="text-xs text-[#DA1E28] hover:underline flex items-center space-x-1">
                <span>Investigate</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
            </div>

            <div className="p-3 divide-y divide-gray-100">
              {recentAlerts.length === 0 ? (
                <div className="py-8 text-center text-gray-400 text-xs">
                  <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2 opacity-60" />
                  <p>No active fraud alerts detected.</p>
                  <p className="text-[11px] text-gray-400">All claims verified clean.</p>
                </div>
              ) : (
                recentAlerts.map((alt) => (
                  <div key={alt.alert_id} className="py-2.5 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-red-100 text-red-800 font-semibold">
                        {alt.severity}
                      </span>
                      <span className="text-[10px] text-gray-400 font-mono">
                        {alt.created_at?.slice(0, 10)}
                      </span>
                    </div>
                    <p className="text-xs font-semibold text-[#161616] leading-tight">
                      {alt.alert_type}
                    </p>
                    <p className="text-[11px] text-[#525252] line-clamp-2">
                      {alt.description}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="p-3 bg-gray-50 border-t border-gray-100">
            <Link
              to="/reports"
              className="w-full flex items-center justify-center space-x-2 py-1.5 bg-white border border-[#E0E0E0] hover:bg-gray-100 text-xs text-[#161616] font-medium transition-colors rounded-sm"
            >
              <Sparkles className="w-3.5 h-3.5 text-[#0F62FE]" />
              <span>Generate Explainable AI Report</span>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
