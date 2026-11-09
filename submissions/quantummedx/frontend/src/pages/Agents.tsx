import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, Dataset, errText } from "../api";

const color = (s: string) => (s === "COMPLETED" ? "text-ok" : s === "FAILED" ? "text-bad" : "text-warn");

export default function Agents() {
  const [datasets, setDatasets] = useState<Dataset[]>([]); const [ds, setDs] = useState<number | "">("");
  const [mode, setMode] = useState("DETERMINISTIC"); const [runs, setRuns] = useState<any[]>([]);
  const [sel, setSel] = useState<number | null>(null); const [acts, setActs] = useState<any[]>([]);
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false); const timer = useRef<number>();

  const loadRuns = useCallback(() => api.get("/api/agents/runs").then((r) => setRuns(r.data)).catch((e) => setErr(errText(e))), []);
  useEffect(() => { api.get("/api/datasets").then((r) => { setDatasets(r.data); if (r.data[0]) setDs(r.data[0].dataset_id); }); loadRuns(); return () => clearInterval(timer.current); }, [loadRuns]);
  useEffect(() => {
    clearInterval(timer.current); if (sel == null) return;
    const tick = async () => {
      try { setActs((await api.get(`/api/agents/activity/${sel}`)).data); const run = (await api.get(`/api/agents/runs/${sel}`)).data;
        if (run.status !== "RUNNING") { clearInterval(timer.current); loadRuns(); } } catch (x) { clearInterval(timer.current); setErr(errText(x)); }
    };
    tick(); timer.current = window.setInterval(tick, 2500);
  }, [sel, loadRuns]);

  async function start() {
    setErr(""); setBusy(true);
    try { const { data } = await api.post("/api/agents/run", { dataset_id: ds, mode }); await loadRuns(); setSel(data.run_id); }
    catch (x) { setErr(errText(x)); } finally { setBusy(false); }
  }
  const current = runs.find((r) => r.run_id === sel);
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">AI agents</h1>
      <p className="text-sm text-mute max-w-prose">Five agents check the data, find patterns, train classical models, run the quantum classifier and write a verified report. Each tool call is recorded in Db2.</p>
      <div className="bg-panel border border-line rounded-lg p-4 grid gap-3 md:grid-cols-[1fr_1fr_auto] items-end">
        <label className="text-sm">Dataset<select className="field mt-1" value={ds} onChange={(e) => setDs(Number(e.target.value))}>{datasets.map((d) => <option key={d.dataset_id} value={d.dataset_id}>{d.name}</option>)}</select></label>
        <label className="text-sm">Mode<select className="field mt-1" value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="DETERMINISTIC">Tool pipeline (no LLM)</option><option value="CREWAI">CrewAI agents (needs LLM key on the server)</option></select></label>
        <button className="btn" disabled={busy || ds === ""} onClick={start}>{busy ? "Starting" : "Start run"}</button>
      </div>
      {err && <p role="alert" className="text-sm text-bad">{err}</p>}
      <div className="grid md:grid-cols-[260px_1fr] gap-4">
        <section><h2 className="font-medium mb-2">Runs</h2>
          {runs.length === 0 ? <p className="text-mute text-sm">No runs yet.</p> : <ul className="space-y-1">{runs.map((r) => (
            <li key={r.run_id}><button onClick={() => setSel(r.run_id)} className={`w-full text-left rounded-md px-3 py-2 text-sm border ${sel === r.run_id ? "bg-lift border-quantum" : "border-line"}`}>
              Run #{r.run_id} <span className={color(r.status)}>{r.status.toLowerCase()}</span><div className="text-xs text-mute">{r.mode === "CREWAI" ? "CrewAI" : "tool pipeline"}</div></button></li>))}</ul>}
        </section>
        <section><h2 className="font-medium mb-2">Activity</h2>
          {sel == null ? <p className="text-mute text-sm">Select or start a run to see what each agent did.</p> : acts.length === 0 ? <p className="text-mute text-sm">Waiting for the first agent step.</p> : (
            <ol className="space-y-2 border-l border-line pl-4">{acts.map((a) => (
              <li key={a.activity_id}><div className="text-sm"><span className="font-medium">{a.agent_name}</span> <span className="text-mute">called {a.tool_name}</span> <span className={color(a.status)}>{a.status.toLowerCase()}</span></div>
                {a.error_message && <p className="text-xs text-bad">{a.error_message}</p>}
                {a.output_summary && <details className="text-xs text-mute"><summary className="cursor-pointer">Tool output</summary><pre className="font-mono whitespace-pre-wrap break-words mt-1">{a.output_summary.slice(0, 1200)}</pre></details>}</li>))}</ol>)}
          {current?.status === "COMPLETED" && <p className="mt-3 text-sm">Run finished. <Link className="text-cyan underline" to="/reports">Open the report</Link></p>}
          {current?.status === "FAILED" && <p className="mt-3 text-sm text-bad">This run failed. Check the last activity above for the reason.</p>}
        </section>
      </div>
    </div>
  );
}
