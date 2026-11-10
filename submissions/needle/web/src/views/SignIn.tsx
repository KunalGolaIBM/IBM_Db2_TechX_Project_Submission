import { useState, type FormEvent } from "react";
import { api, ApiError, type DemoUser, type Health, type Session } from "../api";
import { ErrorState } from "../components/ui";
import Steps from "../components/Steps";

const STEPS = [
  { obj: "CALL NEEDLE.TRIAGE_MODE", says: "Keyword rank (BM25 in plain SQL) and meaning rank (DiskANN vector index, FETCH APPROX), fused in one Db2 statement." },
  { obj: "CREATE PERMISSION", says: "Row access control decides which advisories your Db2 identity can read. Embargoed ones never leave Db2 for a junior analyst." },
  { obj: "FOR BUSINESS_TIME AS OF", says: "An exact package and version join over each service's deploy history says who is affected, and since when." },
];

export default function SignIn({ demo, demoUsers, health, onSignedIn }: {
  demo: boolean; demoUsers: DemoUser[]; health: Health | null; onSignedIn: (s: Session) => void;
}) {
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<ApiError | null>(null);

  const submit = async (e?: FormEvent, demoUser?: string) => {
    e?.preventDefault();
    setErr(null);
    if (!demoUser && (!user.trim() || !password)) {
      setErr(new ApiError(400, "login", "Enter your Db2 user ID and password."));
      return;
    }
    setBusy(demoUser ?? "form");
    try {
      const s = await api.login(demoUser ?? user.trim(), demoUser ? undefined : password);
      setPassword("");
      onSignedIn(s);
    } catch (x) {
      setErr(x as ApiError);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="grid gap-8 pt-2">
    <Steps current={1} />
    <div className="grid gap-10 lg:grid-cols-[minmax(0,1.15fr)_minmax(340px,440px)] lg:gap-16 lg:pt-6">
      <section className="max-w-[720px]">
        <h1 className="text-3xl font-semibold tracking-[-0.02em]">Which services does this advisory hit?</h1>
        <p className="mt-4 max-w-[60ch] text-md text-ink-2">
          Paste a security report, even a vague chat message with no CVE. NEEDLE searches the OSV Python advisories
          inside IBM Db2, shows only what your Db2 identity may see, and names the affected services.
        </p>
        <dl className="mt-10 border-t border-hair">
          {STEPS.map((s) => (
            <div key={s.obj} className="grid gap-1 border-b border-hair py-4 sm:grid-cols-[230px_minmax(0,1fr)] sm:gap-6">
              <dt className="font-mono text-[13px] font-semibold text-accent-strong">{s.obj}</dt>
              <dd className="text-sm text-ink-2">{s.says}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="signin-title" className="panel h-fit p-6">
        <h2 id="signin-title" className="text-lg font-semibold">{demo ? "Choose who you are" : "Sign in to Db2"}</h2>
        {demo ? (
          <>
            <p className="mt-1 text-sm text-mute">Three Db2 users with different row permissions. Start as the senior analyst, then switch in the top bar to see what changes.</p>
            <div className="mt-5 border-y border-hair">
              {demoUsers.map((u) => (
                <button key={u.user} onClick={() => submit(undefined, u.user)} disabled={!!busy}
                  className="group flex w-full items-center justify-between gap-4 border-b border-hair px-1 py-3 text-left transition-colors duration-150 last:border-b-0 hover:bg-ground disabled:opacity-60">
                  <span>
                    <span className="flex items-center gap-2 font-mono text-[13px] font-semibold">{u.user}
                      {u.user === "NDL_SENIOR" && <span className="rounded-[3px] bg-accent-wash px-1.5 py-[1px] font-sans text-[11px] font-semibold text-accent-strong">Start here</span>}
                    </span>
                    <span className="block text-xs text-mute">{u.role}</span>
                  </span>
                  <span className="text-sm font-medium text-accent-text group-hover:text-accent-strong">{busy === u.user ? "Signing in…" : "Continue →"}</span>
                </button>
              ))}
            </div>
          </>
        ) : (
          <form onSubmit={submit} className="mt-5 grid gap-4" autoComplete="on">
            <label className="grid gap-1.5">
              <span className="text-sm font-medium">Db2 user ID</span>
              <input className="field font-mono uppercase" value={user} onChange={(e) => setUser(e.target.value)}
                placeholder="e.g. NDL_JUNIOR" autoComplete="username" spellCheck={false} maxLength={30} name="user" />
            </label>
            <label className="grid gap-1.5">
              <span className="text-sm font-medium">Password</span>
              <input className="field" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password" name="password" />
            </label>
            <button className="btn btn-primary mt-1 w-full" disabled={busy === "form"}>{busy ? "Signing in…" : "Sign in"}</button>
            <p className="text-xs text-mute">
              Use a Db2 user from your setup, for example NDL_JUNIOR (its password is NDL_JUNIOR_PASSWORD in needle/.env).
              Row access control binds to this identity. The password goes to Db2 through this local server, stays in
              its memory for this session only, and is never written to disk or logs.
            </p>
          </form>
        )}
        {err && <div className="mt-4"><ErrorState kind={err.kind} message={err.message} /></div>}
        {health && !health.db.ok && !err && (
          <p className="mt-4 border-l-[3px] border-affected pl-3 text-xs text-ink-2">
            Db2 is not reachable ({health.db.detail}). Start Db2 and check DB2_HOST and DB2_PORT in .env.
          </p>
        )}
      </section>
    </div>
    </div>
  );
}
