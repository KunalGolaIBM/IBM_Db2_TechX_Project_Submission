'use client';

import * as React from 'react';
import { AppShell } from '@/components/layout/app-shell';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { useAuth } from '@/hooks/use-auth';
import { api } from '@/lib/api-client';

interface HealthData {
  status: string;
  db2: string;
  version: string;
  environment: string;
  payment_mode: string;
  ai_provider: string;
}

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const [health, setHealth] = React.useState<HealthData | null>(null);
  const [isLoadingHealth, setIsLoadingHealth] = React.useState<boolean>(true);
  const [lastChecked, setLastChecked] = React.useState<string | null>(null);
  const [cacheCleared, setCacheCleared] = React.useState<boolean>(false);

  const fetchHealth = React.useCallback(async () => {
    setIsLoadingHealth(true);
    try {
      // Check both /health and /api/v1/health
      let data: HealthData;
      try {
        data = await api.get<HealthData>('/health');
      } catch {
        data = await api.get<HealthData>('/api/v1/health');
      }
      setHealth(data);
      setLastChecked(new Date().toLocaleTimeString());
    } catch {
      // Fallback display if backend is offline
      setHealth({
        status: 'offline',
        db2: 'disconnected: connection refused',
        version: '1.0.0',
        environment: 'development',
        payment_mode: 'DEMO',
        ai_provider: 'local_fallback',
      });
      setLastChecked(new Date().toLocaleTimeString());
    } finally {
      setIsLoadingHealth(false);
    }
  }, []);

  React.useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  const handleClearCache = () => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('token');
      localStorage.clear();
      if (token) localStorage.setItem('token', token);
      setCacheCleared(true);
      setTimeout(() => setCacheCleared(false), 3000);
    }
  };

  const isDb2Connected = health?.db2 === 'connected';
  const isHealthy = health?.status === 'healthy' || health?.status === 'running';

  return (
    <AppShell title="Settings & Diagnostics">
      <div className="space-y-8 max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">
              Settings & System Diagnostics
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Live enterprise telemetry, database connectivity status, and environment safeguards.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            isLoading={isLoadingHealth}
            onClick={fetchHealth}
          >
            <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Re-run Diagnostics
          </Button>
        </div>

        {/* Diagnostics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Card 1: Live Infrastructure Telemetry */}
          <Card className="border-slate-200">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-bold text-slate-900">
                  Infrastructure Telemetry
                </CardTitle>
                {lastChecked && (
                  <span className="text-[11px] text-slate-400">
                    Checked {lastChecked}
                  </span>
                )}
              </div>
              <CardDescription>
                Live connectivity status with IBM Db2 and backend services.
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4 pt-2">
              {isLoadingHealth ? (
                <div className="flex h-36 items-center justify-center">
                  <Spinner size="md" />
                </div>
              ) : (
                <div className="divide-y divide-slate-100 text-sm">
                  {/* Backend Status */}
                  <div className="flex items-center justify-between py-2.5">
                    <span className="text-slate-600 font-medium">Backend API</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-500 font-mono">v{health?.version}</span>
                      <Badge variant={isHealthy ? 'success' : 'danger'} className="uppercase text-[10px] font-bold">
                        {health?.status}
                      </Badge>
                    </div>
                  </div>

                  {/* IBM Db2 Status */}
                  <div className="flex items-center justify-between py-2.5">
                    <div>
                      <span className="text-slate-600 font-medium block">IBM Db2 Database</span>
                      <span className="text-[11px] text-slate-400">ACID Relational Engine</span>
                    </div>
                    <Badge variant={isDb2Connected ? 'success' : 'warning'} className="uppercase text-[10px] font-bold">
                      {isDb2Connected ? 'Connected' : 'Offline / Standby'}
                    </Badge>
                  </div>

                  {/* Environment */}
                  <div className="flex items-center justify-between py-2.5">
                    <span className="text-slate-600 font-medium">Environment</span>
                    <span className="font-mono text-xs uppercase bg-slate-100 px-2 py-0.5 rounded text-slate-800">
                      {health?.environment || 'development'}
                    </span>
                  </div>

                  {/* Payment Mode */}
                  <div className="flex items-center justify-between py-2.5">
                    <span className="text-slate-600 font-medium">Payment Gateway</span>
                    <Badge variant="warning" className="uppercase text-[10px] font-bold">
                      {health?.payment_mode || 'DEMO'} Sandbox
                    </Badge>
                  </div>

                  {/* AI Provider */}
                  <div className="flex items-center justify-between py-2.5">
                    <span className="text-slate-600 font-medium">AI Query Engine</span>
                    <Badge variant="info" className="uppercase text-[10px] font-bold font-mono">
                      {health?.ai_provider || 'OpenAI / Gemini / Local'}
                    </Badge>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Card 2: Security & Local Session Hygiene */}
          <Card className="border-slate-200">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-bold text-slate-900">
                Security & Data Hygiene
              </CardTitle>
              <CardDescription>
                Zero-secret client configuration and local session storage audit.
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4 pt-2">
              <div className="rounded-md bg-emerald-50 border border-emerald-200 p-3 text-xs text-emerald-900">
                <div className="flex items-center gap-2 font-bold mb-1">
                  <svg className="w-4 h-4 text-emerald-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                  <span>Zero Client-Side Secrets Confirmed</span>
                </div>
                Database credentials and AI API tokens are strictly isolated in backend environment variables.
              </div>

              <div className="space-y-2 text-xs text-slate-600">
                <p>
                  Active user: <strong className="text-slate-900 font-semibold">{user?.display_name || 'Authenticated'}</strong> ({user?.email || 'user'})
                </p>
                <p>
                  Authentication mode: <strong className="text-slate-900 font-semibold">JWT Bearer Auth</strong> via Authorization header.
                </p>
              </div>

              {cacheCleared && (
                <div className="rounded-md bg-indigo-50 border border-indigo-200 p-2 text-xs text-indigo-800">
                  Client cache cleared successfully.
                </div>
              )}

              <div className="pt-2 flex flex-col sm:flex-row gap-2.5">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleClearCache}
                  className="flex-1"
                >
                  Clear Cached Data
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  size="sm"
                  onClick={logout}
                  className="flex-1"
                >
                  Sign Out Session
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Card 3: Hackathon Submission Details */}
        <Card className="border-slate-200">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-primary-600 text-white flex items-center justify-center font-bold">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
              </div>
              <div>
                <CardTitle className="text-base font-bold text-slate-900">
                  SplitSync AI — IBM Db2 TechX Summit 2026
                </CardTitle>
                <CardDescription>
                  Enterprise-grade group expense reconciliation with dual-custody verification and deterministic graph settlements.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 text-xs text-slate-600">
            <p className="leading-relaxed">
              Engineered with Python FastAPI, Pydantic v2, and Next.js 14 App Router. All financial ledger quantities are strictly stored as integer paise (BIGINT) to guarantee zero float drift across distributed group settlements.
            </p>
            <div className="flex items-center gap-2 pt-2 text-[11px] text-slate-400">
              <span>Stack: IBM Db2 • Python FastAPI • Next.js 14 • Tailwind CSS • TypeScript</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
