import React, { useState } from 'react';
import { ListFilter, Check, X, ShieldAlert, CheckCircle2, AlertCircle } from 'lucide-react';
import type { RecallAction } from '../../services/api';

interface ResponseQueueCardProps {
  actions: RecallAction[];
  onDecision: (actionId: string, decision: 'APPROVED' | 'REJECTED') => Promise<void>;
  isProcessing?: boolean;
}

export const ResponseQueueCard: React.FC<ResponseQueueCardProps> = ({
  actions,
  onDecision,
  isProcessing,
}) => {
  const [confirmModal, setConfirmModal] = useState<{
    action: RecallAction;
    decision: 'APPROVED' | 'REJECTED';
  } | null>(null);

  const approvedCount = actions.filter((a) => a.status === 'APPROVED').length;
  const rejectedCount = actions.filter((a) => a.status === 'REJECTED').length;
  const proposedCount = actions.filter((a) => a.status === 'PROPOSED').length;

  const handleConfirm = async () => {
    if (!confirmModal) return;
    await onDecision(confirmModal.action.action_id, confirmModal.decision);
    setConfirmModal(null);
  };

  return (
    <div className="bento-opaque-card p-6 flex flex-col justify-between gap-4 h-full">
      <div>
        {/* Header Label & Dynamic Approval Status */}
        <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-white/[0.08]">
          <div className="flex items-center space-x-2">
            <ListFilter className="w-3.5 h-3.5 text-[#23cad2]" />
            <span className="text-[11px] font-mono font-bold tracking-wider uppercase text-white/70">
              RESPONSE QUEUE
            </span>
          </div>

          {proposedCount > 0 ? (
            <span className="inline-flex items-center gap-1.5 text-[10px] font-mono font-bold uppercase px-2.5 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30">
              <ShieldAlert className="w-3 h-3 text-amber-400" />
              {approvedCount > 0
                ? `${approvedCount} APPROVED / ${proposedCount} PENDING REVIEW`
                : `${proposedCount} REQUIRES HUMAN APPROVAL`}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-[10px] font-mono font-bold uppercase px-2.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              ALL DECISIONS RECORDED ({approvedCount} APPROVED{rejectedCount > 0 ? `, ${rejectedCount} REJECTED` : ''})
            </span>
          )}
        </div>

        {/* Action Items List */}
        <div className="mt-3 space-y-2">
          {actions.map((act) => {
            const isApproved = act.status === 'APPROVED';
            const isRejected = act.status === 'REJECTED';
            const isProposed = act.status === 'PROPOSED';

            return (
              <div
                key={act.action_id}
                className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.06] hover:border-white/[0.12] transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-2"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs font-bold text-white tracking-wide">
                      {act.action_id}
                    </span>
                    <span className="text-[9.5px] font-mono uppercase px-1.5 py-0.2 rounded bg-white/[0.06] text-white/60">
                      {act.action_type.replace('_', ' ')}
                    </span>
                    <span
                      className={`text-[9px] font-mono uppercase px-1.5 py-0.2 rounded font-bold ${
                        isApproved
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                          : isRejected
                          ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                          : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                      }`}
                    >
                      {act.status}
                    </span>
                  </div>
                  <p className="text-xs text-white/75 line-clamp-1 sm:line-clamp-2 mt-1 leading-snug">
                    {act.action_description}
                  </p>
                  {isApproved && act.approved_by && (
                    <span className="text-[10px] font-mono text-emerald-300/60 block mt-0.5">
                      ✓ Confirmed by {act.approved_by}
                    </span>
                  )}
                </div>

                {/* Approve / Reject Controls */}
                <div className="flex items-center gap-1.5 self-end sm:self-auto shrink-0">
                  {isProposed ? (
                    <>
                      <button
                        onClick={() => setConfirmModal({ action: act, decision: 'APPROVED' })}
                        disabled={isProcessing}
                        className="px-2.5 py-1 rounded bg-emerald-600/20 hover:bg-emerald-600/40 border border-emerald-500/40 text-emerald-300 text-[11px] font-semibold flex items-center gap-1 transition-all active:scale-95 cursor-pointer disabled:opacity-40"
                      >
                        <Check className="w-3 h-3" />
                        <span>Approve</span>
                      </button>
                      <button
                        onClick={() => setConfirmModal({ action: act, decision: 'REJECTED' })}
                        disabled={isProcessing}
                        className="px-2.5 py-1 rounded bg-red-600/20 hover:bg-red-600/40 border border-red-500/40 text-red-300 text-[11px] font-semibold flex items-center gap-1 transition-all active:scale-95 cursor-pointer disabled:opacity-40"
                      >
                        <X className="w-3 h-3" />
                        <span>Reject</span>
                      </button>
                    </>
                  ) : (
                    <span className="text-[10px] font-mono text-white/40">
                      Logged in Db2
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Safety Gate Footer */}
      <div className="pt-2.5 border-t border-white/[0.06] text-[10px] text-white/40 font-mono">
        Safety Gate: All actions require human operator confirmation before committing database mutations.
      </div>

      {/* Confirmation Modal */}
      {confirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#171717] border border-white/20 rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <AlertCircle
                className={`w-5 h-5 ${
                  confirmModal.decision === 'APPROVED' ? 'text-emerald-400' : 'text-red-400'
                }`}
              />
              <h3 className="text-base font-bold text-white">
                Confirm Human {confirmModal.decision === 'APPROVED' ? 'Approval' : 'Rejection'}
              </h3>
            </div>

            <p className="text-xs text-white/80 leading-relaxed">
              Are you sure you want to mark action{' '}
              <strong className="text-white font-mono">{confirmModal.action.action_id}</strong> as{' '}
              <strong
                className={
                  confirmModal.decision === 'APPROVED' ? 'text-emerald-300 font-bold' : 'text-red-300 font-bold'
                }
              >
                {confirmModal.decision}
              </strong>
              ? This action will be committed to <span className="font-mono text-white/90">IBM Db2</span> and written into the immutable audit ledger.
            </p>

            <div className="pt-2 flex justify-end gap-2.5 font-mono text-xs">
              <button
                onClick={() => setConfirmModal(null)}
                className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/15 text-white cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                disabled={isProcessing}
                className={`px-4 py-2 rounded-lg font-bold cursor-pointer transition-all ${
                  confirmModal.decision === 'APPROVED'
                    ? 'bg-emerald-500 hover:bg-emerald-400 text-black'
                    : 'bg-red-500 hover:bg-red-400 text-white'
                }`}
              >
                {isProcessing ? 'Committing...' : `Confirm ${confirmModal.decision}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
