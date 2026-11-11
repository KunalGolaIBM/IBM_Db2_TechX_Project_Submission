import React, { useState } from 'react';
import {
  FilePlus2,
  FolderClock,
  Clock,
  CheckCircle2,
  AlertCircle,
  Search,
  ArrowRight,
  MapPin,
  Tag,
  Calendar,
  Sparkles,
  ChevronRight,
  ShieldCheck,
  TrendingUp,
  RotateCcw
} from 'lucide-react';
import { Complaint, ComplaintStatus } from '../../types';
import { useAuth } from '../../context/AuthContext';

interface CitizenDashboardProps {
  complaints: Complaint[];
  onOpenReportForm: (preset?: 'pothole' | 'garbage' | 'streetlight') => void;
  onSelectComplaint: (complaint: Complaint) => void;
  onNavigateTab: (tabId: string) => void;
}

export const CitizenDashboard: React.FC<CitizenDashboardProps> = ({
  complaints,
  onOpenReportForm,
  onSelectComplaint,
  onNavigateTab
}) => {
  const { userProfile } = useAuth();
  const [trackSearchId, setTrackSearchId] = useState('');
  const [trackResult, setTrackResult] = useState<Complaint | null>(null);
  const [trackError, setTrackError] = useState<string | null>(null);

  // Statistics calculation from actual complaints records
  const total = complaints.length;
  const pending = complaints.filter(c => c.status === 'Submitted' || c.status === 'Under Review').length;
  const inProgress = complaints.filter(c => c.status === 'Assigned' || c.status === 'In Progress').length;
  const resolved = complaints.filter(c => c.status === 'Resolved').length;

  const handleTrackSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setTrackError(null);
    setTrackResult(null);

    const clean = trackSearchId.trim().toUpperCase();
    if (!clean) return;

    const matched = complaints.find(c => c.complaintId.toUpperCase() === clean);
    if (matched) {
      setTrackResult(matched);
    } else {
      setTrackError(`No complaint found with ID "${clean}". Please verify your ticket reference.`);
    }
  };

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
      {/* Welcome Banner with Prominent CTA */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-teal-950 p-6 sm:p-8 text-white shadow-md border border-slate-800">
        <div className="relative z-10 max-w-2xl">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-teal-500/20 text-teal-300 border border-teal-500/30 mb-3">
            <ShieldCheck className="w-3.5 h-3.5" />
            Citizen Grievance Redressal Portal
          </span>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
            Welcome, {userProfile?.name?.split(' ')[0] || 'Resident'}
          </h1>
          <p className="mt-2 text-xs sm:text-sm text-slate-300 leading-relaxed">
            Report municipal sanitation, road potholes, broken streetlights, or drainage failures directly to your local civic administration. Track inspection and resolution progress in real time.
          </p>

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => onOpenReportForm()}
              className="px-5 py-2.5 rounded-xl bg-teal-500 hover:bg-teal-400 text-slate-950 font-bold text-xs sm:text-sm shadow-md transition flex items-center gap-2"
            >
              <FilePlus2 className="w-4 h-4" />
              <span>Report a Problem</span>
            </button>
            <button
              type="button"
              onClick={() => onNavigateTab('citizen-complaints')}
              className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-medium text-xs sm:text-sm border border-slate-700 transition flex items-center gap-2"
            >
              <FolderClock className="w-4 h-4 text-teal-400" />
              <span>View My Complaints</span>
            </button>
          </div>
        </div>
      </div>

      {/* 4 Summary Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-xs">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Total Complaints</span>
            <FolderClock className="w-4 h-4 text-teal-600" />
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">{total}</p>
          <span className="text-[11px] text-slate-400">Lifetime logged tickets</span>
        </div>

        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-xs">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Under Review</span>
            <Clock className="w-4 h-4 text-purple-600" />
          </div>
          <p className="text-2xl font-bold text-purple-700 mt-2">{pending}</p>
          <span className="text-[11px] text-slate-400">Awaiting dept routing</span>
        </div>

        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-xs">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">In Progress</span>
            <TrendingUp className="w-4 h-4 text-amber-600" />
          </div>
          <p className="text-2xl font-bold text-amber-700 mt-2">{inProgress}</p>
          <span className="text-[11px] text-slate-400">Field work underway</span>
        </div>

        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-xs">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Resolved</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <p className="text-2xl font-bold text-emerald-700 mt-2">{resolved}</p>
          <span className="text-[11px] text-emerald-600 font-medium">
            {total > 0 ? `${Math.round((resolved / total) * 100)}% resolution rate` : '0% resolved'}
          </span>
        </div>
      </div>

      {/* Direct Tracking Input */}
      <div className="p-4 sm:p-5 rounded-2xl bg-white border border-slate-200/90 shadow-xs">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-2">
          Track Grievance By Complaint ID
        </h3>
        <form onSubmit={handleTrackSubmit} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
            <input
              type="text"
              value={trackSearchId}
              onChange={(e) => setTrackSearchId(e.target.value)}
              placeholder="Enter unique ID (e.g. CCMS-2026-0001)..."
              className="w-full pl-9 pr-3 py-2 text-xs sm:text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-teal-500 bg-slate-50/50"
            />
          </div>
          <button
            type="submit"
            className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs sm:text-sm font-semibold transition"
          >
            Track Status
          </button>
        </form>

        {trackError && <p className="text-xs text-red-600 mt-2">{trackError}</p>}

        {trackResult && (
          <div className="mt-3 p-3.5 rounded-xl bg-teal-50 border border-teal-200 flex items-center justify-between">
            <div>
              <span className="font-mono text-xs font-bold text-teal-900 mr-2">{trackResult.complaintId}</span>
              <span className={`text-[11px] px-2 py-0.5 rounded-full border font-bold ${getStatusBadge(trackResult.status)}`}>
                {trackResult.status}
              </span>
              <p className="text-xs font-medium text-slate-800 mt-1">{trackResult.title}</p>
              <p className="text-[11px] text-slate-500">{trackResult.location} • Assigned to: {trackResult.departmentName || 'Pending'}</p>
            </div>
            <button
              type="button"
              onClick={() => onSelectComplaint(trackResult)}
              className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-teal-600 text-white hover:bg-teal-500"
            >
              View Full Timeline
            </button>
          </div>
        )}
      </div>

      {/* Recent Complaints Section */}
      <div className="p-4 sm:p-6 rounded-2xl bg-white border border-slate-200/90 shadow-xs">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-bold text-slate-900">Recent Complaints</h2>
            <p className="text-xs text-slate-500">Status and department updates for your submitted issues</p>
          </div>
          {complaints.length > 0 && (
            <button
              type="button"
              onClick={() => onNavigateTab('citizen-complaints')}
              className="text-xs font-semibold text-teal-700 hover:text-teal-800 flex items-center gap-1"
            >
              <span>See All ({complaints.length})</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {complaints.length === 0 ? (
          <div className="text-center py-12 border-2 border-dashed border-slate-200 rounded-xl bg-slate-50/50">
            <div className="w-12 h-12 rounded-full bg-teal-50 text-teal-600 flex items-center justify-center mx-auto mb-3">
              <FilePlus2 className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-bold text-slate-800">No complaints submitted yet</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1 mb-4">
              Have you spotted a pothole, uncollected garbage, or a broken streetlight in your neighborhood?
            </p>
            <button
              type="button"
              onClick={() => onOpenReportForm('pothole')}
              className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold transition"
            >
              Report a Problem Now
            </button>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {complaints.slice(0, 5).map((comp) => (
              <div
                key={comp.id}
                onClick={() => onSelectComplaint(comp)}
                className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-slate-50/80 -mx-2 px-2 rounded-xl cursor-pointer transition"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs font-bold text-teal-800 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
                      {comp.complaintId}
                    </span>
                    <span className={`text-[11px] px-2 py-0.5 rounded-full border font-semibold ${getStatusBadge(comp.status)}`}>
                      {comp.status}
                    </span>
                    <span className="text-[11px] text-slate-500 flex items-center gap-1">
                      <Tag className="w-3 h-3" />
                      {comp.category}
                    </span>
                  </div>
                  <h4 className="text-sm font-semibold text-slate-900 line-clamp-1">{comp.title}</h4>
                  <div className="flex items-center gap-3 text-xs text-slate-500">
                    <span className="flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5 text-slate-400" />
                      <span className="truncate max-w-[220px]">{comp.location}</span>
                    </span>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5 text-slate-400" />
                      {new Date(comp.createdAt).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2 self-end sm:self-center">
                  <button
                    type="button"
                    className="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 transition flex items-center gap-1"
                  >
                    <span>View Timeline</span>
                    <ArrowRight className="w-3 h-3" />
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
