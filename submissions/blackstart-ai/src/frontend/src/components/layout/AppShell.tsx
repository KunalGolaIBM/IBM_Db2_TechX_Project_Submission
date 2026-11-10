import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { CheckCircle2, X, XCircle } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useDashboard } from '../../state/DashboardContext';
import { SWAGGER_URL } from '../../services/api';

function Banner() {
  const { banner, dismissBanner } = useDashboard();

  if (!banner) return null;

  const success = banner.tone === 'success';

  return (
    <div
      className={`mt-4 flex w-full animate-fade-up items-start gap-3 rounded-xl border px-4 py-3 ${
        success
          ? 'border-emerald-400/30 bg-emerald-500/[0.07]'
          : 'border-red-500/35 bg-red-500/[0.07]'
      }`}
      role="status"
      aria-live="polite"
    >
      {success ? (
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
      ) : (
        <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-300" />
      )}
      <div className="min-w-0 flex-1">
        <p
          className={`text-sm font-semibold ${success ? 'text-emerald-200' : 'text-red-200'}`}
        >
          {banner.title}
        </p>
        {banner.detail ? (
          <p className="mt-0.5 text-xs leading-relaxed text-slate-400">{banner.detail}</p>
        ) : null}
      </div>
      <button
        type="button"
        onClick={dismissBanner}
        aria-label="Dismiss notification"
        className="rounded-md p-1 text-slate-500 transition hover:bg-white/5 hover:text-slate-200"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

function Footer() {
  return (
    <footer className="border-t border-white/[0.06] px-4 py-5 sm:px-6 lg:px-8">
      <div className="flex w-full flex-col gap-3 text-[11px] text-slate-600 sm:flex-row sm:items-center sm:justify-between">
        <p>
          <span className="font-display font-semibold text-slate-500">BLACKSTART AI</span>{' '}
          · Autonomous grid intelligence · IBM Db2 + FastAPI + LangGraph
        </p>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <span className="uppercase tracking-[0.14em]">Advisory only</span>
          <span className="uppercase tracking-[0.14em]">Simulated thresholds</span>
          <a
            href={SWAGGER_URL}
            target="_blank"
            rel="noreferrer"
            className="text-accent/80 transition hover:text-accent"
          >
            API docs ↗
          </a>
        </div>
      </div>
    </footer>
  );
}

export function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'auto' });
    setSidebarOpen(false);
  }, [pathname]);

  return (
    <div className="flex min-h-screen">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col lg:pl-[264px]">
        <TopBar onMenu={() => setSidebarOpen(true)} />
        <div className="px-4 sm:px-6 lg:px-8">
          <Banner />
        </div>
        <main className="flex-1 px-4 pb-10 pt-6 sm:px-6 lg:px-8">
          <div className="w-full">
            <Outlet />
          </div>
        </main>
        <Footer />
      </div>
    </div>
  );
}
