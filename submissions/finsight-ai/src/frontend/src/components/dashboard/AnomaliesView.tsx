import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  XCircle,
  TrendingUp,
  Filter,
  RefreshCw,
  Loader2,
  Info,
  Calendar,
  Tag,
  ChevronRight,
  Sparkles,
  ShieldCheck,
  X
} from 'lucide-react';
import {
  apiClient,
  AnomalyItem,
  AnomalyExplainResponse
} from '../../api/client';
import { useAuth } from '../../context/AuthContext';

export const AnomaliesView: React.FC = () => {
  const { csrfToken } = useAuth();
  const [anomalies, setAnomalies] = useState<AnomalyItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [typeFilter, setTypeFilter] = useState<string>('ALL');

  // Selected Alert for Explanation Modal
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);
  const [explanation, setExplanation] = useState<AnomalyExplainResponse | null>(null);
  const [isLoadingExplanation, setIsLoadingExplanation] = useState(false);
  const [explanationError, setExplanationError] = useState<string | null>(null);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState<string | null>(null);

  const formatINR = (val?: number | null) => {
    if (val === null || val === undefined) return 'N/A';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(val);
  };

  const loadAnomalies = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params: { status?: string; severity?: string; alert_type?: string } = {};
      if (statusFilter !== 'ALL') params.status = statusFilter;
      if (severityFilter !== 'ALL') params.severity = severityFilter;
      if (typeFilter !== 'ALL') params.alert_type = typeFilter;

      const resp = await apiClient.anomalies.getAnomalies(params);
      setAnomalies(resp.anomalies || []);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch anomaly alerts from IBM Db2.');
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter, severityFilter, typeFilter]);

  useEffect(() => {
    loadAnomalies();
  }, [loadAnomalies]);

  const handleOpenDetail = async (alertId: string) => {
    setSelectedAlertId(alertId);
    setExplanation(null);
    setIsLoadingExplanation(true);
    setExplanationError(null);
    try {
      const resp = await apiClient.anomalies.explainAnomaly(alertId, csrfToken);
      setExplanation(resp);
    } catch (err: any) {
      setExplanationError(err?.message || 'Failed to generate explainable breakdown.');
    } finally {
      setIsLoadingExplanation(false);
    }
  };

  const handleUpdateStatus = async (alertId: string, newStatus: string) => {
    setIsUpdatingStatus(alertId);
    try {
      await apiClient.anomalies.updateStatus(alertId, newStatus, csrfToken);
      // Optimistically update list
      setAnomalies((prev) =>
        prev.map((a) => (a.alert_id === alertId ? { ...a, status: newStatus } : a))
      );
      // If modal is open for this alert, update it
      if (explanation && explanation.alert_id === alertId) {
        setExplanation({ ...explanation, status: newStatus });
      }
    } catch (err: any) {
      alert(`Failed to update status: ${err?.message || 'Unknown error'}`);
    } finally {
      setIsUpdatingStatus(null);
    }
  };

  // Metrics summary
  const totalCount = anomalies.length;
  const highSeverityCount = anomalies.filter(
    (a) => a.severity === 'HIGH' || a.severity === 'CRITICAL'
  ).length;
  const needsReviewCount = anomalies.filter(
    (a) => a.status === 'NEEDS_REVIEW' || a.status === 'ACTIVE'
  ).length;
  const reviewedCount = anomalies.filter((a) => a.status === 'REVIEWED').length;

  const getSeverityBadge = (sev: string) => {
    switch (sev.toUpperCase()) {
      case 'CRITICAL':
        return 'bg-rose-50 text-rose-800 border-rose-300 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-900';
      case 'HIGH':
        return 'bg-[#FFF2B4] text-[#15370D] border-[#E5CD82]';
      case 'MEDIUM':
        return 'bg-cream-100 text-stone-800 border-gold-300 dark:bg-[#163013] dark:text-gold-300 dark:border-gold-600/50';
      default:
        return 'bg-sage-100 text-sage-800 border-sage-300 dark:bg-sage-950/70 dark:text-sage-200 dark:border-sage-800';
    }
  };

  const getStatusBadge = (st: string) => {
    switch (st.toUpperCase()) {
      case 'REVIEWED':
        return 'bg-sage-100/80 text-sage-800 border-sage-300 dark:bg-forest-900/80 dark:text-sage-300 dark:border-forest-700';
      case 'DISMISSED':
        return 'bg-stone-100 text-stone-600 border-stone-200 dark:bg-forest-950 dark:text-stone-400 dark:border-forest-800';
      default:
        return 'bg-[#FFF2B4] text-[#15370D] border-[#E5CD82]';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-forest-50 dark:bg-forest-900/70 text-forest-800 dark:text-sage-300 border border-forest-200 dark:border-forest-800 mb-3">
              <AlertTriangle className="w-3.5 h-3.5 text-sage-600 dark:text-gold-400" />
              <span>IBM Db2 Anomaly Intelligence · Stage 4C</span>
            </div>
            <h1 className="text-2xl font-bold text-forest-950 dark:text-cream-100 tracking-tight">
              Anomaly Intelligence & Financial Alerts
            </h1>
            <p className="text-xs sm:text-sm text-stone-500 dark:text-sage-400 mt-1 max-w-3xl">
              Deterministic, explainable indicators that highlight unusual financial behavior using your verified transaction history.
              An anomaly is a statistical signal for your review — <strong>never assumed to be fraud or unauthorized activity</strong>.
            </p>
          </div>
          <button
            onClick={loadAnomalies}
            disabled={isLoading}
            className="self-start md:self-auto px-4 py-2 bg-stone-100 dark:bg-[#163013] hover:bg-stone-200 dark:hover:bg-forest-900 text-stone-800 dark:text-cream-100 text-xs font-medium rounded-xl transition-colors flex items-center gap-2 border border-stone-200 dark:border-forest-800"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh Alerts</span>
          </button>
        </div>

        {/* 4 KPI Metric Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-6 pt-6 border-t border-stone-100 dark:border-forest-900/60">
          <div className="rounded-xl border border-stone-200 dark:border-forest-800/80 bg-stone-50/70 dark:bg-[#163013]/60 p-4">
            <div className="text-xs font-medium text-stone-500 dark:text-sage-400">Total Alerts</div>
            <div className="text-2xl font-bold font-mono text-forest-950 dark:text-cream-100 mt-1">{totalCount}</div>
            <div className="text-[11px] text-stone-400 dark:text-sage-500 mt-0.5">Scored in Db2 FINDB</div>
          </div>

          <div className="rounded-xl border border-rose-200 dark:border-rose-950/70 bg-rose-50/60 dark:bg-rose-950/30 p-4">
            <div className="text-xs font-medium text-rose-700 dark:text-rose-400">High / Critical</div>
            <div className="text-2xl font-bold font-mono text-rose-800 dark:text-rose-300 mt-1">{highSeverityCount}</div>
            <div className="text-[11px] text-rose-600/70 dark:text-rose-400/60 mt-0.5">Statistical outliers</div>
          </div>

          <div className="rounded-xl border border-gold-300 dark:border-forest-700 bg-cream-100/70 dark:bg-[#1a3814] p-4">
            <div className="text-xs font-medium text-[#15370D] dark:text-[#E5CD82]">Awaiting Review</div>
            <div className="text-2xl font-bold font-mono text-[#15370D] dark:text-[#FFF2B4] mt-1">{needsReviewCount}</div>
            <div className="text-[11px] text-forest-800/70 dark:text-gold-400/70 mt-0.5">User review requested</div>
          </div>

          <div className="rounded-xl border border-sage-200 dark:border-forest-800 bg-sage-50/70 dark:bg-forest-900/40 p-4">
            <div className="text-xs font-medium text-sage-700 dark:text-sage-300">Reviewed / Cleared</div>
            <div className="text-2xl font-bold font-mono text-forest-900 dark:text-sage-200 mt-1">{reviewedCount}</div>
            <div className="text-[11px] text-sage-600/70 dark:text-sage-400/60 mt-0.5">Verified decisions</div>
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 rounded-xl border border-stone-200 dark:border-forest-800/80 bg-stone-50/60 dark:bg-[#14290f]/70 text-xs">
        <div className="flex items-center gap-2 text-stone-700 dark:text-sage-300 font-medium">
          <Filter className="w-3.5 h-3.5 text-sage-500" />
          <span>Filters:</span>
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
          {/* Status Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-stone-500 dark:text-sage-400">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-white dark:bg-[#10240d] border border-stone-200 dark:border-forest-800 rounded-lg px-2.5 py-1 text-stone-800 dark:text-cream-100 focus:outline-hidden"
            >
              <option value="ALL">All Statuses</option>
              <option value="NEEDS_REVIEW">Needs Review</option>
              <option value="REVIEWED">Reviewed</option>
              <option value="DISMISSED">Dismissed</option>
            </select>
          </div>

          {/* Severity Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-stone-500 dark:text-sage-400">Severity:</span>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="bg-white dark:bg-[#10240d] border border-stone-200 dark:border-forest-800 rounded-lg px-2.5 py-1 text-stone-800 dark:text-cream-100 focus:outline-hidden"
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>

          {/* Type Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-stone-500 dark:text-sage-400">Type:</span>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="bg-white dark:bg-[#10240d] border border-stone-200 dark:border-forest-800 rounded-lg px-2.5 py-1 text-stone-800 dark:text-cream-100 focus:outline-hidden"
            >
              <option value="ALL">All Types</option>
              <option value="RECURRING_DRIFT">Recurring Drift</option>
              <option value="VELOCITY_SPIKE">Velocity Spike</option>
              <option value="AMOUNT_SPIKE">Amount Spike</option>
            </select>
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/80 dark:bg-rose-950/30 p-4 text-rose-800 dark:text-rose-300 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2.5">
            <XCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={loadAnomalies}
            className="px-3 py-1 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-xs font-semibold"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] p-12 text-center shadow-sm">
          <Loader2 className="w-8 h-8 animate-spin text-sage-600 dark:text-gold-400 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-forest-950 dark:text-cream-100">Loading Db2 Anomaly Alerts</h3>
          <p className="text-xs text-stone-500 dark:text-sage-400 mt-1 max-w-md mx-auto">
            Retrieving statistical evaluations and category baselines directly from IBM Db2 FINDB...
          </p>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && anomalies.length === 0 && (
        <div className="rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] p-12 text-center shadow-sm">
          <CheckCircle2 className="w-10 h-10 text-sage-600 dark:text-gold-400 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-forest-950 dark:text-cream-100">No anomalies match criteria</h3>
          <p className="text-xs text-stone-500 dark:text-sage-400 mt-1 max-w-md mx-auto">
            All evaluated ledger transactions are within expected mathematical category baselines, or active filters have excluded them.
          </p>
        </div>
      )}

      {/* Anomalies List */}
      {!isLoading && anomalies.length > 0 && (
        <div className="space-y-3">
          {anomalies.map((item) => {
            const isNeedsReview = item.status === 'NEEDS_REVIEW' || item.status === 'ACTIVE';

            return (
              <div
                key={item.alert_id}
                className="group rounded-xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] hover:border-gold-300 dark:hover:border-forest-700 p-5 transition-all shadow-sm"
              >
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                  {/* Left: Info */}
                  <div className="space-y-2 flex-1">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      {/* Severity Badge */}
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${getSeverityBadge(
                          item.severity
                        )}`}
                      >
                        <AlertTriangle className="w-3 h-3" />
                        {item.severity}
                      </span>

                      {/* Type Badge */}
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-stone-100 dark:bg-forest-900/60 text-stone-700 dark:text-sage-300 border border-stone-200/60 dark:border-forest-800/60">
                        {item.alert_type}
                      </span>

                      {/* Status Badge */}
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border ${getStatusBadge(
                          item.status
                        )}`}
                      >
                        {item.status === 'REVIEWED' ? (
                          <CheckCircle2 className="w-3 h-3 text-sage-600" />
                        ) : item.status === 'DISMISSED' ? (
                          <XCircle className="w-3 h-3" />
                        ) : (
                          <Clock className="w-3 h-3 text-[#15370D]" />
                        )}
                        <span>{item.status === 'ACTIVE' ? 'NEEDS REVIEW' : item.status}</span>
                      </span>

                      {/* Anomaly Score */}
                      <span className="text-[11px] font-mono text-stone-500 dark:text-sage-400">
                        Confidence: <strong className="text-forest-950 dark:text-cream-100">{item.score.toFixed(1)}/100</strong>
                      </span>
                    </div>

                    {/* Merchant & Amount */}
                    <div className="flex items-baseline gap-3 flex-wrap">
                      <span className="text-base sm:text-lg font-bold text-forest-950 dark:text-cream-100 tracking-tight">
                        {item.merchant || 'Multiple / Pattern Alert'}
                      </span>
                      {item.amount !== null && item.amount !== undefined && (
                        <span className="text-sm sm:text-base font-semibold font-mono text-stone-800 dark:text-gold-300">
                          {formatINR(item.amount)}
                        </span>
                      )}
                      {item.category && (
                        <span className="inline-flex items-center gap-1 text-xs text-stone-500 dark:text-sage-400">
                          <Tag className="w-3 h-3 text-sage-500" />
                          {item.category}
                        </span>
                      )}
                    </div>

                    {/* Explanation */}
                    <p className="text-xs sm:text-sm text-stone-700 dark:text-stone-300 leading-relaxed">
                      {item.explanation}
                    </p>

                    {/* Meta Footer */}
                    <div className="flex items-center gap-4 text-[11px] text-stone-400 dark:text-sage-500 font-mono pt-1">
                      {item.date && (
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {item.date}
                        </span>
                      )}
                      <span>Alert ID: <strong className="text-stone-600 dark:text-sage-300">{item.alert_id}</strong></span>
                      {item.transaction_id && (
                        <span>Tx ID: <strong className="text-stone-600 dark:text-sage-300">{item.transaction_id}</strong></span>
                      )}
                    </div>
                  </div>

                  {/* Right: Actions */}
                  <div className="flex md:flex-col items-center md:items-end gap-2 border-t md:border-t-0 pt-3 md:pt-0 border-stone-100 dark:border-forest-900/60">
                    <button
                      onClick={() => handleOpenDetail(item.alert_id)}
                      className="px-3.5 py-1.5 bg-[#15370D] hover:bg-[#1e4a14] text-[#FFF2B4] rounded-xl text-xs font-semibold transition-colors flex items-center gap-1.5 shadow-xs border border-forest-800"
                    >
                      <span>Explain Breakdown</span>
                      <ChevronRight className="w-3.5 h-3.5 text-[#E5CD82]" />
                    </button>

                    <div className="flex items-center gap-1.5">
                      {isNeedsReview ? (
                        <>
                          <button
                            onClick={() => handleUpdateStatus(item.alert_id, 'REVIEWED')}
                            disabled={isUpdatingStatus === item.alert_id}
                            className="px-2.5 py-1 bg-sage-100 hover:bg-sage-200 text-sage-900 dark:bg-forest-900/80 dark:hover:bg-forest-800 dark:text-sage-200 border border-sage-300 dark:border-forest-700 rounded-lg text-xs font-medium transition-colors"
                          >
                            Mark Reviewed
                          </button>
                          <button
                            onClick={() => handleUpdateStatus(item.alert_id, 'DISMISSED')}
                            disabled={isUpdatingStatus === item.alert_id}
                            className="px-2.5 py-1 bg-stone-100 hover:bg-stone-200 text-stone-600 dark:bg-[#163013] dark:hover:bg-forest-900 dark:text-stone-400 border border-stone-200 dark:border-forest-800 rounded-lg text-xs font-medium transition-colors"
                          >
                            Dismiss
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => handleUpdateStatus(item.alert_id, 'NEEDS_REVIEW')}
                          disabled={isUpdatingStatus === item.alert_id}
                          className="px-2.5 py-1 bg-stone-100 hover:bg-stone-200 text-stone-700 dark:bg-forest-900 dark:hover:bg-forest-800 dark:text-sage-200 border border-stone-200 dark:border-forest-800 rounded-lg text-xs font-medium transition-colors"
                        >
                          Reopen Alert
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Detailed Explanation Modal */}
      {selectedAlertId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-stone-950/70 backdrop-blur-xs animate-in fade-in">
          <div className="bg-white dark:bg-[#10240d] border border-stone-200 dark:border-forest-800 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl p-6 space-y-6">
            {/* Modal Header */}
            <div className="flex items-start justify-between gap-4 border-b border-stone-100 dark:border-forest-900/60 pb-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-stone-100 dark:bg-forest-900 text-stone-700 dark:text-sage-300 border border-stone-200 dark:border-forest-800">
                    {selectedAlertId}
                  </span>
                  <span className="text-xs text-stone-400">·</span>
                  <span className="text-xs text-forest-800 dark:text-gold-400 font-semibold flex items-center gap-1">
                    <Sparkles className="w-3 h-3" />
                    Explainable AI Grounding
                  </span>
                </div>
                <h2 className="text-xl font-bold text-forest-950 dark:text-cream-100 tracking-tight">
                  Anomaly Investigation & Mathematical Proof
                </h2>
              </div>
              <button
                onClick={() => setSelectedAlertId(null)}
                className="p-1 rounded-lg text-stone-400 hover:text-stone-800 dark:hover:text-white hover:bg-stone-100 dark:hover:bg-forest-900 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            {isLoadingExplanation && (
              <div className="py-12 text-center">
                <Loader2 className="w-8 h-8 animate-spin text-sage-600 dark:text-gold-400 mx-auto mb-2" />
                <p className="text-xs text-stone-500 dark:text-sage-400">Synthesizing statistical baseline from IBM Db2...</p>
              </div>
            )}

            {explanationError && (
              <div className="p-4 rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/80 dark:bg-rose-950/30 text-rose-800 dark:text-rose-300 text-xs">
                {explanationError}
              </div>
            )}

            {!isLoadingExplanation && explanation && (
              <div className="space-y-5 text-xs text-stone-700 dark:text-stone-300">
                {/* 1. What was detected */}
                <div className="p-4 rounded-xl border border-stone-200 dark:border-forest-800/80 bg-stone-50/70 dark:bg-[#142d0f]/60 space-y-2">
                  <h4 className="font-semibold text-forest-950 dark:text-cream-100 text-sm flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-gold-400" />
                    <span>What Was Detected</span>
                  </h4>
                  <p className="leading-relaxed text-stone-700 dark:text-stone-300">
                    {explanation.explanation}
                  </p>
                </div>

                {/* 2. Mathematical Calculation & Baselines */}
                {explanation.calculation_details && (
                  <div className="p-4 rounded-xl border border-stone-200 dark:border-forest-800/80 bg-stone-50/70 dark:bg-[#142d0f]/60 space-y-3">
                    <h4 className="font-semibold text-forest-950 dark:text-cream-100 text-sm flex items-center gap-1.5">
                      <TrendingUp className="w-4 h-4 text-forest-700 dark:text-forest-400" />
                      <span>Mathematical Baselines & Calculation Formula</span>
                    </h4>

                    {/* Formula Applied Box */}
                    {explanation.calculation_details.formula_applied && (
                      <div className="p-3 rounded-lg bg-cream-50/80 dark:bg-[#0c1a0a] border border-gold-300/80 dark:border-forest-800 font-mono text-[11px] text-forest-950 dark:text-cream-100">
                        {explanation.calculation_details.formula_applied}
                      </div>
                    )}

                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-1">
                      <div>
                        <span className="text-stone-500 dark:text-sage-400 block text-[10px]">Evaluated Charge:</span>
                        <strong className="text-forest-950 dark:text-cream-100 text-xs font-mono">
                          {formatINR(explanation.calculation_details.transaction_amount)}
                        </strong>
                      </div>

                      {explanation.calculation_details.merchant_historical_baseline !== undefined && (
                        <div>
                          <span className="text-stone-500 dark:text-sage-400 block text-[10px]">Merchant Baseline (5 mos):</span>
                          <strong className="text-forest-800 dark:text-sage-300 text-xs font-mono">
                            {formatINR(explanation.calculation_details.merchant_historical_baseline)}
                          </strong>
                        </div>
                      )}

                      {explanation.calculation_details.merchant_multiplier !== undefined && (
                        <div>
                          <span className="text-stone-500 dark:text-sage-400 block text-[10px]">Merchant Surge:</span>
                          <strong className="text-amber-800 dark:text-gold-300 text-xs font-mono">
                            {explanation.calculation_details.merchant_multiplier}x (+{Math.round((explanation.calculation_details.merchant_multiplier - 1) * 100)}%)
                          </strong>
                        </div>
                      )}

                      {explanation.calculation_details.category_baseline_clean !== undefined && (
                        <div>
                          <span className="text-stone-500 dark:text-sage-400 block text-[10px]">Clean Category Baseline:</span>
                          <strong className="text-stone-800 dark:text-stone-200 text-xs font-mono">
                            {formatINR(explanation.calculation_details.category_baseline_clean)}
                          </strong>
                        </div>
                      )}

                      {explanation.calculation_details.category_average_unadjusted !== undefined && (
                        <div>
                          <span className="text-stone-500 dark:text-sage-400 block text-[10px]">Unadjusted Category Avg:</span>
                          <strong className="text-stone-600 dark:text-sage-300 text-xs font-mono">
                            {formatINR(explanation.calculation_details.category_average_unadjusted)} ({explanation.calculation_details.category_multiplier_unadjusted}x)
                          </strong>
                        </div>
                      )}

                      {explanation.calculation_details.burst_transaction_count !== undefined && (
                        <div>
                          <span className="text-stone-500 dark:text-sage-400 block text-[10px]">Burst Occurrences:</span>
                          <strong className="text-amber-800 dark:text-gold-300 text-xs font-mono">
                            {explanation.calculation_details.burst_transaction_count} swipes
                          </strong>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 3. Evidence Identifiers */}
                {explanation.evidence_tx_ids && explanation.evidence_tx_ids.length > 0 && (
                  <div className="p-3 rounded-xl border border-stone-200 dark:border-forest-800/80 bg-stone-50/50 dark:bg-[#12280f]/50">
                    <span className="text-stone-600 dark:text-sage-300 font-medium block mb-1">Db2 Transaction Evidence:</span>
                    <div className="flex flex-wrap gap-1.5">
                      {explanation.evidence_tx_ids.map((id) => (
                        <span key={id} className="px-2 py-0.5 rounded bg-white dark:bg-[#0c1a0a] border border-stone-200 dark:border-forest-800 text-forest-950 dark:text-cream-100 font-mono text-[11px]">
                          {id}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* 4. Recommendation */}
                <div className="p-4 rounded-xl border border-forest-200 dark:border-forest-800 bg-forest-50/60 dark:bg-forest-950/40 space-y-1.5">
                  <h4 className="font-semibold text-forest-900 dark:text-cream-100 text-sm flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-forest-700 dark:text-gold-400" />
                    <span>Recommended User Action</span>
                  </h4>
                  <p className="text-stone-700 dark:text-stone-300 leading-relaxed">
                    {explanation.recommendation}
                  </p>
                </div>

                {/* 5. Limitations */}
                {explanation.limitations && (
                  <div className="p-3 rounded-lg border border-stone-200 dark:border-forest-800/80 bg-stone-50 dark:bg-[#0c1a0a] text-stone-500 dark:text-sage-400 text-[11px] leading-relaxed flex items-start gap-2">
                    <Info className="w-4 h-4 text-sage-500 shrink-0 mt-0.5" />
                    <span>{explanation.limitations}</span>
                  </div>
                )}

                {/* Modal Footer Controls */}
                <div className="flex items-center justify-between pt-4 border-t border-stone-100 dark:border-forest-900/60">
                  <div className="flex items-center gap-2">
                    <span className="text-stone-500 dark:text-sage-400">Current Status:</span>
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getStatusBadge(explanation.status)}`}>
                      {explanation.status}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleUpdateStatus(explanation.alert_id, 'REVIEWED')}
                      className="px-3 py-1.5 bg-[#15370D] hover:bg-[#1e4a14] text-[#FFF2B4] rounded-lg text-xs font-semibold transition-colors border border-forest-800"
                    >
                      Mark Reviewed
                    </button>
                    <button
                      onClick={() => handleUpdateStatus(explanation.alert_id, 'DISMISSED')}
                      className="px-3 py-1.5 bg-stone-100 hover:bg-stone-200 text-stone-700 dark:bg-[#163013] dark:hover:bg-forest-900 dark:text-stone-300 rounded-lg text-xs font-semibold transition-colors border border-stone-200 dark:border-forest-800"
                    >
                      Dismiss
                    </button>
                    <button
                      onClick={() => handleUpdateStatus(explanation.alert_id, 'NEEDS_REVIEW')}
                      className="px-3 py-1.5 bg-stone-100 hover:bg-stone-200 text-stone-600 dark:bg-[#163013] dark:hover:bg-forest-900 dark:text-sage-400 rounded-lg text-xs font-medium transition-colors border border-stone-200 dark:border-forest-800"
                    >
                      Needs Review
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
