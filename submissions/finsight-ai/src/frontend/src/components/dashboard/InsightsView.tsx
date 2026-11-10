import React, { useState, useEffect, useCallback } from 'react';
import { 
  TrendingUp, 
  Minus, 
  Calendar, 
  Printer, 
  Sparkles, 
  RefreshCw, 
  AlertCircle, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  ShieldCheck, 
  FileText, 
  BarChart2, 
  PieChart, 
  HelpCircle,
  ArrowUpRight,
  ArrowDownRight,
  Info
} from 'lucide-react';
import { apiClient, FinancialInsightsData, MonthlyReportData } from '../../api/client';

interface InsightsViewProps {
  onNavigateToAnomalies?: () => void;
  onNavigateToTransactions?: () => void;
}

export const InsightsView: React.FC<InsightsViewProps> = ({
  onNavigateToAnomalies,
  onNavigateToTransactions
}) => {
  const [selectedMonth, setSelectedMonth] = useState<string>('');
  const [insights, setInsights] = useState<FinancialInsightsData | null>(null);
  const [report, setReport] = useState<MonthlyReportData | null>(null);
  const [viewMode, setViewMode] = useState<'insights' | 'report'>('insights');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showFormulaTooltip, setShowFormulaTooltip] = useState<boolean>(false);

  const fetchInsightsAndReport = useCallback(async (month?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const [insightsRes, reportRes] = await Promise.all([
        apiClient.insights.getInsights(month),
        apiClient.insights.getMonthlyReport(month)
      ]);
      setInsights(insightsRes);
      setReport(reportRes);
      if (!selectedMonth) {
        setSelectedMonth(insightsRes.month);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load financial insights from IBM Db2.');
    } finally {
      setIsLoading(false);
    }
  }, [selectedMonth]);

  useEffect(() => {
    fetchInsightsAndReport(selectedMonth || undefined);
  }, [selectedMonth, fetchInsightsAndReport]);

  const handleMonthChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newMonth = e.target.value;
    setSelectedMonth(newMonth);
  };

  const handlePrint = () => {
    window.print();
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2
    }).format(amount);
  };

  const formatMonthName = (m: string) => {
    if (!m) return '';
    try {
      const [y, mon] = m.split('-');
      const date = new Date(parseInt(y, 10), parseInt(mon, 10) - 1, 1);
      return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
    } catch {
      return m;
    }
  };

  const renderDeltaBadge = (delta: number, pct: number | null, isExpense: boolean = false) => {
    if (pct === null) {
      return (
        <span className="inline-flex items-center space-x-1 text-[11px] font-mono px-2 py-0.5 rounded-md bg-stone-100 dark:bg-forest-900/60 text-stone-600 dark:text-sage-400">
          <Minus className="w-3 h-3 text-stone-400" />
          <span>New / 0 baseline</span>
        </span>
      );
    }

    const isPositive = delta > 0;
    const isNeutral = delta === 0;

    if (isNeutral) {
      return (
        <span className="inline-flex items-center space-x-1 text-[11px] font-mono px-2 py-0.5 rounded-md bg-stone-100 dark:bg-forest-900/60 text-stone-600 dark:text-sage-400">
          <Minus className="w-3 h-3 text-stone-400" />
          <span>0.0% MoM</span>
        </span>
      );
    }

    const isFavorable = isExpense ? !isPositive : isPositive;
    const badgeBg = isFavorable 
      ? 'bg-forest-50 dark:bg-forest-950/60 text-forest-800 dark:text-sage-300 border-forest-200 dark:border-forest-800' 
      : 'bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-900/60';

    return (
      <span className={`inline-flex items-center space-x-1 text-[11px] font-mono font-medium px-2 py-0.5 rounded-md border ${badgeBg}`}>
        {isPositive ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
        <span>{Math.abs(pct).toFixed(1)}% ({isPositive ? '+' : ''}{formatCurrency(delta)})</span>
      </span>
    );
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Top Header & View Controls */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-stone-200/80 dark:border-forest-900/60 pb-6 print:hidden">
        <div>
          <div className="flex items-center space-x-2">
            <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-forest-50 dark:bg-forest-900/70 text-forest-800 dark:text-sage-300 border border-forest-200 dark:border-forest-800">
              <Sparkles className="w-3 h-3 text-sage-600 dark:text-gold-400 mr-1" />
              Stage 6 · Deterministic Financial Intelligence
            </span>
            <span className="text-[11px] font-mono text-stone-500 dark:text-sage-400">
              Db2 Mode A Engine
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-forest-950 dark:text-cream-100 mt-1">
            Financial Insights & Reports
          </h1>
          <p className="text-xs text-stone-500 dark:text-sage-400">
            Evidence-backed cash flow trajectory, month-over-month shifts, and printable audit reports.
          </p>
        </div>

        {/* Action Toolbar */}
        <div className="flex items-center space-x-3 flex-wrap gap-y-2">
          {/* Month Selector */}
          <div className="flex items-center space-x-2 bg-white dark:bg-[#10240d] border border-stone-200 dark:border-forest-800 rounded-xl px-3 py-1.5 shadow-xs">
            <Calendar className="w-4 h-4 text-sage-500" />
            <select
              value={selectedMonth}
              onChange={handleMonthChange}
              disabled={isLoading}
              className="bg-transparent text-xs font-semibold text-forest-950 dark:text-cream-100 focus:outline-hidden cursor-pointer"
            >
              {insights?.available_months && insights.available_months.length > 0 ? (
                insights.available_months.map((m) => (
                  <option key={m} value={m} className="bg-white dark:bg-[#10240d] text-forest-950 dark:text-cream-100">
                    {formatMonthName(m)} ({m})
                  </option>
                ))
              ) : (
                <option value={selectedMonth || '2026-11'}>
                  {formatMonthName(selectedMonth || '2026-11')}
                </option>
              )}
            </select>
          </div>

          {/* View Mode Toggle: Insights vs Report */}
          <div className="flex items-center bg-stone-100 dark:bg-[#163013] p-1 rounded-xl border border-stone-200 dark:border-forest-800">
            <button
              onClick={() => setViewMode('insights')}
              className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                viewMode === 'insights'
                  ? 'bg-[#15370D] text-[#FFF2B4] shadow-xs font-semibold'
                  : 'text-stone-600 dark:text-sage-400 hover:text-forest-950 dark:hover:text-cream-100'
              }`}
            >
              <BarChart2 className="w-3.5 h-3.5 text-[#E5CD82]" />
              <span>Insights View</span>
            </button>
            <button
              onClick={() => setViewMode('report')}
              className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                viewMode === 'report'
                  ? 'bg-[#15370D] text-[#FFF2B4] shadow-xs font-semibold'
                  : 'text-stone-600 dark:text-sage-400 hover:text-forest-950 dark:hover:text-cream-100'
              }`}
            >
              <FileText className="w-3.5 h-3.5 text-[#E5CD82]" />
              <span>Audit Report</span>
            </button>
          </div>

          {/* Print Button */}
          <button
            onClick={handlePrint}
            className="inline-flex items-center space-x-1.5 px-3 py-2 rounded-xl border border-stone-200 dark:border-forest-800 bg-white dark:bg-[#10240d] hover:bg-stone-50 dark:hover:bg-forest-900/60 text-xs font-semibold text-stone-700 dark:text-sage-300 shadow-xs transition-colors"
            title="Print or Save PDF report"
          >
            <Printer className="w-3.5 h-3.5 text-sage-600" />
            <span className="hidden sm:inline">Print / Save PDF</span>
          </button>

          {/* Refresh Action */}
          <button
            onClick={() => fetchInsightsAndReport(selectedMonth)}
            disabled={isLoading}
            className="p-2 rounded-xl border border-stone-200 dark:border-forest-800 bg-white dark:bg-[#10240d] hover:bg-stone-50 dark:hover:bg-forest-900/60 text-stone-700 dark:text-sage-300 shadow-xs transition-colors disabled:opacity-50"
            title="Refresh from IBM Db2"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-sage-400' : 'text-sage-600'}`} />
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div role="alert" className="p-4 rounded-2xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/80 dark:bg-rose-950/30 text-rose-800 dark:text-rose-300 text-xs flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => fetchInsightsAndReport(selectedMonth)}
            className="px-3 py-1 rounded-lg bg-rose-600 text-white hover:bg-rose-700 text-xs font-semibold shrink-0"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && !insights && (
        <div className="py-20 text-center space-y-4">
          <RefreshCw className="w-8 h-8 text-sage-600 dark:text-gold-400 animate-spin mx-auto" />
          <p className="text-xs text-stone-500 dark:text-sage-400 font-mono">
            Querying IBM Db2 12.1.5.0 for verified financial telemetry...
          </p>
        </div>
      )}

      {/* View Mode 1: Insights Dashboard */}
      {viewMode === 'insights' && insights && (
        <div className="space-y-8">
          {/* Executive Summary Narrative Card */}
          <div className="p-6 rounded-2xl border border-[#E5CD82]/80 dark:border-forest-800 bg-cream-50/70 dark:bg-[#12280f] shadow-xs relative overflow-hidden">
            <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <span className="w-2 h-2 rounded-full bg-[#15370D] dark:bg-[#E5CD82]"></span>
                  <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-forest-950 dark:text-cream-100">
                    Monthly Executive Briefing · {formatMonthName(insights.month)}
                  </span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-cream-200 dark:bg-forest-900 text-[#15370D] dark:text-[#E5CD82] font-semibold border border-gold-300 dark:border-forest-700">
                    {insights.generation_mode}
                  </span>
                </div>
                <div className="text-xs sm:text-sm text-stone-700 dark:text-stone-300 leading-relaxed whitespace-pre-line max-w-4xl">
                  {insights.narrative_summary}
                </div>
              </div>

              {/* Verified Badge */}
              <div className="shrink-0 flex items-center space-x-2 bg-white/90 dark:bg-[#163013] backdrop-blur-xs px-3.5 py-2 rounded-xl border border-stone-200 dark:border-forest-800 text-right shadow-xs">
                <ShieldCheck className="w-5 h-5 text-forest-700 dark:text-gold-400" />
                <div className="text-left text-[11px]">
                  <div className="font-bold text-forest-950 dark:text-cream-100">IBM Db2 Verified</div>
                  <div className="text-[10px] text-stone-500 dark:text-sage-400 font-mono">0% Hallucination</div>
                </div>
              </div>
            </div>
          </div>

          {/* 4 Month-over-Month KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Total Inflow */}
            <div className="p-5 rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] shadow-sm space-y-2">
              <div className="flex items-center justify-between text-xs text-stone-500 dark:text-sage-400">
                <span>Verified Inflow</span>
                <span className="text-[11px] font-mono text-forest-800 dark:text-forest-400 font-bold">CREDIT</span>
              </div>
              <div className="text-2xl font-extrabold tracking-tight text-forest-900 dark:text-cream-100 font-mono">
                {formatCurrency(insights.income.current)}
              </div>
              <div className="pt-1 flex items-center justify-between border-t border-stone-100 dark:border-forest-900/50 text-[11px]">
                <span className="text-stone-400 dark:text-sage-500 font-mono">vs {insights.previous_month}:</span>
                {renderDeltaBadge(insights.income.difference, insights.income.percentage_change, false)}
              </div>
            </div>

            {/* Total Outflow */}
            <div className="p-5 rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] shadow-sm space-y-2">
              <div className="flex items-center justify-between text-xs text-stone-500 dark:text-sage-400">
                <span>Consumption Outflow</span>
                <span className="text-[11px] font-mono text-stone-400">DEBIT</span>
              </div>
              <div className="text-2xl font-extrabold tracking-tight text-stone-900 dark:text-cream-100 font-mono">
                {formatCurrency(insights.expenses.current)}
              </div>
              <div className="pt-1 flex items-center justify-between border-t border-stone-100 dark:border-forest-900/50 text-[11px]">
                <span className="text-stone-400 dark:text-sage-500 font-mono">vs {insights.previous_month}:</span>
                {renderDeltaBadge(insights.expenses.difference, insights.expenses.percentage_change, true)}
              </div>
            </div>

            {/* Net Cash Flow */}
            <div className="p-5 rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] shadow-sm space-y-2">
              <div className="flex items-center justify-between text-xs text-stone-500 dark:text-sage-400">
                <span>Net Cash Flow</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono ${
                  insights.net_cash_flow.current >= 0 
                    ? 'bg-[#FFF2B4] text-[#15370D] border border-[#E5CD82]' 
                    : 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                }`}>
                  {insights.net_cash_flow.current >= 0 ? 'SURPLUS' : 'DEFICIT'}
                </span>
              </div>
              <div className={`text-2xl font-extrabold tracking-tight font-mono ${
                insights.net_cash_flow.current >= 0 ? 'text-[#15370D] dark:text-[#E5CD82]' : 'text-rose-600 dark:text-rose-400'
              }`}>
                {formatCurrency(insights.net_cash_flow.current)}
              </div>
              <div className="pt-1 flex items-center justify-between border-t border-stone-100 dark:border-forest-900/50 text-[11px]">
                <span className="text-stone-400 dark:text-sage-500 font-mono">vs {insights.previous_month}:</span>
                {renderDeltaBadge(insights.net_cash_flow.difference, insights.net_cash_flow.percentage_change, false)}
              </div>
            </div>

            {/* Documented Savings Rate */}
            <div className="p-5 rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] shadow-sm space-y-2 relative">
              <div className="flex items-center justify-between text-xs text-stone-500 dark:text-sage-400">
                <div className="flex items-center space-x-1">
                  <span>Savings Rate</span>
                  <button
                    onClick={() => setShowFormulaTooltip(!showFormulaTooltip)}
                    className="text-stone-400 hover:text-stone-600 dark:hover:text-stone-200 transition-colors"
                    title="View formula & calculation method"
                  >
                    <HelpCircle className="w-3.5 h-3.5" />
                  </button>
                </div>
                <span className="text-[10px] font-mono text-sage-600 dark:text-gold-400 font-semibold">FORMULA APPLIED</span>
              </div>

              {/* Tooltip Popup */}
              {showFormulaTooltip && (
                <div className="absolute top-12 left-2 right-2 z-30 p-3 rounded-xl bg-white dark:bg-[#10240d] text-forest-950 dark:text-cream-100 text-[11px] shadow-lg border border-gold-300 dark:border-forest-700 space-y-1">
                  <div className="font-bold flex items-center justify-between">
                    <span>Calculation Methodology</span>
                    <button onClick={() => setShowFormulaTooltip(false)} className="text-stone-400 hover:text-stone-700 dark:hover:text-white">✕</button>
                  </div>
                  <div className="font-mono text-forest-800 dark:text-gold-300 bg-cream-100 dark:bg-forest-900/60 p-1.5 rounded">{insights.savings_rate_formula}</div>
                  <div className="text-stone-600 dark:text-sage-300">{insights.savings_rate_explanation}</div>
                </div>
              )}

              <div className="text-2xl font-extrabold tracking-tight text-[#15370D] dark:text-[#E5CD82] font-mono">
                {insights.savings_rate.toFixed(1)}%
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-cream-100 dark:bg-[#163013] h-2 rounded-full overflow-hidden">
                <div 
                  className={`h-full rounded-full transition-all duration-500 ${
                    insights.savings_rate >= 20 ? 'bg-[#15370D] dark:bg-[#E5CD82]' : insights.savings_rate > 0 ? 'bg-sage-500' : 'bg-rose-500'
                  }`}
                  style={{ width: `${Math.min(Math.max(insights.savings_rate, 0), 100)}%` }}
                />
              </div>

              <div className="pt-1 text-[10px] text-stone-500 dark:text-sage-400 truncate">
                {insights.savings_rate_explanation}
              </div>
            </div>
          </div>

          {/* Category Spending Shift Table */}
          <div className="p-6 rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] shadow-sm space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div>
                <h3 className="text-base font-bold text-forest-950 dark:text-cream-100 flex items-center space-x-2">
                  <PieChart className="w-4 h-4 text-sage-600 dark:text-gold-400" />
                  <span>Category Spending Shifts ({insights.month} vs {insights.previous_month})</span>
                </h3>
                <p className="text-xs text-stone-500 dark:text-sage-400">
                  Month-over-month expenditure expansion and contraction across living categories.
                </p>
              </div>
              <span className="text-[11px] font-mono text-stone-400 dark:text-sage-500">
                {insights.category_changes.length} categories tracked
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-stone-100 dark:border-forest-900/60 text-stone-500 dark:text-sage-400 font-mono text-[11px]">
                    <th className="py-2.5 px-3">CATEGORY</th>
                    <th className="py-2.5 px-3 text-right">THIS MONTH ({insights.month})</th>
                    <th className="py-2.5 px-3 text-right">PREV MONTH ({insights.previous_month})</th>
                    <th className="py-2.5 px-3 text-right">NET SHIFT (INR)</th>
                    <th className="py-2.5 px-3 text-right">MOM CHANGE</th>
                    <th className="py-2.5 px-3 text-center">TXS</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 dark:divide-forest-900/50 font-sans">
                  {insights.category_changes.map((cat, idx) => (
                    <tr key={idx} className="hover:bg-stone-50/60 dark:hover:bg-forest-900/30 transition-colors">
                      <td className="py-3 px-3 font-semibold text-forest-950 dark:text-cream-100 flex items-center space-x-2">
                        <span className="w-2 h-2 rounded-full bg-[#15370D] dark:bg-[#E5CD82]"></span>
                        <span>{cat.category_name}</span>
                      </td>
                      <td className="py-3 px-3 text-right font-mono font-medium text-forest-950 dark:text-cream-100">
                        {formatCurrency(cat.current_amount)}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-stone-500 dark:text-sage-400">
                        {formatCurrency(cat.previous_amount)}
                      </td>
                      <td className="py-3 px-3 text-right font-mono">
                        <span className={cat.difference > 0 ? 'text-amber-700 dark:text-amber-400' : cat.difference < 0 ? 'text-forest-700 dark:text-forest-300' : 'text-stone-400'}>
                          {cat.difference > 0 ? '+' : ''}{formatCurrency(cat.difference)}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right">
                        {renderDeltaBadge(cat.difference, cat.percentage_change, true)}
                      </td>
                      <td className="py-3 px-3 text-center font-mono text-stone-500 dark:text-sage-400">
                        {cat.tx_count}
                      </td>
                    </tr>
                  ))}
                  {insights.category_changes.length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-stone-400 font-mono">
                        No categorized expense records recorded for this monthly period.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Two-Column Grid: Recurring Commitments & Anomaly Intelligence */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Recurring Commitments */}
            <div className="p-6 rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Clock className="w-4 h-4 text-sage-600 dark:text-gold-400" />
                  <h3 className="text-base font-bold text-forest-950 dark:text-cream-100">
                    Recurring Commitments & Subscriptions
                  </h3>
                </div>
                <span className="text-[11px] font-mono text-stone-400 dark:text-sage-500">
                  {insights.recurring_observations.length} observed
                </span>
              </div>

              <div className="space-y-2.5">
                {insights.recurring_observations.map((rec, idx) => (
                  <div 
                    key={idx}
                    className="p-3 rounded-xl border border-stone-100 dark:border-forest-800 bg-stone-50/60 dark:bg-[#163013]/60 flex items-center justify-between text-xs"
                  >
                    <div className="space-y-0.5">
                      <div className="font-semibold text-forest-950 dark:text-cream-100">
                        {rec.merchant}
                      </div>
                      <div className="text-[11px] text-stone-500 dark:text-sage-400 flex items-center space-x-2">
                        <span>{rec.category}</span>
                        <span>·</span>
                        <span className="font-mono text-[10px] text-stone-400 dark:text-sage-500">{rec.last_date}</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono font-bold text-forest-950 dark:text-cream-100">
                        {formatCurrency(rec.amount)}
                      </div>
                      <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#FFF2B4] text-[#15370D] font-bold border border-[#E5CD82]">
                        {rec.frequency}
                      </span>
                    </div>
                  </div>
                ))}
                {insights.recurring_observations.length === 0 && (
                  <div className="py-8 text-center text-stone-400 font-mono text-xs">
                    No recurring subscriptions or automated bills observed in this month.
                  </div>
                )}
              </div>
            </div>

            {/* Anomaly & Risk Observations */}
            <div className="p-6 rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-gold-400" />
                  <h3 className="text-base font-bold text-forest-950 dark:text-cream-100">
                    Unusual Spending & Anomaly Alerts
                  </h3>
                </div>
                {onNavigateToAnomalies && (
                  <button
                    onClick={onNavigateToAnomalies}
                    className="text-xs font-semibold text-forest-800 dark:text-gold-400 hover:underline"
                  >
                    View Anomaly Center →
                  </button>
                )}
              </div>

              <div className="space-y-2.5">
                {insights.unusual_observations.map((anom, idx) => (
                  <div 
                    key={idx}
                    className="p-3.5 rounded-xl border border-gold-300 dark:border-forest-800 bg-cream-50/70 dark:bg-[#183013]/60 space-y-1.5"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <div className="font-bold text-forest-950 dark:text-cream-100 flex items-center space-x-1.5">
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#FFF2B4] text-[#15370D] font-bold border border-[#E5CD82]">
                          {anom.alert_type}
                        </span>
                        <span>{anom.merchant}</span>
                      </div>
                      <div className="font-mono font-bold text-forest-950 dark:text-cream-100">
                        {formatCurrency(anom.amount)}
                      </div>
                    </div>
                    <p className="text-[11px] text-stone-600 dark:text-sage-300 leading-snug">
                      {anom.description}
                    </p>
                  </div>
                ))}
                {insights.unusual_observations.length === 0 && (
                  <div className="py-8 text-center text-stone-400 font-mono text-xs flex flex-col items-center space-y-2">
                    <CheckCircle2 className="w-6 h-6 text-forest-700 dark:text-sage-400" />
                    <span>No unreviewed statistical anomaly alerts flagged for this period.</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Top Merchants Leaderboard */}
          <div className="p-6 rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-forest-950 dark:text-cream-100 flex items-center space-x-2">
                <TrendingUp className="w-4 h-4 text-forest-700 dark:text-gold-400" />
                <span>Top Merchant Expenditures ({formatMonthName(insights.month)})</span>
              </h3>
              {onNavigateToTransactions && (
                <button
                  onClick={onNavigateToTransactions}
                  className="text-xs font-semibold text-forest-800 dark:text-gold-400 hover:underline"
                >
                  View in Transactions Explorer →
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
              {insights.top_merchants.map((m, idx) => (
                <div 
                  key={idx}
                  className="p-3.5 rounded-xl border border-stone-100 dark:border-forest-800 bg-stone-50/60 dark:bg-[#163013]/60 space-y-1"
                >
                  <div className="text-[10px] font-mono text-sage-600 dark:text-gold-400 font-semibold uppercase">
                    Rank #{idx + 1}
                  </div>
                  <div className="font-bold text-xs text-forest-950 dark:text-cream-100 truncate" title={m.merchant}>
                    {m.merchant}
                  </div>
                  <div className="text-sm font-extrabold font-mono text-forest-950 dark:text-cream-100">
                    {formatCurrency(m.total_spent)}
                  </div>
                  <div className="text-[10px] text-stone-500 dark:text-sage-400 flex items-center justify-between">
                    <span>{m.category}</span>
                    <span>{m.tx_count} txs</span>
                  </div>
                </div>
              ))}
              {insights.top_merchants.length === 0 && (
                <div className="col-span-full py-6 text-center text-stone-400 font-mono text-xs">
                  Zero merchant transactions recorded for this period.
                </div>
              )}
            </div>
          </div>

          {/* Calculation Methodology & Disclaimer */}
          <div className="p-4 rounded-xl border border-stone-200 dark:border-forest-800 bg-stone-50 dark:bg-[#0c1a0a] text-[11px] text-stone-500 dark:text-sage-400 space-y-1">
            <div className="font-bold text-forest-950 dark:text-cream-100 flex items-center space-x-1.5">
              <Info className="w-3.5 h-3.5 text-sage-600 dark:text-gold-400" />
              <span>Calculation Methodology & Verification Notes:</span>
            </div>
            <ul className="list-disc list-inside space-y-0.5">
              {insights.calculation_notes.map((note, idx) => (
                <li key={idx}>{note}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* View Mode 2: Formal Printable Monthly Report */}
      {viewMode === 'report' && report && (
        <div className="bg-white dark:bg-[#0b160a] p-8 sm:p-12 rounded-3xl border-2 border-[#15370D] dark:border-forest-700 shadow-sm print:border-none print:shadow-none print:p-0 space-y-8 font-sans">
          {/* Printable Report Header */}
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between border-b-2 border-[#15370D] dark:border-[#E5CD82] pb-6 gap-4">
            <div>
              <div className="flex items-center space-x-2">
                <div className="w-7 h-7 rounded-lg bg-[#15370D] text-[#FFF2B4] flex items-center justify-center font-bold text-sm border border-forest-800">
                  F
                </div>
                <span className="text-xl font-black tracking-tight text-forest-950 dark:text-cream-100">
                  FinSight AI
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sage-100 dark:bg-forest-900 text-forest-900 dark:text-cream-100 border border-sage-200 dark:border-forest-800">
                  Db2 Verified
                </span>
              </div>
              <h2 className="text-2xl font-black tracking-tight text-forest-950 dark:text-cream-100 uppercase mt-2">
                Monthly Financial Statement
              </h2>
              <div className="text-xs text-stone-500 dark:text-sage-400 font-mono">
                Accounting Period: {formatMonthName(report.month)} ({report.month})
              </div>
            </div>

            {/* Document Telemetry */}
            <div className="text-left sm:text-right text-xs space-y-0.5 font-mono">
              <div className="text-stone-500 dark:text-sage-400">Statement ID: STMT-{report.month.replace('-', '')}-{report.user_id.slice(-8)}</div>
              <div className="text-stone-500 dark:text-sage-400">Generated: {report.generated_at}</div>
              <div className="text-forest-950 dark:text-cream-100 font-semibold">Account: {report.user_name}</div>
              <div className="text-stone-400 dark:text-sage-500 text-[10px]">{report.user_email}</div>
            </div>
          </div>

          {/* Executive Summary Block */}
          <div className="p-4 rounded-xl border border-gold-300 dark:border-forest-800 bg-cream-50/70 dark:bg-[#163013]/60 text-xs text-stone-700 dark:text-stone-300 leading-relaxed">
            <span className="font-bold text-forest-950 dark:text-cream-100 block mb-1">
              Executive Commentary:
            </span>
            {report.executive_summary}
          </div>

          {/* Primary Statement Metrics Table */}
          <div className="space-y-3">
            <h3 className="text-sm font-bold tracking-tight text-forest-950 dark:text-cream-100 uppercase font-mono">
              1. Cash Flow Settlement Summary
            </h3>
            <table className="w-full text-xs text-left border-collapse border border-stone-200 dark:border-forest-800">
              <thead>
                <tr className="bg-stone-50 dark:bg-[#15370D] text-forest-950 dark:text-cream-100 font-mono text-[11px]">
                  <th className="p-2.5 border border-stone-200 dark:border-forest-700">FINANCIAL INDICATOR</th>
                  <th className="p-2.5 text-right border border-stone-200 dark:border-forest-700">REPORTING PERIOD ({report.month})</th>
                  <th className="p-2.5 text-right border border-stone-200 dark:border-forest-700">PREVIOUS PERIOD ({report.previous_month})</th>
                  <th className="p-2.5 text-right border border-stone-200 dark:border-forest-700">NET CHANGE</th>
                  <th className="p-2.5 text-right border border-stone-200 dark:border-forest-700">VARIANCE (%)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-200 dark:divide-forest-800/80 font-mono">
                <tr>
                  <td className="p-2.5 font-bold text-forest-950 dark:text-cream-100">Gross Verified Inflow (Credits)</td>
                  <td className="p-2.5 text-right font-bold text-forest-950 dark:text-cream-100">{formatCurrency(report.summary.total_income)}</td>
                  <td className="p-2.5 text-right text-stone-500 dark:text-sage-400">{formatCurrency(report.comparison.income.previous)}</td>
                  <td className="p-2.5 text-right">{formatCurrency(report.comparison.income.difference)}</td>
                  <td className="p-2.5 text-right">{report.comparison.income.percentage_change !== null ? `${report.comparison.income.percentage_change.toFixed(1)}%` : 'N/A'}</td>
                </tr>
                <tr>
                  <td className="p-2.5 font-bold text-stone-800 dark:text-stone-300">Consumption Outflow (Debits)</td>
                  <td className="p-2.5 text-right font-bold text-stone-800 dark:text-stone-300">{formatCurrency(report.summary.total_expenses)}</td>
                  <td className="p-2.5 text-right text-stone-500 dark:text-sage-400">{formatCurrency(report.comparison.expenses.previous)}</td>
                  <td className="p-2.5 text-right">{formatCurrency(report.comparison.expenses.difference)}</td>
                  <td className="p-2.5 text-right">{report.comparison.expenses.percentage_change !== null ? `${report.comparison.expenses.percentage_change.toFixed(1)}%` : 'N/A'}</td>
                </tr>
                <tr className="bg-cream-50/50 dark:bg-forest-900/40">
                  <td className="p-2.5 font-bold text-[#15370D] dark:text-[#E5CD82]">Net Cash Flow (Surplus / Deficit)</td>
                  <td className="p-2.5 text-right font-extrabold text-[#15370D] dark:text-[#E5CD82]">{formatCurrency(report.summary.net_cash_flow)}</td>
                  <td className="p-2.5 text-right text-stone-500 dark:text-sage-400">{formatCurrency(report.comparison.net_cash_flow.previous)}</td>
                  <td className="p-2.5 text-right">{formatCurrency(report.comparison.net_cash_flow.difference)}</td>
                  <td className="p-2.5 text-right">{report.comparison.net_cash_flow.percentage_change !== null ? `${report.comparison.net_cash_flow.percentage_change.toFixed(1)}%` : 'N/A'}</td>
                </tr>
                <tr>
                  <td className="p-2.5 font-bold text-forest-800 dark:text-gold-400">Effective Savings Rate (%)</td>
                  <td className="p-2.5 text-right font-bold text-forest-800 dark:text-gold-400">{report.summary.savings_rate.toFixed(2)}%</td>
                  <td colSpan={3} className="p-2.5 text-stone-400 dark:text-sage-500 text-[10px] font-sans">Formula: (Inflow - Outflow) / Inflow * 100</td>
                </tr>
                <tr>
                  <td className="p-2.5 text-stone-600 dark:text-sage-400 font-sans">Posted Transaction Ledger Count</td>
                  <td className="p-2.5 text-right font-mono">{report.summary.posted_transaction_count} items</td>
                  <td colSpan={3} className="p-2.5 text-stone-400 dark:text-sage-500 text-[10px] font-sans">Excludes {report.summary.pending_transaction_count} pending / escrow transactions</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Category Spending Breakdown Table */}
          <div className="space-y-3">
            <h3 className="text-sm font-bold tracking-tight text-forest-950 dark:text-cream-100 uppercase font-mono">
              2. Categorical Expenditure Allocation
            </h3>
            <table className="w-full text-xs text-left border-collapse border border-stone-200 dark:border-forest-800">
              <thead>
                <tr className="bg-stone-50 dark:bg-[#15370D] text-forest-950 dark:text-cream-100 font-mono text-[11px]">
                  <th className="p-2 border border-stone-200 dark:border-forest-700">CATEGORY</th>
                  <th className="p-2 text-right border border-stone-200 dark:border-forest-700">CURRENT SPENT</th>
                  <th className="p-2 text-right border border-stone-200 dark:border-forest-700">PREV SPENT</th>
                  <th className="p-2 text-right border border-stone-200 dark:border-forest-700">VARIANCE</th>
                  <th className="p-2 text-center border border-stone-200 dark:border-forest-700">ACTIVITY</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-200 dark:divide-forest-800/80 font-mono">
                {report.category_breakdown.map((cat, idx) => (
                  <tr key={idx}>
                    <td className="p-2 font-semibold text-forest-950 dark:text-cream-100 font-sans">{cat.category_name}</td>
                    <td className="p-2 text-right">{formatCurrency(cat.current_amount)}</td>
                    <td className="p-2 text-right text-stone-500 dark:text-sage-400">{formatCurrency(cat.previous_amount)}</td>
                    <td className="p-2 text-right">{cat.percentage_change !== null ? `${cat.percentage_change.toFixed(1)}%` : 'N/A'}</td>
                    <td className="p-2 text-center">{cat.tx_count} txs</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Top Merchants Table */}
          <div className="space-y-3">
            <h3 className="text-sm font-bold tracking-tight text-forest-950 dark:text-cream-100 uppercase font-mono">
              3. Significant Merchant Engagements
            </h3>
            <table className="w-full text-xs text-left border-collapse border border-stone-200 dark:border-forest-800">
              <thead>
                <tr className="bg-stone-50 dark:bg-[#15370D] text-forest-950 dark:text-cream-100 font-mono text-[11px]">
                  <th className="p-2 border border-stone-200 dark:border-forest-700">MERCHANT / PAYEE</th>
                  <th className="p-2 border border-stone-200 dark:border-forest-700">CATEGORY</th>
                  <th className="p-2 text-center border border-stone-200 dark:border-forest-700">TRANSACTIONS</th>
                  <th className="p-2 text-right border border-stone-200 dark:border-forest-700">TOTAL DISBURSED</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-200 dark:divide-forest-800/80 font-mono">
                {report.top_merchants.map((m, idx) => (
                  <tr key={idx}>
                    <td className="p-2 font-bold text-forest-950 dark:text-cream-100 font-sans">{m.merchant}</td>
                    <td className="p-2 text-stone-600 dark:text-sage-400 font-sans">{m.category}</td>
                    <td className="p-2 text-center">{m.tx_count}</td>
                    <td className="p-2 text-right font-bold">{formatCurrency(m.total_spent)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Methodology & Regulatory Footnote */}
          <div className="border-t border-stone-200 dark:border-forest-800 pt-6 text-[10px] text-stone-400 dark:text-sage-500 space-y-1 font-mono">
            <div className="font-bold text-forest-950 dark:text-cream-100">AUDIT METHODOLOGY & LEDGER CONSTRAINTS</div>
            <ul className="list-disc list-inside space-y-0.5">
              {report.methodology_notes.map((m, idx) => (
                <li key={idx}>{m}</li>
              ))}
            </ul>
            <div className="pt-4 flex items-center justify-between text-stone-400 dark:text-sage-500">
              <span>IBM Db2 12.1.5.0 · Cryptographic Tenant Partitioning</span>
              <span>FinSight AI Platform Automated Attestation</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
