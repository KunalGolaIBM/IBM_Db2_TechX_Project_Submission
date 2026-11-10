import React, { useEffect, useState } from 'react';
import { CheckCircle2, XCircle, ShieldCheck, Lock, History } from 'lucide-react';
import { SentinelApi } from '../services/api';
import { ApprovalRequest } from '../types';

export const Approvals: React.FC = () => {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);

  const fetchApprovals = async () => {
    try {
      const res = await SentinelApi.getApprovals();
      setApprovals(res.approvals || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApprovals();
  }, []);

  const handleApprove = async (id: string) => {
    try {
      const res = await SentinelApi.approveAction(id, 'Security DBA Admin');
      setMessage(res.message);
      fetchApprovals();
    } catch (err) {
      console.error(err);
    }
  };

  const handleReject = async (id: string) => {
    try {
      const res = await SentinelApi.rejectAction(id, 'Security DBA Admin', 'False positive operational exception');
      setMessage(res.message);
      fetchApprovals();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-white">Human-in-the-Loop Governance & Approvals</h2>
        <p className="text-xs text-slate-400 mt-1">
          Mandatory approval gates for sensitive database remediation actions (Zero-Autonomous-Destruction Policy)
        </p>
      </div>

      {message && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-xs text-emerald-400 flex items-center justify-between">
          <span>{message}</span>
          <button onClick={() => setMessage(null)} className="text-emerald-500 font-bold">✕</button>
        </div>
      )}

      <div className="space-y-4">
        {loading ? (
          <div className="py-12 text-center text-cyan-400 text-xs">Loading approval requests...</div>
        ) : approvals.length === 0 ? (
          <div className="bg-[#132238] border border-[#1E3A5F] rounded-2xl p-12 text-center text-slate-500 text-sm">
            No containment actions currently pending review.
          </div>
        ) : (
          approvals.map((app) => (
            <div
              key={app.approval_id}
              className="bg-[#132238] border border-[#1E3A5F] rounded-2xl p-6 shadow-lg flex flex-col md:flex-row items-start md:items-center justify-between gap-6"
            >
              <div className="space-y-2 max-w-3xl">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono font-bold text-cyan-400">{app.approval_id}</span>
                  <span className="text-xs text-slate-400">• Incident: {app.incident_id}</span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                    app.approval_status === 'APPROVED'
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                      : app.approval_status === 'REJECTED'
                      ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                      : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                  }`}>
                    {app.approval_status}
                  </span>
                </div>

                <h3 className="text-base font-bold text-white">{app.proposed_action}</h3>
                <p className="text-xs text-slate-300">
                  Requested By: <strong className="text-cyan-400 font-mono">{app.requested_by}</strong>
                </p>

                {app.audit_notes && (
                  <p className="text-xs text-slate-400 bg-[#0D182E] p-2.5 rounded-lg border border-[#1E3A5F]/40 font-mono">
                    Notes: {app.audit_notes} ({app.reviewer} @ {app.reviewed_at})
                  </p>
                )}
              </div>

              {app.approval_status === 'PENDING' ? (
                <div className="flex items-center gap-3 shrink-0">
                  <button
                    onClick={() => handleReject(app.approval_id)}
                    className="flex items-center gap-1.5 px-3.5 py-2 bg-[#1C2E4A] hover:bg-rose-600/30 text-rose-400 border border-rose-500/30 rounded-xl text-xs font-semibold transition-all"
                  >
                    <XCircle className="w-3.5 h-3.5" />
                    Reject
                  </button>

                  <button
                    onClick={() => handleApprove(app.approval_id)}
                    className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-emerald-500/20 transition-all"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Approve & Execute
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-xs text-slate-400 shrink-0">
                  <History className="w-4 h-4 text-emerald-400" />
                  <span>Decision committed to Db2 audit trail</span>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
