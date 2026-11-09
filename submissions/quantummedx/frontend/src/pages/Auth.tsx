import { FormEvent, useState } from "react";
import { Atom } from "lucide-react";
import { api, errText, setToken } from "../api";

export default function Auth({ onDone }: { onDone: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [f, setF] = useState({ username: "", email: "", password: "" });
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      if (mode === "register") await api.post("/api/auth/register", f);
      const { data } = await api.post("/api/auth/login", { username: f.username, password: f.password });
      setToken(data.access_token); onDone();
    } catch (x) { setErr(errText(x)); } finally { setBusy(false); }
  }
  return (
    <div className="min-h-screen grid md:grid-cols-2">
      <div className="hidden md:flex flex-col justify-center gap-4 p-14 bg-rail border-r border-line">
        <Atom className="text-quantum" size={40} />
        <h1 className="text-3xl font-semibold">QuantumMedX</h1>
        <p className="text-mute max-w-md leading-relaxed">Compare classical machine learning with a quantum classifier on healthcare datasets. AI agents coordinate the work and every result is stored in IBM Db2.</p>
      </div>
      <form onSubmit={submit} className="flex flex-col justify-center gap-4 p-8 md:p-14 max-w-md w-full mx-auto">
        <h2 className="text-xl font-semibold">{mode === "login" ? "Sign in" : "Create account"}</h2>
        <label className="text-sm">Username<input className="field mt-1" value={f.username} onChange={set("username")} required minLength={3} autoComplete="username" /></label>
        {mode === "register" && <label className="text-sm">Email<input className="field mt-1" type="email" value={f.email} onChange={set("email")} required autoComplete="email" /></label>}
        <label className="text-sm">Password (8+ characters)<input className="field mt-1" type="password" value={f.password} onChange={set("password")} required minLength={8} autoComplete={mode === "login" ? "current-password" : "new-password"} /></label>
        {err && <p role="alert" className="text-bad text-sm">{err}</p>}
        <button className="btn" disabled={busy}>{busy ? "Working" : mode === "login" ? "Sign in" : "Create account"}</button>
        <button type="button" className="text-sm text-mute underline" onClick={() => { setMode(mode === "login" ? "register" : "login"); setErr(""); }}>
          {mode === "login" ? "Need an account? Create one" : "Have an account? Sign in"}
        </button>
      </form>
    </div>
  );
}
