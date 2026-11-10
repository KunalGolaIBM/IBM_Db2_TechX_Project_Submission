import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { api, describeApiError } from '../services/api';
import type {
  AnalysisResult,
  AnalysisState,
  Db2Status,
  GridOverview,
  HealthResponse,
  LoadState,
} from '../types/api';

export interface BannerMessage {
  id: number;
  tone: 'success' | 'error' | 'info';
  title: string;
  detail?: string;
}

interface DashboardContextValue {
  overview: GridOverview | null;
  overviewState: LoadState;
  overviewError: string | null;
  overviewFetchedAt: Date | null;

  health: HealthResponse | null;
  db2: Db2Status | null;
  statusState: LoadState;
  statusError: string | null;
  apiLatencyMs: number | null;

  analysis: AnalysisResult | null;
  analysisState: AnalysisState;
  analysisError: string | null;
  lastAnalysisAt: Date | null;
  analysisDurationMs: number | null;

  banner: BannerMessage | null;
  refreshOverview: () => Promise<void>;
  refreshStatus: () => Promise<void>;
  refreshAll: () => Promise<void>;
  runAnalysis: () => Promise<void>;
  dismissBanner: () => void;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

const STATUS_POLL_INTERVAL_MS = 45000;

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [overview, setOverview] = useState<GridOverview | null>(null);
  const [overviewState, setOverviewState] = useState<LoadState>('loading');
  const [overviewError, setOverviewError] = useState<string | null>(null);
  const [overviewFetchedAt, setOverviewFetchedAt] = useState<Date | null>(null);

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [db2, setDb2] = useState<Db2Status | null>(null);
  const [statusState, setStatusState] = useState<LoadState>('loading');
  const [statusError, setStatusError] = useState<string | null>(null);
  const [apiLatencyMs, setApiLatencyMs] = useState<number | null>(null);

  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [analysisState, setAnalysisState] = useState<AnalysisState>('idle');
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [lastAnalysisAt, setLastAnalysisAt] = useState<Date | null>(null);
  const [analysisDurationMs, setAnalysisDurationMs] = useState<number | null>(null);

  const [banner, setBanner] = useState<BannerMessage | null>(null);

  const analysisInFlight = useRef(false);
  const statusInFlight = useRef(false);
  const overviewInFlight = useRef(false);
  const bannerId = useRef(0);

  const showBanner = useCallback((tone: BannerMessage['tone'], title: string, detail?: string) => {
    bannerId.current += 1;
    setBanner({ id: bannerId.current, tone, title, detail });
  }, []);

  const dismissBanner = useCallback(() => setBanner(null), []);

  const refreshOverview = useCallback(async () => {
    if (overviewInFlight.current) return;
    overviewInFlight.current = true;
    const isInitial = overview === null;
    if (isInitial) setOverviewState('loading');
    try {
      const data = await api.getOverview();
      setOverview(data);
      setOverviewFetchedAt(new Date());
      setOverviewError(null);
      setOverviewState('success');
    } catch (error) {
      const message = describeApiError(error);
      setOverviewError(message);
      setOverviewState('error');
    } finally {
      overviewInFlight.current = false;
    }
  }, [overview]);

  const refreshStatus = useCallback(async () => {
    if (statusInFlight.current) return;
    statusInFlight.current = true;
    try {
      const started = performance.now();
      const [healthResult, db2Result] = await Promise.all([
        api.getHealth(),
        api.getDb2Status(),
      ]);
      const elapsed = Math.round(performance.now() - started);
      setHealth(healthResult);
      setDb2(db2Result);
      setApiLatencyMs(elapsed);
      setStatusError(null);
      setStatusState('success');
    } catch (error) {
      setStatusError(describeApiError(error));
      setStatusState('error');
    } finally {
      statusInFlight.current = false;
    }
  }, []);

  const refreshAll = useCallback(async () => {
    await Promise.all([refreshOverview(), refreshStatus()]);
  }, [refreshOverview, refreshStatus]);

  const runAnalysis = useCallback(async () => {
    if (analysisInFlight.current) return;
    analysisInFlight.current = true;
    setAnalysisState('running');
    setAnalysisError(null);
    const started = performance.now();
    try {
      const result = await api.runAnalysis();
      const duration = Math.round(performance.now() - started);
      setAnalysis(result);
      setAnalysisDurationMs(duration);
      setLastAnalysisAt(new Date());
      setAnalysisState('success');
      showBanner(
        'success',
        'Intelligence analysis complete',
        `${result.agents_executed.length} agents executed in ${duration} ms · grid overview refreshed · data source ${result.data_source}`,
      );
      await refreshOverview();
    } catch (error) {
      const message = describeApiError(error);
      setAnalysisError(message);
      setAnalysisState('error');
      showBanner('error', 'Analysis failed', message);
    } finally {
      analysisInFlight.current = false;
    }
  }, [refreshOverview, showBanner]);

  useEffect(() => {
    void refreshAll();
    // Initial load only; polling below keeps connection status fresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void refreshStatus();
    }, STATUS_POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [refreshStatus]);

  const value = useMemo<DashboardContextValue>(
    () => ({
      overview,
      overviewState,
      overviewError,
      overviewFetchedAt,
      health,
      db2,
      statusState,
      statusError,
      apiLatencyMs,
      analysis,
      analysisState,
      analysisError,
      lastAnalysisAt,
      analysisDurationMs,
      banner,
      refreshOverview,
      refreshStatus,
      refreshAll,
      runAnalysis,
      dismissBanner,
    }),
    [
      overview,
      overviewState,
      overviewError,
      overviewFetchedAt,
      health,
      db2,
      statusState,
      statusError,
      apiLatencyMs,
      analysis,
      analysisState,
      analysisError,
      lastAnalysisAt,
      analysisDurationMs,
      banner,
      refreshOverview,
      refreshStatus,
      refreshAll,
      runAnalysis,
      dismissBanner,
    ],
  );

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}

export function useDashboard(): DashboardContextValue {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error('useDashboard must be used within a DashboardProvider');
  }
  return context;
}
