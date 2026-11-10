import { useCallback, useEffect, useState } from "react";
import { api, ApiError, fmt, setToken, type Config, type Health, type Session } from "./api";
import { Dot } from "./components/ui";
import { initScroll, scrollTop } from "./lib/scroll";
import SignIn from "./views/SignIn";
import Triage, { useTriageState } from "./views/Triage";
import FindingView from "./views/Finding";
import HowItWorks from "./views/HowItWorks";
import Landing from "./views/Landing";

type View = "home" | "triage" | "finding" | "how";
const VIEWS: { id: View; label: string }[] = [
  { id: "home", label: "Overview" },
  { id: "triage", label: "Triage" },
  { id: "finding", label: "The finding" },
  { id: "how", label: "How it works" },
];
const viewFromHash = (): View => {
  const h = window.location.hash.replace(/^#\/?/, "");
  return (VIEWS.find((v) => v.id === h)?.id ?? "home") as View;
};

function Mark() {
  return (
    <svg width="24" height="24" viewBox="0 0 32 32" aria-hidden className="shrink-0">
      <rect width="32" height="32" rx="7" fill="#101213" />
      <circle cx="8.2" cy="23.8" r="3.1" fill="#19c3cf" />
      <path d="M7.2 24.8 L25.6 9.9 A2.25 2.25 0 0 0 22.1 6.4 Z" fill="#f3f7f9" />
      <rect x="-2.3" y="-0.6" width="4.6" height="1.2" rx="0.6" transform="translate(21.6 10.4) rotate(-45)" fill="#101213" />
    </svg>
  );
}

export default function App() {
  const [view, setView] = useState<View>(viewFromHash);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthErr, setHealthErr] = useState(false);
  const [config, setConfig] = useState<Config | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [switching, setSwitching] = useState(false);
  const [switchErr, setSwitchErr] = useState<ApiError | null>(null);
  const [autoRun, setAutoRun] = useState(false);
  const triage = useTriageState();

  useEffect(() => initScroll(), []);
  useEffect(() => { scrollTop(); }, [view]);

  useEffect(() => {
    const on = () => setView(viewFromHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);

  const loadHealth = useCallback(() => {
    api.health().then((h) => { setHealth(h); setHealthErr(false); }).catch(() => setHealthErr(true));
  }, []);
  useEffect(() => {
    loadHealth();
    api.config().then(setConfig).catch(() => setConfig(null));
    const t = window.setInterval(loadHealth, 15000);
    return () => window.clearInterval(t);
  }, [loadHealth]);

  const go = (v: View) => { window.location.hash = `/${v}`; setView(v); };

  const signedIn = (s: Session) => {
    setToken(s.token);
    setSession(s);
    triage.reset(); // results belong to the identity that ran them
  };
  const signOut = async () => {
    await api.logout().catch(() => undefined);
    setToken(null);
    setSession(null);
    triage.reset();
  };
  const switchTo = async (user: string, runAfter = false) => {
    if (!user || user === session?.user) return;
    setSwitching(true);
    setSwitchErr(null);
    try { const s = await api.login(user); setAutoRun(runAfter); signedIn(s); }
    catch (e) { setSwitchErr(e as ApiError); } finally { setSwitching(false); }
  };

  const demo = !!config?.demo_switcher;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-hair bg-ground/95 backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-[1600px] items-center gap-3 px-4 sm:gap-6 sm:px-6 lg:px-8">
          <a href="#/home" onClick={() => go("home")} className="flex items-center gap-2.5 text-ink no-underline">
            <Mark />
            <span className="hidden font-mono text-[15px] font-semibold tracking-[0.08em] sm:inline">NEEDLE</span>
          </a>
          <nav aria-label="Views" className="flex h-full min-w-0 items-stretch overflow-x-auto sm:gap-1">
            {VIEWS.map((v) => (
              <a key={v.id} href={`#/${v.id}`} onClick={() => go(v.id)} aria-current={view === v.id ? "page" : undefined}
                className={`relative flex items-center px-2 text-sm font-medium whitespace-nowrap sm:px-3 no-underline transition-colors duration-150 ${view === v.id ? "text-ink" : "text-mute hover:text-ink"}`}>
                {v.label}
                {view === v.id && <span className="absolute inset-x-3 bottom-0 h-[2px] bg-accent" />}
              </a>
            ))}
          </nav>
          <p className={`hidden min-w-0 truncate text-xs text-mute ${view === "home" ? "" : "xl:block"}`}>Permission-aware hybrid search for vulnerability triage, inside IBM Db2 12.1.5</p>
          <div className="ml-auto flex shrink-0 items-center gap-5">
            <div className="flex items-center gap-2.5 md:gap-4">
              <Dot ok={healthErr ? false : health ? health.db.ok : null} label={`Db2 ${health?.db.database ?? ""}`.trim()}
                detail={healthErr ? "API not reachable" : health?.db.detail} />
              <Dot ok={healthErr ? false : health ? health.ollama.ok : null} label="Ollama"
                detail={healthErr ? "API not reachable" : health ? `${health.ollama.detail}; ${health.ollama.embed_model} ${health.ollama.embed_ok ? "ready" : "missing"}, ${health.ollama.llm_model} ${health.ollama.llm_ok ? "ready" : "missing"}` : undefined} />
            </div>
            {session && !demo && (
              <div className="flex items-center gap-3">
                <IdentityChip user={session.user} visible={session.visible_docs} />
                <button className="text-sm text-mute hover:text-ink" onClick={signOut}>Sign out</button>
              </div>
            )}
            {demo && (
              <label className="flex items-center gap-2">
                <span className="sr-only">Demo identity</span>
                <select value={session?.user ?? ""} disabled={switching} onChange={(e) => switchTo(e.target.value)}
                  data-testid="demo-identity"
                  className="h-9 max-w-[9.5rem] rounded-[6px] border border-rule bg-paper pr-7 pl-2 font-mono text-[13px] font-semibold sm:max-w-none sm:pr-8 sm:pl-3">
                  <option value="" disabled>Pick a demo identity</option>
                  {config!.demo_users.map((u) => <option key={u.user} value={u.user}>{u.user}</option>)}
                </select>
              </label>
            )}
          </div>
        </div>
        {demo && (
          <div className="border-t border-amber/25 bg-amber-wash">
            <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-4 gap-y-0.5 px-4 py-1.5 text-xs text-amber sm:flex-nowrap sm:px-6 lg:px-8">
              <span className="shrink-0 font-mono font-semibold tracking-[0.02em]" data-testid="demo-badge">DEMO IDENTITY SWITCHER — NOT AUTHENTICATION</span>
              <span className="hidden min-w-0 truncate lg:inline">Passwords for these identities come from the server's .env. Default mode: sign in with your own Db2 user.</span>
              {switchErr && <span className="font-semibold text-affected">{switchErr.message}</span>}
              {session && <span className="ml-auto shrink-0 font-mono text-ink-2 num">{fmt.int(session.visible_docs)} advisories visible to {session.user}</span>}
            </div>
          </div>
        )}
      </header>

      {view === "home" && <Landing />}
      <main className={view === "home" ? "hidden" : "mx-auto max-w-[1600px] px-4 pt-6 pb-16 sm:px-6 lg:px-8"}>
        {view === "triage" && (
          session
            ? <Triage key={session.user} session={session} state={triage} demo={demo} autoRun={autoRun}
                onAutoRunDone={() => setAutoRun(false)} onSwitch={(u) => { window.scrollTo(0, 0); switchTo(u, true); }} />
            : <SignIn demo={demo} demoUsers={config?.demo_users ?? []} health={health} onSignedIn={signedIn} />
        )}
        {view === "finding" && <FindingView session={session} demo={demo} />}
        {view === "how" && <HowItWorks />}
      </main>
    </div>
  );
}

function IdentityChip({ user, visible }: { user: string; visible: number | null }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-[6px] border border-hair bg-paper py-1 pr-2.5 pl-1.5" data-testid="identity">
      <span className="rounded-[3px] bg-ink px-1.5 py-[1px] font-mono text-[12px] font-semibold text-paper">{user}</span>
      <span className="font-mono text-xs text-mute num">{fmt.int(visible)} visible</span>
    </span>
  );
}
