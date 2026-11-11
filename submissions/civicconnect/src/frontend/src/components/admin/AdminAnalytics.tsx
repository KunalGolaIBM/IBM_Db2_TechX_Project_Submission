import React, { useMemo } from 'react';
import {
  BarChart3,
  TrendingUp,
  Clock,
  Star,
  CheckCircle2,
  AlertTriangle,
  Award,
  Users
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import { Complaint, CIVIC_CATEGORIES } from '../../types';

interface AdminAnalyticsProps {
  complaints: Complaint[];
}

export const AdminAnalytics: React.FC<AdminAnalyticsProps> = ({ complaints }) => {
  const total = complaints.length;
  const resolved = complaints.filter(c => c.status === 'Resolved').length;
  const inProgress = complaints.filter(c => c.status === 'In Progress').length;
  const pending = complaints.filter(c => c.status === 'Submitted' || c.status === 'Under Review' || c.status === 'Assigned').length;

  // Department SLA breakdown
  const deptPerformance = useMemo(() => {
    const map: Record<string, { total: number; resolved: number; avgHours: number }> = {};
    complaints.forEach(c => {
      const d = c.departmentName || 'Unassigned';
      if (!map[d]) map[d] = { total: 0, resolved: 0, avgHours: 0 };
      map[d].total += 1;
      if (c.status === 'Resolved') {
        map[d].resolved += 1;
      }
    });

    return Object.entries(map).map(([dept, data]) => ({
      department: dept.replace('Department', '').trim(),
      total: data.total,
      resolved: data.resolved,
      efficiency: data.total > 0 ? Math.round((data.resolved / data.total) * 100) : 0
    }));
  }, [complaints]);

  // Priority distribution
  const priorityData = useMemo(() => {
    const counts = { urgent: 0, high: 0, medium: 0, low: 0 };
    complaints.forEach(c => {
      if (counts[c.priority] !== undefined) counts[c.priority] += 1;
    });
    return [
      { name: 'Urgent', count: counts.urgent, color: '#ef4444' },
      { name: 'High', count: counts.high, color: '#f59e0b' },
      { name: 'Medium', count: counts.medium, color: '#0ea5e9' },
      { name: 'Low', count: counts.low, color: '#64748b' }
    ];
  }, [complaints]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Municipal Service Analytics & SLA Performance</h1>
        <p className="text-xs text-slate-500">
          Transparency benchmarks, department response metrics, and resolution turnaround analytics
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-xs">
          <span className="text-xs text-slate-400 font-semibold uppercase">Total Complaints Handled</span>
          <p className="text-2xl font-bold text-slate-900 mt-1">{total}</p>
          <span className="text-[11px] text-teal-600 font-medium">100% digitally tracked</span>
        </div>

        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-xs">
          <span className="text-xs text-slate-400 font-semibold uppercase">Overall Resolution Rate</span>
          <p className="text-2xl font-bold text-emerald-700 mt-1">
            {total > 0 ? Math.round((resolved / total) * 100) : 0}%
          </p>
          <span className="text-[11px] text-slate-400">Target SLA benchmark: 85%</span>
        </div>

        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-xs">
          <span className="text-xs text-slate-400 font-semibold uppercase">Active Field Queue</span>
          <p className="text-2xl font-bold text-amber-700 mt-1">{inProgress + pending}</p>
          <span className="text-[11px] text-slate-400">Across 6 municipal departments</span>
        </div>

        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-xs">
          <span className="text-xs text-slate-400 font-semibold uppercase">Citizen Feedback Avg</span>
          <p className="text-2xl font-bold text-amber-600 mt-1 flex items-center gap-1">
            <span>4.8</span>
            <Star className="w-5 h-5 fill-amber-400 text-amber-400" />
          </p>
          <span className="text-[11px] text-slate-400">Public satisfaction rating</span>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Department Efficiency Comparison */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/90 shadow-xs">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-3">
            Department Resolution Efficiency (%)
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={deptPerformance} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="department" angle={-20} textAnchor="end" tick={{ fontSize: 10, fill: '#64748b' }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#64748b' }} />
                <Tooltip
                  formatter={(val) => [`${val}%`, 'Resolution Rate']}
                  contentStyle={{ backgroundColor: '#0f172a', borderRadius: '8px', color: '#fff', fontSize: '12px' }}
                />
                <Bar dataKey="efficiency" fill="#0d9488" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Priority Breakdown */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/90 shadow-xs">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-3">
            Complaint Severity & Urgency Distribution
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={priorityData}
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  innerRadius={45}
                  dataKey="count"
                  paddingAngle={3}
                >
                  {priorityData.map((entry, index) => (
                    <Cell key={`prio-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderRadius: '8px', color: '#fff', fontSize: '12px' }}
                />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};
