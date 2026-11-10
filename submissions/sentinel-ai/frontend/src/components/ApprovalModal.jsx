import React, { useState } from 'react';
import { ShieldCheck, X, AlertTriangle, Lock, CheckCircle2, XCircle } from 'lucide-react';

export default function ApprovalModal({ isOpen, onClose, recommendation, onActionSuccess }) {
  const [adminName, setAdminName] = useState('Cyber Commander Administrator');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen || !recommendation) return null;

  const handleAction = async (actionType) => {
    setSubmitting(true);
    setError(null);
    try {
      await onActionSuccess(recommendation.recommendation_id, actionType, adminName, notes);
      onClose();
    } catch (err) {
      setError(err.message || 'Action failed to execute');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[#0b1528] border border-[#2b4c80] rounded-xl max-w-lg w-full p-6 shadow-2xl relative glow-blue">
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center space-x-3 mb-4">
          <div className="p-2.5 rounded-lg bg-amber-950/80 border border-amber-600/80 text-amber-400">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h3 className="font-tech text-lg font-bold text-white uppercase tracking-wide">
              Human-in-the-Loop Authorization
            </h3>
            <p className="text-xs text-slate-400 font-mono-code">
              ACTION ID: {recommendation.recommendation_id}
            </p>
          </div>
        </div>

        <div className="p-3.5 rounded-lg bg-[#070d18] border border-[#1a2f55] mb-4 space-y-2 text-xs">
          <div className="flex justify-between">
            <span className="text-slate-400">Defense Action:</span>
            <span className="font-mono-code font-bold text-cyan-400">{recommendation.action_type}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Target User/Asset:</span>
            <span className="font-mono-code text-slate-200">{recommendation.target_user_name || recommendation.target || 'Defence Perimeter'}</span>
          </div>
          <div>
            <span className="text-slate-400 block mb-1">Playbook Description:</span>
            <p className="text-slate-200 bg-[#0b1528] p-2 rounded border border-[#152642] leading-relaxed">
              {recommendation.description}
            </p>
          </div>
        </div>

        <div className="space-y-3 mb-6 text-xs">
          <div>
            <label className="block text-slate-300 font-medium mb-1">Authorizing Commander Name</label>
            <input 
              type="text" 
              value={adminName}
              onChange={(e) => setAdminName(e.target.value)}
              className="w-full bg-[#070d18] border border-[#1a2f55] rounded px-3 py-2 text-slate-100 font-mono-code focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-slate-300 font-medium mb-1">Operational Justification / Notes</label>
            <textarea 
              rows="2"
              placeholder="e.g. Verified multi-event compromise. Account locked pending physical debrief."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full bg-[#070d18] border border-[#1a2f55] rounded px-3 py-2 text-slate-100 text-xs focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        {error && (
          <div className="p-2.5 rounded bg-rose-950/60 border border-rose-800 text-rose-300 text-xs mb-4">
            {error}
          </div>
        )}

        <div className="flex items-center space-x-3">
          <button
            onClick={() => handleAction('APPROVE')}
            disabled={submitting}
            className="flex-1 flex items-center justify-center space-x-2 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition-all shadow-lg shadow-emerald-900/30"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>{submitting ? 'Executing...' : 'AUTHORIZE & EXECUTE'}</span>
          </button>
          <button
            onClick={() => handleAction('REJECT')}
            disabled={submitting}
            className="flex-1 flex items-center justify-center space-x-2 px-4 py-2.5 rounded-lg bg-rose-950 hover:bg-rose-900 text-rose-300 border border-rose-800/60 font-semibold text-xs transition-all"
          >
            <XCircle className="w-4 h-4" />
            <span>REJECT RECOMMENDATION</span>
          </button>
        </div>
      </div>
    </div>
  );
}

