import React from 'react';
import { AlertTriangle, Inbox, Loader2, RefreshCw } from 'lucide-react';

/** Consistent loading state with accessible text. */
export const Loading = ({ label = 'Loading…', className = '' }) => (
  <div className={`flex flex-col items-center justify-center py-16 text-gray-500 ${className}`} role="status" aria-live="polite">
    <Loader2 className="w-7 h-7 animate-spin text-carbon-500 mb-3" />
    <p className="text-sm">{label}</p>
  </div>
);

/**
 * Error state with details + Retry. Uses ApiError fields when present so the
 * backend's actionable message (e.g. NEBIUS_API_KEY missing) is shown as-is.
 */
export const ErrorState = ({ error, onRetry, label = 'Something went wrong', compact = false }) => {
  if (!error) return null;
  const code = error.code || 'ERROR';
  const message = error.message || 'Unexpected error.';
  const details = Array.isArray(error.details) && error.details.length ? error.details : null;

  return (
    <div
      role="alert"
      className={`bg-red-950/30 border border-red-900/50 rounded-2xl ${compact ? 'p-4' : 'p-6'} flex flex-col items-start gap-3`}
    >
      <div className="flex items-start gap-3 w-full">
        <div className="p-2 bg-red-500/10 rounded-lg shrink-0">
          <AlertTriangle size={18} className="text-red-400" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-red-300 text-sm">{label}</p>
          <p className="text-sm text-red-200/80 mt-1 break-words">{message}</p>
          <p className="text-[11px] font-mono text-red-400/60 mt-1">{code}{error.status ? ` · HTTP ${error.status}` : ''}</p>
          {details && (
            <ul className="mt-2 space-y-1 text-xs text-red-300/70 list-disc list-inside">
              {details.map((d, i) => <li key={i}>{d}</li>)}
            </ul>
          )}
        </div>
        {onRetry && (
          <button
            onClick={onRetry}
            className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-red-500/15 hover:bg-red-500/25 text-red-300 border border-red-500/30 rounded-lg transition-colors"
          >
            <RefreshCw size={13} /> Retry
          </button>
        )}
      </div>
    </div>
  );
};

/** Friendly empty state with optional action. */
export const EmptyState = ({ icon: Icon = Inbox, title, description, action, onAction }) => (
  <div className="text-center py-14 px-6 bg-dark-800/30 rounded-2xl border border-dashed border-carbon-800/40">
    <div className="w-14 h-14 bg-carbon-900/50 rounded-full flex items-center justify-center mx-auto mb-4">
      <Icon className="w-7 h-7 text-carbon-600" />
    </div>
    <h3 className="text-lg font-bold text-white mb-2">{title}</h3>
    {description && <p className="text-sm text-gray-400 max-w-md mx-auto">{description}</p>}
    {action && (
      <button onClick={onAction} className="btn-primary mt-5 text-sm py-2.5">{action}</button>
    )}
  </div>
);
