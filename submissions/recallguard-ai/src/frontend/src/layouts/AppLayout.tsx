import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  Activity, BrainCircuit, ClipboardCheck, Database, FileSearch, FlaskConical, GitBranch, LayoutDashboard, Menu, Radar, Settings, ShieldCheck, Siren, X,
} from "lucide-react";
import { useHealth } from "@/hooks/queries";
import { useDemo } from "@/hooks/useDemo";
import { getRole, setRole } from "@/services/api";
import { Button } from "@/components/ui";
import { DemoPanel } from "@/components/DemoPanel";
import { cn } from "@/lib/utils";
import type { Role } from "@/types";

const NAV = [
  { to: "/", label: "Executive Dashboard", icon: LayoutDashboard, end: true },
  { to: "/incidents", label: "Incident Investigation", icon: Siren },
  { to: "/explorer", label: "Supply Chain Explorer", icon: GitBranch },
  { to: "/investigations", label: "AI Investigation Centre", icon: BrainCircuit },
  { to: "/recalls", label: "Recall Planning", icon: ClipboardCheck },
  { to: "/evidence", label: "Evidence Vault", icon: FileSearch },
  { to: "/monitoring", label: "Recall Monitoring", icon: Radar },
  { to: "/settings", label: "Settings", icon: Settings },
];

function EngineBadge() {
  const { data, isError } = useHealth();
  if (isError) return <span className="inline-flex items-center gap-1.5 rounded-md border border-red-500/40 bg-red-500/10 px-2 py-1 text-[11px] text-red-300"><Database className="size-3.5" />API offline</span>;
  if (!data) return null;
  const db2 = data.database.is_ibm_db2;
  return (
    <span title={data.database.warning ?? data.database.label}
      className={cn("inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-medium",
        db2 && data.database.connected ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300" : "border-amber-500/40 bg-amber-500/10 text-amber-300")}>
      <Database className="size-3.5" />
      {db2 ? (data.database.connected ? "IBM Db2 · connected" : "IBM Db2 · unreachable") : "DEV MODE · not Db2"}
    </span>
  );
}

function RoleSwitcher() {
  const qc = useQueryClient();
  const [role, setR] = useState<Role>(getRole());
  return (
    <label className="flex items-center gap-1.5 text-[11px] text-slate-400">
      <ShieldCheck className="size-3.5" />
      <span className="sr-only">Acting role</span>
      <select aria-label="Acting role" value={role} className="rounded-md border border-line bg-ink-900 px-1.5 py-1 text-[11px] text-slate-200"
        onChange={(e) => { const r = e.target.value as Role; setRole(r); setR(r); qc.invalidateQueries(); }}>
        <option value="viewer">Viewer</option>
        <option value="analyst">QA Analyst</option>
        <option value="recall_manager">Recall Manager</option>
        <option value="admin">Admin</option>
      </select>
    </label>
  );
}

export function AppLayout() {
  const [mobile, setMobile] = useState(false);
  const { run, running } = useDemo();
  const { data: health } = useHealth();
  const loc = useLocation();
  const nav = (
    <nav className="flex flex-col gap-0.5 p-3" aria-label="Main">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} onClick={() => setMobile(false)}
          className={({ isActive }) => cn("flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] transition-colors",
            isActive ? "bg-cyan-500/10 text-cyan-200 shadow-[inset_2px_0_0_#22d3ee]" : "text-slate-400 hover:bg-ink-800 hover:text-slate-100")}>
          <Icon className="size-4" />{label}
        </NavLink>
      ))}
    </nav>
  );
  return (
    <div className="flex min-h-full">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-line bg-ink-950/60 backdrop-blur lg:flex">
        <Brand />
        {nav}
        <div className="mt-auto space-y-2 p-4 text-[11px] text-slate-500">
          <div className="flex items-center gap-1.5"><Activity className="size-3.5 text-emerald-400" />Agents: {health?.ai.mode === "CREWAI_LLM" ? "CrewAI + LLM" : "deterministic fallback"}</div>
          <p>All notifications are <span className="text-amber-300">simulated</span>. Recalls require human approval.</p>
        </div>
      </aside>

      {mobile && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-ink-950/70" onClick={() => setMobile(false)} />
          <aside className="absolute left-0 top-0 h-full w-64 border-r border-line bg-ink-900">
            <div className="flex items-center justify-between pr-3"><Brand /><button aria-label="Close menu" onClick={() => setMobile(false)}><X className="size-5 text-slate-400" /></button></div>
            {nav}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center gap-2 border-b border-line bg-ink-950/75 px-4 py-2.5 backdrop-blur md:px-6">
          <button className="lg:hidden" aria-label="Open menu" onClick={() => setMobile(true)}><Menu className="size-5 text-slate-300" /></button>
          <div className="lg:hidden"><span className="text-sm font-semibold text-white">RecallGuard <span className="text-cyan-400">AI</span></span></div>
          <div className="ml-auto flex flex-wrap items-center justify-end gap-2">
            <EngineBadge />
            <RoleSwitcher />
            <Button variant="primary" size="sm" onClick={run} loading={running} data-testid="run-demo">
              {!running && <FlaskConical />}<span className="hidden sm:inline">Run Tomato Contamination Demo</span><span className="sm:hidden">Demo</span>
            </Button>
          </div>
        </header>
        {health && !health.database.is_ibm_db2 && (
          <div className="border-b border-amber-500/20 bg-amber-500/[0.06] px-4 py-1.5 text-center text-[11px] text-amber-200/90 md:px-6">
            DEV MODE — data is served by an embedded engine running the same Db2 SQL files. This is <b>not</b> a live IBM Db2 instance. Set <code className="mono">DB_MODE=db2</code> to connect.
          </div>
        )}
        <main key={loc.pathname} className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-5 md:px-6 md:py-6">
          <Outlet />
        </main>
      </div>
      <DemoPanel />
    </div>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-5 py-4">
      <img src="/favicon.svg" alt="" className="size-8" />
      <div>
        <p className="text-sm font-semibold leading-tight text-white">RecallGuard <span className="text-cyan-400">AI</span></p>
        <p className="text-[10px] leading-tight text-slate-500">Food-safety command centre</p>
      </div>
    </div>
  );
}
