import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiClient, DashboardSummary, Transaction } from '../api/client';
import { DashboardNav } from '../components/dashboard/DashboardNav';
import { MetricCards } from '../components/dashboard/MetricCards';
import { MonthlyChart } from '../components/dashboard/MonthlyChart';
import { CategoryBreakdown } from '../components/dashboard/CategoryBreakdown';
import { RecentTransactions } from '../components/dashboard/RecentTransactions';
import { TransactionsView } from '../components/dashboard/TransactionsView';
import { AssistantView, MessageItem } from '../components/dashboard/AssistantView';
import { SemanticSearchView } from '../components/dashboard/SemanticSearchView';
import { AnomaliesView } from '../components/dashboard/AnomaliesView';
import { ImportTransactionsView } from '../components/dashboard/ImportTransactionsView';
import { InsightsView } from '../components/dashboard/InsightsView';
import { 
  RefreshCw, 
  AlertCircle, 
  Database, 
  Sparkles, 
  Bot, 
  Search, 
  AlertTriangle, 
  UploadCloud,
  LineChart
} from 'lucide-react';

interface DashboardPageProps {
  onNavigate: (route: string) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onNavigate }) => {
  const { user, logout } = useAuth();
  const [currentTab, setCurrentTab] = useState<'dashboard' | 'transactions' | 'insights' | 'assistant' | 'search' | 'anomalies' | 'import'>('dashboard');
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [recentTransactions, setRecentTransactions] = useState<Transaction[]>([]);
  const [assistantMessages, setAssistantMessages] = useState<MessageItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<string>('');

  const loadDashboardData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [summaryRes, txRes] = await Promise.all([
        apiClient.dashboard.getSummary(),
        apiClient.dashboard.getTransactions({ limit: 8 }),
      ]);
      setSummary(summaryRes);
      setRecentTransactions(txRes.transactions);
      setLastRefreshed(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    } catch (err: any) {
      setError(err?.message || 'Failed to load financial telemetry from IBM Db2.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    setAssistantMessages([]); // Clear in-memory conversation on logout
    try {
      await logout();
      onNavigate('/');
    } catch (err: any) {
      setError(err?.message || 'Logout failed.');
      setIsLoggingOut(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FAF8F3] dark:bg-[#0b160a] text-[#152912] dark:text-[#F5F7F2] flex flex-col font-sans transition-colors">
      {/* Authenticated Navigation: Desktop Forest Green Sidebar + Top Header + Mobile Drawer */}
      <DashboardNav
        currentTab={currentTab}
        onTabChange={setCurrentTab}
        onLogout={handleLogout}
        isLoggingOut={isLoggingOut}
        onRefresh={loadDashboardData}
        isLoading={isLoading}
        lastRefreshed={lastRefreshed}
      />

      {/* Main Command Center Container — Offset on Desktop for Fixed Sidebar */}
      <div className="lg:pl-64 flex-1 flex flex-col min-w-0">
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
          {/* Error Alert with Retry */}
          {error && (
            <div
              role="alert"
              className="p-4 rounded-2xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/90 dark:bg-rose-950/40 text-rose-800 dark:text-rose-200 text-xs flex items-center justify-between shadow-2xs"
            >
              <div className="flex items-center space-x-2.5">
                <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />
                <span>{error}</span>
              </div>
              <button
                onClick={loadDashboardData}
                className="px-3 py-1 rounded-lg bg-[#15370D] text-[#FFF2B4] hover:bg-[#1f4e14] text-xs font-semibold shrink-0 transition-colors"
              >
                Retry
              </button>
            </div>
          )}

          {currentTab === 'transactions' ? (
            /* Full Transactions Ledger View */
            <TransactionsView
              onBack={() => setCurrentTab('dashboard')}
              onImport={() => setCurrentTab('import')}
            />
          ) : currentTab === 'insights' ? (
            /* Stage 6: Financial Insights & Reports View */
            <InsightsView
              onNavigateToAnomalies={() => setCurrentTab('anomalies')}
              onNavigateToTransactions={() => setCurrentTab('transactions')}
            />
          ) : currentTab === 'assistant' ? (
            /* Conversational Financial AI Assistant View */
            <AssistantView messages={assistantMessages} setMessages={setAssistantMessages} />
          ) : currentTab === 'search' ? (
            /* Semantic Transaction Search View */
            <SemanticSearchView />
          ) : currentTab === 'anomalies' ? (
            /* Anomaly Intelligence & Alerts View */
            <AnomaliesView />
          ) : currentTab === 'import' ? (
            /* Secure CSV Import View */
            <ImportTransactionsView
              onNavigateToTransactions={() => setCurrentTab('transactions')}
              onNavigateToDashboard={() => {
                setCurrentTab('dashboard');
                loadDashboardData();
              }}
            />
          ) : (
            /* Command Center Overview View */
            <div className="space-y-8">
              {/* Top Welcome & Telemetry Bar */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 p-6 rounded-2xl border border-[#E6E2D8] dark:border-[#1c3619] bg-white/80 dark:bg-[#10210e]/80 shadow-2xs backdrop-blur-xs">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#15370D] text-[#FFF2B4] border border-[#E5CD82]/40 shadow-xs">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#E5CD82] animate-pulse mr-1"></span>
                      Db2 Active Session
                    </span>
                    <span className="text-[11px] font-mono text-[#5C6C58] dark:text-[#95A890]">
                      FINDB 12.1.5.0
                    </span>
                  </div>
                  <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[#152912] dark:text-white">
                    Welcome back, {user?.full_name?.split(' ')[0] || 'FinSight User'}
                  </h1>
                  <p className="text-xs text-[#5C6C58] dark:text-[#95A890]">
                    Real-time telemetry and cash-flow narrative synthesized from your IBM Db2 ledger
                  </p>
                </div>

                {/* Refresh Action */}
                <div className="flex items-center space-x-3 self-start sm:self-auto">
                  {lastRefreshed && (
                    <span className="text-[11px] font-mono text-[#728E6D] dark:text-[#95A890] hidden sm:inline">
                      Updated {lastRefreshed}
                    </span>
                  )}
                  <button
                    onClick={loadDashboardData}
                    disabled={isLoading}
                    className="inline-flex items-center space-x-1.5 px-3.5 py-2 rounded-xl border border-[#D8D2C4] dark:border-[#244220] bg-[#FAF8F3] dark:bg-[#162c14] hover:bg-white dark:hover:bg-[#1e3a1b] text-xs font-semibold text-[#15370D] dark:text-[#E5CD82] shadow-2xs transition-colors disabled:opacity-50"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-[#728E6D]' : 'text-[#728E6D] dark:text-[#E5CD82]'}`} />
                    <span>Refresh</span>
                  </button>
                </div>
              </div>

              {/* PART 3: 4 Key Financial Metrics */}
              <MetricCards summary={summary} isLoading={isLoading} />

              {/* PART 4: Financial Charts (Monthly Trends & Category Breakdown) */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Monthly Inflow vs Outflow Visualizer (2 Columns on Large Screens) */}
                <div className="lg:col-span-2">
                  <MonthlyChart
                    data={summary?.monthly_trends || []}
                    isLoading={isLoading}
                  />
                </div>

                {/* Spending by Category Breakdown (1 Column on Large Screens) */}
                <div className="lg:col-span-1">
                  <CategoryBreakdown
                    categories={summary?.top_categories || []}
                    totalExpenses={summary?.total_expenses || 0}
                    isLoading={isLoading}
                  />
                </div>
              </div>

              {/* PART 5: Recent Transactions Ledger */}
              <RecentTransactions
                transactions={recentTransactions}
                isLoading={isLoading}
                onViewAll={() => setCurrentTab('transactions')}
              />

              {/* Stage 4A Active Assistant Quick Launch Banner */}
              <div className="p-6 rounded-2xl border border-[#E6E2D8] dark:border-[#1c3619] bg-white/90 dark:bg-[#10210e]/90 shadow-2xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2 text-xs font-bold text-[#15370D] dark:text-[#E5CD82]">
                    <Sparkles className="w-4 h-4 text-[#E5CD82]" />
                    <span>Stage 4A Active · Conversational Financial AI Assistant</span>
                  </div>
                  <p className="text-xs text-[#5C6C58] dark:text-[#95A890] max-w-2xl">
                    Ask natural-language questions about your spending, monthly trends, top merchants, subscriptions, and anomalies grounded in your verified IBM Db2 ledger.
                  </p>
                </div>

                <div className="flex items-center space-x-2 shrink-0 flex-wrap gap-y-2">
                  <button
                    onClick={() => setCurrentTab('insights')}
                    className="inline-flex items-center space-x-1.5 px-3.5 py-2 rounded-xl border border-[#728E6D]/40 bg-[#f5f7f4] dark:bg-[#162a14] text-[#15370D] dark:text-[#FFF2B4] text-xs font-semibold hover:bg-[#e8ede6] dark:hover:bg-[#1d361a] transition-all shadow-xs"
                  >
                    <LineChart className="w-3.5 h-3.5 text-[#728E6D] dark:text-[#E5CD82]" />
                    <span>Financial Insights</span>
                  </button>
                  <button
                    onClick={() => setCurrentTab('import')}
                    className="inline-flex items-center space-x-1.5 px-3.5 py-2 rounded-xl border border-[#D8D2C4] dark:border-[#244220] bg-[#FAF8F3] dark:bg-[#162a14] text-[#15370D] dark:text-[#FFF2B4] text-xs font-semibold hover:bg-white dark:hover:bg-[#1d361a] transition-all shadow-xs"
                  >
                    <UploadCloud className="w-3.5 h-3.5 text-[#728E6D] dark:text-[#E5CD82]" />
                    <span>Import CSV</span>
                  </button>
                  <button
                    onClick={() => setCurrentTab('anomalies')}
                    className="inline-flex items-center space-x-1.5 px-3.5 py-2 rounded-xl border border-[#E5CD82]/60 bg-[#fdfbf6] dark:bg-[#1f2a17] text-[#15370D] dark:text-[#E5CD82] text-xs font-semibold hover:bg-[#faf4e4] dark:hover:bg-[#28381e] transition-all shadow-xs"
                  >
                    <AlertTriangle className="w-3.5 h-3.5 text-[#E5CD82]" />
                    <span>Anomaly Intel</span>
                  </button>
                  <button
                    onClick={() => setCurrentTab('search')}
                    className="inline-flex items-center space-x-1.5 px-3.5 py-2 rounded-xl border border-[#D8D2C4] dark:border-[#244220] bg-white dark:bg-[#122410] text-[#152912] dark:text-[#F5F7F2] text-xs font-semibold hover:bg-[#FAF8F3] dark:hover:bg-[#1a3317] transition-all shadow-xs"
                  >
                    <Search className="w-3.5 h-3.5 text-[#728E6D]" />
                    <span>Semantic Search</span>
                  </button>
                  <button
                    onClick={() => setCurrentTab('assistant')}
                    className="inline-flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-[#15370D] text-[#FFF2B4] hover:bg-[#1f4e14] text-xs font-bold shadow-xs hover:scale-[1.02] active:scale-[0.98] transition-all"
                  >
                    <Bot className="w-3.5 h-3.5 text-[#E5CD82]" />
                    <span>Launch AI Assistant</span>
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>

        {/* Authenticated Application Footer */}
        <footer className="border-t border-[#E6E2D8] dark:border-[#1c3619] bg-white dark:bg-[#0b160a] py-6 text-xs text-[#728E6D] dark:text-[#95A890]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
            <div className="flex items-center space-x-2">
              <Database className="w-3.5 h-3.5 text-[#728E6D] dark:text-[#E5CD82]" />
              <span className="font-medium text-[#152912] dark:text-[#F5F7F2]">
                IBM Db2Hack 2026 · FinSight AI Financial Command Center
              </span>
            </div>
            <div className="flex items-center space-x-3 font-mono text-[11px] text-[#5C6C58] dark:text-[#95A890]">
              <span>Db2 Linux/x86_64 12.1.5.0</span>
              <span>·</span>
              <span>Zero Client Tokens</span>
              <span>·</span>
              <span>Strict Tenant Scoping</span>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
};
