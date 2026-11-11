import React, { useState, useEffect } from 'react';
import {
  X,
  MapPin,
  Calendar,
  User,
  Clock,
  Building,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Star,
  Send,
  Loader2,
  FileCheck,
  Camera,
  Layers,
  ArrowRight,
  ShieldCheck,
  Check
} from 'lucide-react';
import {
  Complaint,
  ComplaintUpdate,
  ComplaintStatus,
  ComplaintPriority,
  CitizenFeedback,
  Department
} from '../../types';
import { useAuth } from '../../context/AuthContext';
import {
  fetchComplaintUpdates,
  assignComplaint,
  updateComplaintStatus,
  reopenComplaint,
  submitCitizenFeedback,
  fetchFeedbackForComplaint,
  fetchDepartments
} from '../../services/complaintService';
import { SAMPLE_CIVIC_PHOTOS } from '../../utils/photoPresets';

interface ComplaintDetailsModalProps {
  complaint: Complaint;
  onClose: () => void;
  onComplaintUpdated: () => void;
}

export const ComplaintDetailsModal: React.FC<ComplaintDetailsModalProps> = ({
  complaint,
  onClose,
  onComplaintUpdated
}) => {
  const { activeRole, userProfile, currentUser } = useAuth();

  const [updates, setUpdates] = useState<ComplaintUpdate[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [feedback, setFeedback] = useState<CitizenFeedback | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Admin Assignment form states
  const [selectedDeptId, setSelectedDeptId] = useState<string>(complaint.departmentId || '');
  const [selectedDeptName, setSelectedDeptName] = useState<string>(complaint.departmentName || '');
  const [selectedPriority, setSelectedPriority] = useState<ComplaintPriority>(complaint.priority);
  const [adminNotes, setAdminNotes] = useState<string>('');
  const [isAssigning, setIsAssigning] = useState<boolean>(false);

  // Status transition states
  const [newStatus, setNewStatus] = useState<ComplaintStatus>(complaint.status);
  const [statusNote, setStatusNote] = useState<string>('');
  const [rejectionReason, setRejectionReason] = useState<string>('');
  const [resolutionProofUrl, setResolutionProofUrl] = useState<string>('');
  const [isUpdatingStatus, setIsUpdatingStatus] = useState<boolean>(false);

  // Reopen states (Citizen)
  const [reopenReasonText, setReopenReasonText] = useState<string>('');
  const [isReopening, setIsReopening] = useState<boolean>(false);
  const [showReopenBox, setShowReopenBox] = useState<boolean>(false);

  // Citizen Rating states
  const [rating, setRating] = useState<number>(5);
  const [ratingComment, setRatingComment] = useState<string>('');
  const [isSubmittingRating, setIsSubmittingRating] = useState<boolean>(false);
  const [ratingSuccess, setRatingSuccess] = useState<boolean>(false);

  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [hist, depts, fb] = await Promise.all([
        fetchComplaintUpdates(complaint.complaintId),
        fetchDepartments(),
        fetchFeedbackForComplaint(complaint.complaintId)
      ]);
      setUpdates(hist || []);
      setDepartments(depts || []);
      setFeedback(fb);

      if (complaint.departmentName && !selectedDeptName) {
        setSelectedDeptName(complaint.departmentName);
      }
    } catch (err) {
      console.warn('Error loading complaint modal details:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [complaint.id]);

  // Handle Admin Assignment
  const handleAssignDepartment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDeptName) {
      alert('Please select a department.');
      return;
    }
    setIsAssigning(true);
    try {
      const matchedDept = departments.find(d => d.name === selectedDeptName);
      const adminName = userProfile?.name || 'Administrator';
      const adminUid = userProfile?.uid || currentUser?.uid || 'admin-user';

      await assignComplaint({
        complaintDocId: complaint.id,
        complaintId: complaint.complaintId,
        citizenUserId: complaint.userId,
        departmentId: matchedDept?.departmentId || 'DEPT-MISC',
        departmentName: selectedDeptName,
        priority: selectedPriority,
        adminName,
        adminUid,
        notes: adminNotes || `Department assigned to ${selectedDeptName} with ${selectedPriority} priority.`
      });

      setActionMessage('Department successfully assigned.');
      onComplaintUpdated();
      await loadData();
    } catch (err: any) {
      alert('Error assigning department: ' + err.message);
    } finally {
      setIsAssigning(false);
    }
  };

  // Handle Status Update (Admin or Staff)
  const handleUpdateStatus = async (statusToSet: ComplaintStatus) => {
    if (statusToSet === 'Rejected' && !rejectionReason.trim()) {
      alert('A rejection reason is mandatory when rejecting a complaint.');
      return;
    }

    setIsUpdatingStatus(true);
    try {
      const updaterName = userProfile?.name || (activeRole === 'staff' ? 'Department Staff' : 'Administrator');
      const updaterUid = userProfile?.uid || currentUser?.uid || 'user-uid';

      await updateComplaintStatus({
        complaintDocId: complaint.id,
        complaintId: complaint.complaintId,
        citizenUserId: complaint.userId,
        previousStatus: complaint.status,
        newStatus: statusToSet,
        updatedBy: updaterName,
        updatedByUid: updaterUid,
        role: activeRole,
        note: statusNote || (statusToSet === 'In Progress' ? 'Work commenced on-site by field team.' : `Status updated to ${statusToSet}`),
        rejectionReason: statusToSet === 'Rejected' ? rejectionReason : undefined,
        resolutionProofUrl: statusToSet === 'Resolved' ? (resolutionProofUrl || SAMPLE_CIVIC_PHOTOS.resolvedRoad) : undefined,
        resolutionNotes: statusToSet === 'Resolved' ? (statusNote || 'Issue successfully rectified and inspected by municipal staff.') : undefined
      });

      setActionMessage(`Complaint marked as ${statusToSet}.`);
      onComplaintUpdated();
      await loadData();
    } catch (err: any) {
      alert('Error updating status: ' + err.message);
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  // Handle Reopening (Citizen)
  const handleReopenSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reopenReasonText.trim()) {
      alert('Please explain why this complaint is being reopened.');
      return;
    }
    setIsReopening(true);
    try {
      const cName = userProfile?.name || 'Citizen';
      const cUid = userProfile?.uid || currentUser?.uid || complaint.userId;

      await reopenComplaint({
        complaintDocId: complaint.id,
        complaintId: complaint.complaintId,
        citizenUserId: cUid,
        citizenName: cName,
        reopenReason: reopenReasonText.trim()
      });

      setShowReopenBox(false);
      setActionMessage('Complaint has been reopened and queued for department re-inspection.');
      onComplaintUpdated();
      await loadData();
    } catch (err: any) {
      alert('Error reopening complaint: ' + err.message);
    } finally {
      setIsReopening(false);
    }
  };

  // Handle Citizen Feedback
  const handleFeedbackSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmittingRating(true);
    try {
      const cUid = userProfile?.uid || currentUser?.uid || complaint.userId;
      await submitCitizenFeedback({
        complaintId: complaint.complaintId,
        userId: cUid,
        rating,
        comment: ratingComment
      });
      setRatingSuccess(true);
      await loadData();
    } catch (err: any) {
      alert('Error submitting feedback: ' + err.message);
    } finally {
      setIsSubmittingRating(false);
    }
  };

  // Status badge styling
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
        return 'bg-red-50 text-red-700 border-red-200 font-bold';
      case 'high':
        return 'bg-amber-50 text-amber-700 border-amber-200 font-semibold';
      case 'medium':
        return 'bg-sky-50 text-sky-700 border-sky-200';
      case 'low':
        return 'bg-slate-50 text-slate-600 border-slate-200';
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-4xl max-h-[92vh] flex flex-col overflow-hidden animate-fadeIn">
        {/* Header */}
        <div className="p-4 sm:p-6 bg-slate-900 text-white flex items-center justify-between shrink-0">
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="font-mono text-xs sm:text-sm font-bold bg-teal-500/20 text-teal-300 px-2.5 py-0.5 rounded border border-teal-500/40">
                {complaint.complaintId}
              </span>
              <span className={`text-xs px-2.5 py-0.5 rounded-full border font-semibold ${getStatusBadge(complaint.status)}`}>
                {complaint.status}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded border capitalize ${getPriorityBadge(complaint.priority)}`}>
                Priority: {complaint.priority}
              </span>
            </div>
            <h2 className="text-base sm:text-lg font-bold text-white mt-1.5 line-clamp-1">{complaint.title}</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-4 sm:p-6 overflow-y-auto space-y-6">
          {actionMessage && (
            <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-xs sm:text-sm flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{actionMessage}</span>
            </div>
          )}

          {/* Quick Info Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs">
              <span className="text-slate-400 block font-medium">Category</span>
              <span className="font-semibold text-slate-800 text-sm mt-0.5 block">{complaint.category}</span>
            </div>
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs">
              <span className="text-slate-400 block font-medium">Assigned Department</span>
              <span className="font-semibold text-slate-800 text-sm mt-0.5 block">
                {complaint.departmentName || 'Not Assigned Yet'}
              </span>
            </div>
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs">
              <span className="text-slate-400 block font-medium">Location</span>
              <span className="font-semibold text-slate-800 text-xs mt-0.5 block line-clamp-1">
                {complaint.location}
              </span>
              {complaint.landmark && (
                <span className="text-[11px] text-slate-500 block truncate">Near: {complaint.landmark}</span>
              )}
            </div>
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs">
              <span className="text-slate-400 block font-medium">Submitted On</span>
              <span className="font-semibold text-slate-800 text-xs mt-0.5 block">
                {new Date(complaint.createdAt).toLocaleDateString(undefined, {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit'
                })}
              </span>
              <span className="text-[11px] text-slate-500 block">By: {complaint.citizenName}</span>
            </div>
          </div>

          {/* Problem Description & Evidence Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-3">
              <div className="p-4 rounded-xl bg-slate-50/70 border border-slate-200">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1.5">Citizen Description</h4>
                <p className="text-xs sm:text-sm text-slate-700 whitespace-pre-line leading-relaxed">
                  {complaint.description}
                </p>
              </div>

              {complaint.aiSummary && (
                <div className="p-3 rounded-xl bg-teal-50/60 border border-teal-200 text-xs">
                  <div className="flex items-center gap-1.5 font-bold text-teal-900 mb-1">
                    <ShieldCheck className="w-3.5 h-3.5 text-teal-600" />
                    <span>Gemini AI Summary & Classification</span>
                  </div>
                  <p className="text-slate-700">{complaint.aiSummary}</p>
                </div>
              )}

              {complaint.rejectionReason && (
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs">
                  <span className="font-bold text-rose-800 block mb-0.5">Rejection Reason:</span>
                  <p className="text-rose-700">{complaint.rejectionReason}</p>
                </div>
              )}

              {complaint.reopenReason && (
                <div className="p-3 rounded-xl bg-orange-50 border border-orange-200 text-xs">
                  <span className="font-bold text-orange-800 block mb-0.5">Citizen Reopen Reason:</span>
                  <p className="text-orange-700">{complaint.reopenReason}</p>
                </div>
              )}
            </div>

            {/* Images (Initial Evidence + Resolution Proof) */}
            <div className="space-y-3">
              {complaint.imageUrl ? (
                <div className="rounded-xl overflow-hidden border border-slate-200 bg-slate-900">
                  <div className="px-3 py-1.5 bg-slate-800 text-[11px] font-semibold text-slate-300 flex items-center justify-between">
                    <span>Initial Citizen Evidence</span>
                    <Camera className="w-3.5 h-3.5" />
                  </div>
                  <img src={complaint.imageUrl} alt="Initial Evidence" className="w-full h-44 object-cover" />
                </div>
              ) : (
                <div className="h-28 rounded-xl border border-dashed border-slate-300 flex items-center justify-center text-xs text-slate-400">
                  No initial photograph submitted
                </div>
              )}

              {complaint.resolutionProofUrl && (
                <div className="rounded-xl overflow-hidden border border-emerald-300 bg-slate-900">
                  <div className="px-3 py-1.5 bg-emerald-800 text-[11px] font-semibold text-emerald-100 flex items-center justify-between">
                    <span>Department Resolution Proof</span>
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  </div>
                  <img src={complaint.resolutionProofUrl} alt="Resolution Proof" className="w-full h-44 object-cover" />
                  {complaint.resolutionNotes && (
                    <div className="p-2.5 bg-white text-xs text-slate-700 border-t border-slate-200">
                      <strong>Department Note:</strong> {complaint.resolutionNotes}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* AUDIT TIMELINE (Visual Progress History) */}
          <div className="p-4 rounded-xl bg-white border border-slate-200">
            <div className="flex items-center gap-2 mb-4">
              <Clock className="w-4 h-4 text-teal-600" />
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wide">Status History & Audit Trail</h3>
            </div>

            {loading ? (
              <div className="py-6 text-center text-xs text-slate-400">
                <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-teal-600" />
                Loading timeline records...
              </div>
            ) : updates.length === 0 ? (
              <p className="text-xs text-slate-400">No status updates recorded yet.</p>
            ) : (
              <div className="relative pl-6 space-y-4 border-l-2 border-teal-500/40 ml-2">
                {updates.map((upd, idx) => (
                  <div key={upd.id || idx} className="relative">
                    {/* Timeline bullet */}
                    <div className="absolute -left-[31px] top-1 w-3.5 h-3.5 rounded-full bg-teal-600 border-2 border-white shadow-xs" />
                    <div className="flex items-center justify-between gap-2">
                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${getStatusBadge(upd.newStatus as ComplaintStatus)}`}>
                        {upd.newStatus}
                      </span>
                      <span className="text-[11px] text-slate-400">
                        {new Date(upd.timestamp).toLocaleDateString([], {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </span>
                    </div>
                    <p className="text-xs text-slate-700 mt-1">{upd.note}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      Updated by <strong className="text-slate-600">{upd.updatedBy}</strong> ({upd.role})
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* CITIZEN ACTIONS: Reopen Complaint or Submit Feedback */}
          {activeRole === 'citizen' && (
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">Citizen Actions</h3>

              {complaint.status === 'Resolved' && (
                <div className="space-y-4">
                  {/* Reopen Trigger */}
                  {!showReopenBox ? (
                    <div className="flex items-center justify-between p-3 bg-white rounded-lg border border-slate-200">
                      <div>
                        <p className="text-xs font-semibold text-slate-800">Has the issue not been satisfactorily resolved?</p>
                        <p className="text-[11px] text-slate-500">You have the right to reopen the grievance with a reason.</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setShowReopenBox(true)}
                        className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-orange-100 hover:bg-orange-200 text-orange-800 transition"
                      >
                        Reopen Grievance
                      </button>
                    </div>
                  ) : (
                    <form onSubmit={handleReopenSubmit} className="p-3 bg-orange-50/70 border border-orange-200 rounded-lg space-y-2">
                      <label className="block text-xs font-bold text-orange-900">
                        Reason for Reopening <span className="text-red-500">*</span>
                      </label>
                      <textarea
                        rows={2}
                        value={reopenReasonText}
                        onChange={(e) => setReopenReasonText(e.target.value)}
                        placeholder="Explain why the problem persists or what was left incomplete..."
                        required
                        className="w-full p-2 text-xs border border-orange-300 rounded-lg bg-white"
                      />
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setShowReopenBox(false)}
                          className="px-3 py-1 text-xs text-slate-600 hover:text-slate-800"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          disabled={isReopening}
                          className="px-3 py-1 text-xs font-semibold rounded bg-orange-600 text-white hover:bg-orange-700 transition"
                        >
                          {isReopening ? 'Submitting...' : 'Confirm Reopen'}
                        </button>
                      </div>
                    </form>
                  )}

                  {/* Citizen Satisfaction Feedback */}
                  <div className="p-3.5 bg-white rounded-lg border border-slate-200">
                    <p className="text-xs font-bold text-slate-800 mb-1">Citizen Satisfaction Rating</p>
                    {feedback ? (
                      <div className="text-xs text-slate-600 space-y-1">
                        <div className="flex items-center gap-1 text-amber-500 font-bold">
                          {[1, 2, 3, 4, 5].map((star) => (
                            <Star
                              key={star}
                              className={`w-4 h-4 ${star <= feedback.rating ? 'fill-amber-400 text-amber-400' : 'text-slate-300'}`}
                            />
                          ))}
                          <span className="ml-1 text-slate-700">{feedback.rating}/5</span>
                        </div>
                        {feedback.comment && <p className="italic">"{feedback.comment}"</p>}
                        <p className="text-[10px] text-slate-400">Feedback submitted on {new Date(feedback.createdAt).toLocaleDateString()}</p>
                      </div>
                    ) : (
                      <form onSubmit={handleFeedbackSubmit} className="space-y-2.5 mt-2">
                        <div className="flex items-center gap-1.5">
                          {[1, 2, 3, 4, 5].map((st) => (
                            <button
                              key={st}
                              type="button"
                              onClick={() => setRating(st)}
                              className="p-1 hover:scale-110 transition"
                            >
                              <Star
                                className={`w-5 h-5 ${st <= rating ? 'fill-amber-400 text-amber-400' : 'text-slate-300'}`}
                              />
                            </button>
                          ))}
                          <span className="text-xs font-semibold text-slate-700 ml-2">{rating} Stars</span>
                        </div>
                        <input
                          type="text"
                          value={ratingComment}
                          onChange={(e) => setRatingComment(e.target.value)}
                          placeholder="Optional feedback comment on resolution speed and quality..."
                          className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300"
                        />
                        <button
                          type="submit"
                          disabled={isSubmittingRating}
                          className="px-3 py-1.5 bg-teal-600 hover:bg-teal-500 text-white rounded-lg text-xs font-semibold shadow-xs"
                        >
                          {isSubmittingRating ? 'Saving...' : 'Submit Satisfaction Rating'}
                        </button>
                      </form>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ADMIN ACTION PANEL: Assign Department & Set Priority */}
          {activeRole === 'admin' && (
            <div className="p-4 rounded-xl bg-slate-900 text-white space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Building className="w-4 h-4 text-teal-400" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-teal-300">
                    Administrator Controls: Department Assignment & Priority
                  </h3>
                </div>
              </div>

              <form onSubmit={handleAssignDepartment} className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                    Assign Municipal Department
                  </label>
                  <select
                    value={selectedDeptName}
                    onChange={(e) => setSelectedDeptName(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white text-xs"
                  >
                    <option value="">Select Department</option>
                    {departments.map((dept) => (
                      <option key={dept.id || dept.departmentId} value={dept.name}>
                        {dept.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                    Set Urgency Priority
                  </label>
                  <select
                    value={selectedPriority}
                    onChange={(e) => setSelectedPriority(e.target.value as ComplaintPriority)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white text-xs capitalize"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                  </select>
                </div>

                <div className="flex items-end">
                  <button
                    type="submit"
                    disabled={isAssigning || !selectedDeptName}
                    className="w-full py-2 px-3 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold shadow-sm transition disabled:opacity-50 flex items-center justify-center gap-1.5"
                  >
                    {isAssigning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Building className="w-3.5 h-3.5" />}
                    <span>Assign & Notify</span>
                  </button>
                </div>
              </form>

              {/* Admin direct status buttons */}
              <div className="pt-3 border-t border-slate-800 flex flex-wrap items-center gap-2">
                <span className="text-[11px] text-slate-400">Quick Status Transition:</span>
                <button
                  type="button"
                  onClick={() => handleUpdateStatus('Under Review')}
                  className="px-2.5 py-1 text-xs rounded bg-slate-800 hover:bg-purple-900/60 text-purple-300 border border-purple-800/40"
                >
                  Mark Under Review
                </button>
                <button
                  type="button"
                  onClick={() => handleUpdateStatus('In Progress')}
                  className="px-2.5 py-1 text-xs rounded bg-slate-800 hover:bg-amber-900/60 text-amber-300 border border-amber-800/40"
                >
                  Mark In Progress
                </button>
                <button
                  type="button"
                  onClick={() => handleUpdateStatus('Resolved')}
                  className="px-2.5 py-1 text-xs rounded bg-slate-800 hover:bg-emerald-900/60 text-emerald-300 border border-emerald-800/40"
                >
                  Mark Resolved
                </button>
              </div>
            </div>
          )}

          {/* STAFF ACTION PANEL: Progress Update & Proof Upload */}
          {activeRole === 'staff' && (
            <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/30 space-y-4">
              <div className="flex items-center gap-2">
                <FileCheck className="w-4 h-4 text-emerald-400" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-300">
                  Field Staff Execution ({complaint.departmentName || 'Assigned Department'})
                </h3>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Start Work Button */}
                <button
                  type="button"
                  onClick={() => handleUpdateStatus('In Progress')}
                  disabled={complaint.status === 'In Progress' || complaint.status === 'Resolved'}
                  className="p-3 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-300 text-left transition disabled:opacity-40"
                >
                  <p className="text-xs font-bold">1. Start On-Site Work</p>
                  <p className="text-[11px] text-slate-300 mt-0.5">Transition status to 'In Progress'</p>
                </button>

                {/* Mark as Resolved Button with proof */}
                <button
                  type="button"
                  onClick={() => handleUpdateStatus('Resolved')}
                  disabled={complaint.status === 'Resolved'}
                  className="p-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-left transition shadow-sm disabled:opacity-40"
                >
                  <p className="text-xs font-bold">2. Mark Work Completed & Resolved</p>
                  <p className="text-[11px] text-emerald-100 mt-0.5">Attach repair proof photo & finalize</p>
                </button>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Staff Progress Remark / Notes:
                </label>
                <input
                  type="text"
                  value={statusNote}
                  onChange={(e) => setStatusNote(e.target.value)}
                  placeholder="e.g. Bitumen patch applied, road leveled and rolled. Reopened for normal traffic."
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white dark:bg-slate-900"
                />
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-100 border-t border-slate-200 flex justify-end shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs sm:text-sm font-semibold transition"
          >
            Close Details
          </button>
        </div>
      </div>
    </div>
  );
};
