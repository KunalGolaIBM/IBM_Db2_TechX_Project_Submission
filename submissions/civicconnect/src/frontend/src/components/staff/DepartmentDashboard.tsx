import React, { useState } from 'react';
import {
  HardHat,
  Clock,
  CheckCircle2,
  TrendingUp,
  MapPin,
  Calendar,
  Camera,
  ArrowRight,
  Search,
  Filter,
  Layers,
  Sparkles,
  FileCheck
} from 'lucide-react';
import { Complaint, ComplaintStatus } from '../../types';
import { useAuth } from '../../context/AuthContext';
import { SAMPLE_CIVIC_PHOTOS } from '../../utils/photoPresets';

interface DepartmentDashboardProps {
  complaints: Complaint[];
  onSelectComplaint: (complaint: Complaint) => void;
}

export const DepartmentDashboard: React.FC<DepartmentDashboardProps> = ({
  complaints,
  onSelectComplaint
}) => {
  const { activeDepartment, userProfile } = useAuth();
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [search, setSearch] = useState<string>('');

  // Filter complaints strictly to the active staff department
  const deptComplaints = complaints.filter(
    c => c.departmentName?.toLowerCase() === activeDepartment.toLowerCase()
  );

  const pending = deptComplaints.filter(c => c.status === 'Assigned').length;
  const inProgress = deptComplaints.filter(c => c.status === 'In Progress').length;
  const resolved = deptComplaints.filter(c => c.status === 'Resolved').length;

  const filtered = deptComplaints.filter(c => {
    const matchesStatus = statusFilter === 'ALL' || c.status === statusFilter;
    const matchesSearch =
      c.complaintId.toLowerCase().includes(search.toLowerCase()) ||
      c.title.toLowerCase().includes(search.toLowerCase()) ||
      c.location.toLowerCase().includes(search.toLowerCase());
    return matchesStatus && matchesSearch;
  });

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

  return (
    <div className="space-y-6">
      {/* Department Header */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-emerald-950 text-white shadow-md border border-slate-800">
        <div className="flex items-center gap-2 mb-2">
          <HardHat className="w-5 h-5 text-emerald-400" />
          <span className="text-xs uppercase tracking-wider font-bold text-emerald-300">
            Field Operations Portal
          </span>
        </div>
        <h1 className="text-2xl font-bold">{activeDepartment}</h1>
        <p className="text-xs text-slate-300 mt-1">
          Assigned field grievances requiring on-site inspection, material deployment, and resolution proof.
        </p>
      </div>

      {/* Staff Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-xs">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase">Pending Assignment</span>
            <Clock className="w-4 h-4 text-indigo-600" />
          </div>
          <p className="text-2xl font-bold text-indigo-700 mt-1">{pending}</p>
          <span className="text-[11px] text-slate-400">Awaiting field team dispatch</span>
        </div>

        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-xs">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase">In Progress</span>
            <TrendingUp className="w-4 h-4 text-amber-600" />
          </div>
          <p className="text-2xl font-bold text-amber-700 mt-1">{inProgress}</p>
          <span className="text-[11px] text-slate-400">Active repairs on-site</span>
        </div>

        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-xs">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase">Completed & Resolved</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <p className="text-2xl font-bold text-emerald-700 mt-1">{resolved}</p>
          <span className="text-[11px] text-emerald-600 font-medium">Work inspected & verified</span>
        </div>
      </div>

      {/* Filter and Complaints Card List */}
      <div className="p-5 rounded-2xl bg-white border border-slate-200/90 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-slate-900">Assigned Department Work Orders</h2>
            <p className="text-xs text-slate-500">Select a grievance to start work, add progress notes, or upload completion photo</p>
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search assigned tickets..."
              className="px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
            >
              <option value="ALL">All Statuses</option>
              <option value="Assigned">Assigned</option>
              <option value="In Progress">In Progress</option>
              <option value="Resolved">Resolved</option>
            </select>
          </div>
        </div>

        {filtered.length === 0 ? (
          <div className="text-center py-12 text-slate-400 text-xs border border-dashed border-slate-200 rounded-xl">
            No complaints currently assigned to {activeDepartment} matching this filter.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3">
            {filtered.map(comp => (
              <div
                key={comp.id}
                onClick={() => onSelectComplaint(comp)}
                className="p-4 rounded-xl border border-slate-200/90 hover:border-emerald-400 hover:shadow-xs cursor-pointer transition bg-white flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs font-bold text-emerald-900 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                      {comp.complaintId}
                    </span>
                    <span className={`text-[11px] px-2 py-0.5 rounded-full border font-semibold ${getStatusBadge(comp.status)}`}>
                      {comp.status}
                    </span>
                    <span className="text-xs font-bold text-amber-700 bg-amber-50 px-2 py-0.5 rounded uppercase">
                      Priority: {comp.priority}
                    </span>
                  </div>

                  <h3 className="text-sm sm:text-base font-bold text-slate-900">{comp.title}</h3>
                  <p className="text-xs text-slate-600 line-clamp-1">{comp.description}</p>

                  <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 pt-1">
                    <span className="flex items-center gap-1 font-medium text-slate-700">
                      <MapPin className="w-3.5 h-3.5 text-slate-400" />
                      <span>{comp.location}</span>
                    </span>
                    {comp.landmark && <span>(Near {comp.landmark})</span>}
                    <span>•</span>
                    <span>Reported by: {comp.citizenName}</span>
                  </div>
                </div>

                {/* Staff Quick Action button */}
                <div className="flex items-center gap-2 self-end md:self-center">
                  <button
                    type="button"
                    className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition flex items-center gap-1.5 shadow-xs"
                  >
                    <FileCheck className="w-3.5 h-3.5" />
                    <span>Open Work Order & Update</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
