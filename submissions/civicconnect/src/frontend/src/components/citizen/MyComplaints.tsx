import React, { useState } from 'react';
import {
  FolderClock,
  Search,
  Filter,
  MapPin,
  Calendar,
  Tag,
  ArrowRight,
  Plus,
  Clock,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react';
import { Complaint, ComplaintStatus, CIVIC_CATEGORIES } from '../../types';

interface MyComplaintsProps {
  complaints: Complaint[];
  onSelectComplaint: (complaint: Complaint) => void;
  onOpenReportForm: () => void;
}

export const MyComplaints: React.FC<MyComplaintsProps> = ({
  complaints,
  onSelectComplaint,
  onOpenReportForm
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');

  // Filter complaints
  const filtered = complaints.filter(comp => {
    const matchesSearch =
      comp.complaintId.toLowerCase().includes(searchTerm.toLowerCase()) ||
      comp.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      comp.location.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus = selectedStatus === 'ALL' || comp.status === selectedStatus;
    const matchesCategory = selectedCategory === 'ALL' || comp.category === selectedCategory;

    return matchesSearch && matchesStatus && matchesCategory;
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
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900">My Registered Complaints</h1>
          <p className="text-xs text-slate-500">Track and monitor all civic grievances you have submitted</p>
        </div>
        <button
          type="button"
          onClick={onOpenReportForm}
          className="self-start sm:self-center px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold shadow-sm transition flex items-center gap-1.5"
        >
          <Plus className="w-4 h-4" />
          <span>Report New Grievance</span>
        </button>
      </div>

      {/* Filters & Search */}
      <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-xs space-y-3">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by ticket ID (CCMS-...), title, or locality..."
              className="w-full pl-9 pr-3 py-2 text-xs sm:text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>

          <div className="flex gap-2">
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white"
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

            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white max-w-[180px] truncate"
            >
              <option value="ALL">All Categories</option>
              {CIVIC_CATEGORIES.map(c => (
                <option key={c.name} value={c.name}>{c.name}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Complaints List */}
      {filtered.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-xl border border-slate-200 p-6">
          <FolderClock className="w-12 h-12 text-slate-300 mx-auto mb-2" />
          <h3 className="text-sm font-bold text-slate-700">No matching complaints found</h3>
          <p className="text-xs text-slate-400 mt-1">Try adjusting your filters or search keywords.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {filtered.map(comp => (
            <div
              key={comp.id}
              onClick={() => onSelectComplaint(comp)}
              className="p-4 rounded-xl bg-white border border-slate-200/90 hover:border-teal-400 hover:shadow-sm cursor-pointer transition flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="space-y-1.5 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-xs font-bold text-teal-800 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
                    {comp.complaintId}
                  </span>
                  <span className={`text-[11px] px-2 py-0.5 rounded-full border font-semibold ${getStatusBadge(comp.status)}`}>
                    {comp.status}
                  </span>
                  <span className="text-xs text-slate-500 font-medium">{comp.category}</span>
                </div>

                <h3 className="text-sm sm:text-base font-bold text-slate-900">{comp.title}</h3>

                <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                  <span className="flex items-center gap-1">
                    <MapPin className="w-3.5 h-3.5 text-slate-400" />
                    <span>{comp.location}</span>
                  </span>
                  <span>•</span>
                  <span>Assigned: <strong>{comp.departmentName || 'Under Review'}</strong></span>
                  <span>•</span>
                  <span>Logged: {new Date(comp.createdAt).toLocaleDateString()}</span>
                </div>
              </div>

              {/* Action Button */}
              <div className="flex items-center gap-2 self-end md:self-center">
                <button
                  type="button"
                  className="px-3 py-1.5 rounded-lg bg-teal-50 hover:bg-teal-100 text-teal-800 text-xs font-semibold border border-teal-200 transition flex items-center gap-1"
                >
                  <span>Track Status & History</span>
                  <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
