import React, { useState, useMemo } from 'react';
import {
  FolderClock,
  Clock,
  TrendingUp,
  CheckCircle2,
  Percent,
  Search,
  Filter,
  Building,
  AlertTriangle,
  ArrowUpDown,
  Eye,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  Calendar,
  Layers,
  Sparkles
} from 'lucide-react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  LineChart,
  Line
} from 'recharts';
import { Complaint, ComplaintPriority, ComplaintStatus, CIVIC_CATEGORIES } from '../../types';

interface AdminDashboardProps {
  complaints: Complaint[];
  onSelectComplaint: (complaint: Complaint) => void;
  onNavigateTab: (tabId: string) => void;
}

const STATUS_COLORS: Record<string, string> = {
  'Submitted': '#3b82f6',
  'Under Review': '#a855f7',
  'Assigned': '#6366f1',
  'In Progress': '#f59e0b',
  'Resolved': '#10b981',
  'Rejected': '#f43f5e',
  'Reopened': '#f97316'
};

export const AdminDashboard: React.FC<AdminDashboardProps> = ({
  complaints,
  onSelectComplaint,
  onNavigateTab
}) => {
  // Search, filter, sorting, pagination states
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [departmentFilter, setDepartmentFilter] = useState('ALL');
  const [priorityFilter, setPriorityFilter] = useState('ALL');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(8);
  const [sortField, setSortField] = useState<'createdAt' | 'priority' | 'status'>('createdAt');
  const [sortAsc, setSortAsc] = useState(false);

  // 1. Dynamic Top Statistics from database
  const total = complaints.length;
  const newComplaints = complaints.filter(c => c.status === 'Submitted' || c.status === 'Under Review').length;
  const pendingAssigned = complaints.filter(c => c.status === 'Assigned').length;
  const inProgress = complaints.filter(c => c.status === 'In Progress').length;
  const resolved = complaints.filter(c => c.status === 'Resolved').length;
  const resolutionRate = total > 0 ? Math.round((resolved / total) * 100) : 0;

  // 2. Chart 1: Status Distribution
  const statusChartData = useMemo(() => {
    const counts: Record<string, number> = {};
    complaints.forEach(c => {
      counts[c.status] = (counts[c.status] || 0) + 1;
    });
    return Object.entries(counts).map(([name, value]) => ({
      name,
      value,
      color: STATUS_COLORS[name] || '#64748b'
    }));
  }, [complaints]);

  // 3. Chart 2: Category Distribution
  const categoryChartData = useMemo(() => {
    const counts: Record<string, number> = {};
    CIVIC_CATEGORIES.forEach(c => (counts[c.name] = 0));
    complaints.forEach(c => {
      counts[c.category] = (counts[c.category] || 0) + 1;
    });
    return Object.entries(counts).map(([name, count]) => ({
      name: name.replace('Problems', '').replace('Damage', '').trim(),
      fullName: name,
      count
    }));
  }, [complaints]);

  // 4. Chart 3: Over Time (Day by Day aggregation)
  const timeChartData = useMemo(() => {
    const dateMap: Record<string, number> = {};
    const sorted = [...complaints].sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime());

    sorted.forEach(c => {
      const d = new Date(c.createdAt).toLocaleDateString([], { month: 'short', day: 'numeric' });
      dateMap[d] = (dateMap[d] || 0) + 1;
    });

    // If empty or single day, construct helpful points
    if (Object.keys(dateMap).length === 0) {
      return [{ date: 'Today', complaints: 0 }];
    }
    return Object.entries(dateMap).map(([date, count]) => ({ date, complaints: count }));
  }, [complaints]);

  // 5. Chart 4: Department-wise Distribution
  const departmentChartData = useMemo(() => {
    const map: Record<string, { total: number; resolved: number; inProgress: number }> = {};
    complaints.forEach(c => {
      const dept = c.departmentName || 'Unassigned';
      if (!map[dept]) map[dept] = { total: 0, resolved: 0, inProgress: 0 };
      map[dept].total += 1;
      if (c.status === 'Resolved') map[dept].resolved += 1;
      if (c.status === 'In Progress') map[dept].inProgress += 1;
    });

    return Object.entries(map).map(([dept, data]) => ({
      name: dept.replace('Department', '').replace('Municipal', '').trim(),
      fullDept: dept,
      total: data.total,
      resolved: data.resolved,
      inProgress: data.inProgress,
      rate: data.total > 0 ? Math.round((data.resolved / data.total) * 100) : 0
    }));
  }, [complaints]);

  // Table filtering and sorting
  const filteredComplaints = useMemo(() => {
    return complaints.filter(comp => {
      const matchesSearch =
        comp.complaintId.toLowerCase().includes(searchTerm.toLowerCase()) ||
        comp.citizenName.toLowerCase().includes(searchTerm.toLowerCase()) ||
        comp.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        comp.location.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesCat = categoryFilter === 'ALL' || comp.category === categoryFilter;
      const matchesStat = statusFilter === 'ALL' || comp.status === statusFilter;
      const matchesDept = departmentFilter === 'ALL' || comp.departmentName === departmentFilter;
      const matchesPrio = priorityFilter === 'ALL' || comp.priority === priorityFilter;

      return matchesSearch && matchesCat && matchesStat && matchesDept && matchesPrio;
    }).sort((a, b) => {
      let comparison = 0;
      if (sortField === 'createdAt') {
        comparison = new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
      } else if (sortField === 'priority') {
        const pOrder: Record<string, number> = { urgent: 4, high: 3, medium: 2, low: 1 };
        comparison = (pOrder[a.priority] || 0) - (pOrder[b.priority] || 0);
      } else if (sortField === 'status') {
        comparison = a.status.localeCompare(b.status);
      }
      return sortAsc ? comparison : -comparison;
    });
  }, [complaints, searchTerm, categoryFilter, statusFilter, departmentFilter, priorityFilter, sortField, sortAsc]);

  // Pagination calculation
  const totalPages = Math.ceil(filteredComplaints.length / pageSize) || 1;
  const paginatedComplaints = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredComplaints.slice(start, start + pageSize);
  }, [filteredComplaints, currentPage, pageSize]);

  const getStatusBadge = (status: ComplaintStatus) => {
    switch (status) {
      case 'Submitted':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'Under Review':
        return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'Assigned':
        return 'bg-indigo-100 text-indigo-800 border-indigo-200';
      case 'In Progress':
        return 'bg-amber-100 text-amber-800 border-amber-200';
      case 'Resolved':
        return 'bg-emerald-100 text-emerald-800 border-emerald-200';
      case 'Rejected':
        return 'bg-rose-100 text-rose-800 border-rose-200';
      case 'Reopened':
        return 'bg-orange-100 text-orange-800 border-orange-200';
      default:
        return 'bg-slate-100 text-slate-800 border-slate-200';
    }
  };

  const getPriorityBadge = (p: ComplaintPriority) => {
    switch (p) {
      case 'urgent':
        return 'bg-red-100 text-red-800 font-bold';
      case 'high':
        return 'bg-amber-100 text-amber-800 font-semibold';
      case 'medium':
        return 'bg-sky-100 text-sky-800';
      case 'low':
        return 'bg-slate-100 text-slate-700';
    }
  };

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-bold text-slate-900">Municipal Administrator Dashboard</h1>
            <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
              Live Database
            </span>
          </div>
          <p className="text-xs text-slate-500">
            Real-time complaint triage, department allocation, and civic performance analytics
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onNavigateTab('admin-departments')}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold transition flex items-center gap-1.5"
          >
            <Building className="w-3.5 h-3.5" />
            <span>Manage Departments</span>
          </button>
        </div>
      </div>

      {/* TOP STATISTIC CARDS */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4">
        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-xs">
          <span className="text-[11px] font-semibold uppercase text-slate-500 block">Total Complaints</span>
          <p className="text-2xl font-bold text-slate-900 mt-1">{total}</p>
          <span className="text-[10px] text-slate-400">All recorded</span>
        </div>

        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-xs">
          <span className="text-[11px] font-semibold uppercase text-blue-600 block">New / Review</span>
          <p className="text-2xl font-bold text-blue-700 mt-1">{newComplaints}</p>
          <span className="text-[10px] text-slate-400">Needs assignment</span>
        </div>

        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-xs">
          <span className="text-[11px] font-semibold uppercase text-indigo-600 block">Pending Queue</span>
          <p className="text-2xl font-bold text-indigo-700 mt-1">{pendingAssigned}</p>
          <span className="text-[10px] text-slate-400">Assigned to depts</span>
        </div>

        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-xs">
          <span className="text-[11px] font-semibold uppercase text-amber-600 block">In Progress</span>
          <p className="text-2xl font-bold text-amber-700 mt-1">{inProgress}</p>
          <span className="text-[10px] text-slate-400">Field work active</span>
        </div>

        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-xs">
          <span className="text-[11px] font-semibold uppercase text-emerald-600 block">Resolved</span>
          <p className="text-2xl font-bold text-emerald-700 mt-1">{resolved}</p>
          <span className="text-[10px] text-emerald-600 font-medium">Work inspected</span>
        </div>

        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-xs">
          <span className="text-[11px] font-semibold uppercase text-teal-600 block">Resolution Rate</span>
          <p className="text-2xl font-bold text-teal-700 mt-1">{resolutionRate}%</p>
          <span className="text-[10px] text-slate-400">Efficiency benchmark</span>
        </div>
      </div>

      {/* CHARTS GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Chart 1: Status Distribution (Pie / Donut) */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/90 shadow-xs">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">1. Complaints by Status</h3>
            <span className="text-[11px] text-slate-400 font-medium">Current Status Mix</span>
          </div>
          <div className="h-64">
            {statusChartData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-slate-400">
                No complaint records yet
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statusChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {statusChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', borderRadius: '8px', color: '#fff', fontSize: '12px' }}
                  />
                  <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Chart 2: Complaints by Category (Bar Chart) */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/90 shadow-xs">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">2. Complaints by Category</h3>
            <span className="text-[11px] text-slate-400 font-medium">Issue Types</span>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categoryChartData} margin={{ top: 10, right: 10, left: -20, bottom: 25 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="name"
                  angle={-25}
                  textAnchor="end"
                  interval={0}
                  tick={{ fontSize: 10, fill: '#64748b' }}
                />
                <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: '#64748b' }} />
                <Tooltip
                  formatter={(val: any, _name: any, item: any) => [val, item.payload.fullName]}
                  contentStyle={{ backgroundColor: '#0f172a', borderRadius: '8px', color: '#fff', fontSize: '12px' }}
                />
                <Bar dataKey="count" fill="#0d9488" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 3: Over Time Submission Trend */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/90 shadow-xs">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">3. Grievances Over Time</h3>
            <span className="text-[11px] text-slate-400 font-medium">Daily Incoming Volume</span>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeChartData} margin={{ top: 10, right: 10, left: -20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#64748b' }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: '#64748b' }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderRadius: '8px', color: '#fff', fontSize: '12px' }}
                />
                <Line
                  type="monotone"
                  dataKey="complaints"
                  stroke="#2563eb"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: '#2563eb' }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 4: Department-wise Complaint & Resolution Breakdown */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/90 shadow-xs">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">4. Department Workload & Performance</h3>
            <span className="text-[11px] text-slate-400 font-medium">Total vs Resolved</span>
          </div>
          <div className="h-64">
            {departmentChartData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-slate-400">
                No department assignments yet
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={departmentChartData} margin={{ top: 10, right: 10, left: -20, bottom: 25 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis
                    dataKey="name"
                    angle={-20}
                    textAnchor="end"
                    interval={0}
                    tick={{ fontSize: 10, fill: '#64748b' }}
                  />
                  <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: '#64748b' }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', borderRadius: '8px', color: '#fff', fontSize: '12px' }}
                  />
                  <Legend wrapperStyle={{ fontSize: '11px' }} />
                  <Bar dataKey="total" name="Total Assigned" fill="#6366f1" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="resolved" name="Resolved" fill="#10b981" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* RECENT COMPLAINTS TABLE (With Search, Filter, Sort, Pagination) */}
      <div className="p-5 rounded-2xl bg-white border border-slate-200/90 shadow-xs space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-slate-900">Complaints Management Table</h2>
            <p className="text-xs text-slate-500">Review submitted grievances, assign municipal departments, and audit progress</p>
          </div>
          <span className="text-xs font-semibold text-slate-600 bg-slate-100 px-3 py-1 rounded-lg self-start">
            Showing {filteredComplaints.length} tickets
          </span>
        </div>

        {/* Filter Toolbar */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
          {/* Search */}
          <div className="relative sm:col-span-2 lg:col-span-1">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
              placeholder="Search ID, citizen, road..."
              className="w-full pl-8 pr-2.5 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>

          {/* Category Filter */}
          <select
            value={categoryFilter}
            onChange={(e) => {
              setCategoryFilter(e.target.value);
              setCurrentPage(1);
            }}
            className="px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 bg-white truncate"
          >
            <option value="ALL">All Categories</option>
            {CIVIC_CATEGORIES.map(c => (
              <option key={c.name} value={c.name}>{c.name}</option>
            ))}
          </select>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setCurrentPage(1);
            }}
            className="px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
          >
            <option value="ALL">All Statuses</option>
            <option value="Submitted">Submitted</option>
            <option value="Under Review">Under Review</option>
            <option value="Assigned">Assigned</option>
            <option value="In Progress">In Progress</option>
            <option value="Resolved">Resolved</option>
            <option value="Rejected">Rejected</option>
            <option value="Reopened">Reopened</option>
          </select>

          {/* Priority Filter */}
          <select
            value={priorityFilter}
            onChange={(e) => {
              setPriorityFilter(e.target.value);
              setCurrentPage(1);
            }}
            className="px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
          >
            <option value="ALL">All Priorities</option>
            <option value="urgent">Urgent</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>

          {/* Sort field toggle */}
          <button
            type="button"
            onClick={() => setSortAsc(!sortAsc)}
            className="px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 bg-slate-50 hover:bg-slate-100 text-slate-700 flex items-center justify-between"
          >
            <span>Order: {sortAsc ? 'Ascending' : 'Newest First'}</span>
            <ArrowUpDown className="w-3.5 h-3.5 text-slate-400" />
          </button>
        </div>

        {/* Complaints Table */}
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900 text-white uppercase text-[10px] tracking-wider font-semibold">
              <tr>
                <th className="p-3">Complaint ID</th>
                <th className="p-3">Citizen Name</th>
                <th className="p-3">Category</th>
                <th className="p-3">Location</th>
                <th className="p-3">Department</th>
                <th className="p-3">Priority</th>
                <th className="p-3">Status</th>
                <th className="p-3">Submitted</th>
                <th className="p-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {paginatedComplaints.length === 0 ? (
                <tr>
                  <td colSpan={9} className="p-6 text-center text-slate-400">
                    No complaints match your active filters.
                  </td>
                </tr>
              ) : (
                paginatedComplaints.map(comp => (
                  <tr
                    key={comp.id}
                    className="hover:bg-slate-50/80 transition cursor-pointer"
                    onClick={() => onSelectComplaint(comp)}
                  >
                    <td className="p-3 font-mono font-bold text-teal-800 whitespace-nowrap">
                      {comp.complaintId}
                    </td>
                    <td className="p-3 font-medium text-slate-800 whitespace-nowrap">
                      {comp.citizenName}
                    </td>
                    <td className="p-3 text-slate-600 whitespace-nowrap">{comp.category}</td>
                    <td className="p-3 text-slate-600 max-w-[160px] truncate" title={comp.location}>
                      {comp.location}
                    </td>
                    <td className="p-3 text-slate-700 whitespace-nowrap">
                      <span className="font-semibold text-slate-900">
                        {comp.departmentName || <span className="text-amber-600 italic">Unassigned</span>}
                      </span>
                    </td>
                    <td className="p-3 whitespace-nowrap">
                      <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold ${getPriorityBadge(comp.priority)}`}>
                        {comp.priority}
                      </span>
                    </td>
                    <td className="p-3 whitespace-nowrap">
                      <span className={`px-2 py-0.5 rounded-full border text-[11px] font-semibold ${getStatusBadge(comp.status)}`}>
                        {comp.status}
                      </span>
                    </td>
                    <td className="p-3 text-slate-500 whitespace-nowrap">
                      {new Date(comp.createdAt).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                    </td>
                    <td className="p-3 text-right whitespace-nowrap">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectComplaint(comp);
                        }}
                        className="px-2.5 py-1 text-xs font-semibold rounded bg-teal-50 hover:bg-teal-100 text-teal-800 border border-teal-200 transition"
                      >
                        Manage / Assign
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between text-xs text-slate-500 pt-2">
            <span>
              Page {currentPage} of {totalPages}
            </span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                className="p-1 rounded border border-slate-300 hover:bg-slate-100 disabled:opacity-40"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                type="button"
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                className="p-1 rounded border border-slate-300 hover:bg-slate-100 disabled:opacity-40"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
