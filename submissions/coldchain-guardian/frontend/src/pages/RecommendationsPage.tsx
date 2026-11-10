import { useEffect, useState, useCallback, useRef } from 'react';
import { api, Recommendation } from '../api';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import Badge from '../components/SeverityBadge';
import { Check, X, RefreshCw } from 'lucide-react';

export default function RecommendationsPage() {
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [approving, setApproving] = useState<number | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = useCallback((message: string, type: 'success' | 'error') => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ message, type });
    // Success auto-dismisses; errors persist until the next action so they can be read.
    toastTimer.current = type === 'success' ? setTimeout(() => setToast(null), 4000) : null;
  }, []);

  useEffect(() => () => { if (toastTimer.current) clearTimeout(toastTimer.current); }, []);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setRecs(await api.getRecommendations()); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'Failed to load'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const approve = async (recId: number, status: 'APPROVED' | 'REJECTED') => {
    if (!window.confirm(`${status === 'APPROVED' ? 'Approve' : 'Reject'} this recommendation?`)) return;
    setApproving(recId);
    try {
      await api.approveRecommendation(recId, status);
      showToast(`Recommendation #${recId} ${status.toLowerCase()}.`, 'success');
      load();
    } catch (e: unknown) {
      showToast(`Failed: ${e instanceof Error ? e.message : 'Unknown error'}`, 'error');
    } finally {
      setApproving(null);
    }
  };

  if (loading) return <LoadingSpinner text="Loading recommendations..." />;
  if (error) return <div className="p-6"><ErrorMessage message={error} onRetry={load} /></div>;

  const pendingCount = recs.filter(r => !r.approval_status || r.approval_status === 'PENDING').length;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Recommendations</h1>
          <p className="text-slate-400 text-sm mt-1">
            {recs.length} recommendations · {pendingCount} pending approval
          </p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 px-4 py-2 bg-navy-700 hover:bg-navy-600 text-white rounded-lg text-sm font-medium transition-colors border border-navy-600"
        >
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {toast && (
        <div className={`rounded-lg p-3 text-sm border flex items-center justify-between ${toast.type === 'error' ? 'bg-red-900/20 border-red-700/40 text-red-400' : 'bg-teal-900/20 border-teal-700/40 text-teal-400'}`}>
          <span>{toast.message}</span>
          <button onClick={() => setToast(null)} className="ml-3 opacity-70 hover:opacity-100" aria-label="Dismiss">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      <div className="space-y-3">
        {recs.length === 0 ? (
          <div className="bg-navy-800 border border-navy-600 rounded-xl p-12 text-center text-slate-500">
            No recommendations yet
          </div>
        ) : recs.map(rec => {
          const isPending = !rec.approval_status || rec.approval_status === 'PENDING';
          return (
            <div key={rec.recommendation_id} className="bg-navy-800 border border-navy-600 rounded-xl p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <span className="text-white font-semibold text-sm">#{rec.recommendation_id}</span>
                    <Badge label={`Priority ${rec.priority}`} />
                    <Badge label={rec.approval_status || 'PENDING'} />
                  </div>
                  <p className="text-white text-sm font-medium">{rec.action}</p>
                  <p className="text-slate-400 text-sm mt-1">{rec.justification}</p>
                  <p className="text-slate-500 text-xs mt-2">
                    Incident #{rec.incident_id} · {rec.created_at ? new Date(rec.created_at).toLocaleString() : '—'}
                  </p>
                </div>
                {isPending && (
                  <div className="flex gap-2 flex-shrink-0">
                    <button
                      onClick={() => approve(rec.recommendation_id, 'APPROVED')}
                      disabled={approving === rec.recommendation_id}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-green-700/30 hover:bg-green-700/50 text-green-400 border border-green-700/50 rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
                    >
                      <Check className="w-3 h-3" /> Approve
                    </button>
                    <button
                      onClick={() => approve(rec.recommendation_id, 'REJECTED')}
                      disabled={approving === rec.recommendation_id}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-red-700/30 hover:bg-red-700/50 text-red-400 border border-red-700/50 rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
                    >
                      <X className="w-3 h-3" /> Reject
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
