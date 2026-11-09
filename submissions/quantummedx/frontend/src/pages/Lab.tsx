import { useCallback, useEffect, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, Dataset, errText, Result } from "../api";

const f4 = (x: number | null) => (x == null ? "n/a" : x.toFixed(4));

export default function Lab() {
  const [datasets, setDatasets] = useState<Dataset[]>([]); const [ds, setDs] = useState<number | "">("");
  const [results, setResults] = useState<Result[]>([]); const [err, setErr] = useState(""); const [msg, setMsg] = useState("");
  const [algo, setAlgo] = useState("logistic_regression"); const [k, setK] = useState(8);
  const [qubits, setQubits] = useState(4); const [iters, setIters] = useState(30);
  const [busy, setBusy] = useState(""); const [diagram, setDiagram] = useState(""); const timer = useRef<number>();

  useEffect(() => { api.get("/api/datasets").then((r) => { setDatasets(r.data); if (r.data[0]) setDs(r.data[0].dataset_id); }).catch((e) => setErr(errText(e))); return () => clearInterval(timer.current); }, []);
  const refresh = useCallback(() => ds === "" ? Promise.resolve() :
    api.get(`/api/dashboard/model-comparison?dataset_id=${ds}`).then((r) => setResults(r.data.results)).catch((e) => setErr(errText(e))), [ds]);
  useEffect(() => { setResults([]); setDiagram(""); refresh(); }, [refresh]);

  async function runClassical() {
    setErr(""); setMsg(""); setBusy("classical");
    try { await api.post("/api/models/classical/train", { dataset_id: ds, algorithm: algo, k_features: k }); await refresh(); setMsg("Classical experiment saved."); }
    catch (x) { setErr(errText(x)); } finally { setBusy(""); }
  }
  async function runQuantum() {
    setErr(""); setMsg("Quantum experiment is running on the simulator. This can take a minute."); setBusy("quantum");
    try {
      const { data } = await api.post("/api/models/quantum/train", { dataset_id: ds, n_qubits: qubits, maxiter: iters });
      timer.current = window.setInterval(async () => {
        try {
          const r = (await api.get(data.poll)).data;
          if (r.status === "RUNNING") return;
          clearInterval(timer.current); setBusy("");
          if (r.status === "COMPLETED") { setMsg("Quantum experiment finished."); setDiagram(r.extra?.quantum?.diagram ?? ""); await refresh(); }
          else { setMsg(""); setErr(`Quantum experiment failed: ${r.error_message ?? "unknown error"}`); }
        } catch (x) { clearInterval(timer.current); setBusy(""); setErr(errText(x)); }
      }, 2500);
    } catch (x) { setMsg(""); setErr(errText(x)); setBusy(""); }
  }
  const chart = results.map((r) => ({ name: `${r.algorithm} #${r.experiment_id}`, Accuracy: r.accuracy, F1: r.f1_score }));
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Experiments</h1>
      {datasets.length === 0 ? <p className="text-mute text-sm">Upload a dataset first.</p> : (<>
        <label className="text-sm block max-w-sm">Dataset<select className="field mt-1" value={ds} onChange={(e) => setDs(Number(e.target.value))}>
          {datasets.map((d) => <option key={d.dataset_id} value={d.dataset_id}>{d.name}</option>)}</select></label>
        <div className="grid md:grid-cols-2 gap-4">
          <section className="bg-panel border border-line rounded-lg p-4 space-y-3">
            <h2 className="font-medium">Classical model</h2>
            <label className="text-sm block">Algorithm<select className="field mt-1" value={algo} onChange={(e) => setAlgo(e.target.value)}>
              <option value="logistic_regression">Logistic regression</option><option value="random_forest">Random forest</option><option value="svm">Support vector machine</option></select></label>
            <label className="text-sm block">Features kept<input className="field mt-1" type="number" min={2} max={100} value={k} onChange={(e) => setK(Number(e.target.value))} /></label>
            <button className="btn" disabled={!!busy || ds === ""} onClick={runClassical}>{busy === "classical" ? "Training" : "Run classical experiment"}</button>
          </section>
          <section className="bg-panel border border-quantum/60 rounded-lg p-4 space-y-3">
            <h2 className="font-medium">Quantum classifier (simulator)</h2>
            <label className="text-sm block">Qubits (2 to 6)<input className="field mt-1" type="number" min={2} max={6} value={qubits} onChange={(e) => setQubits(Number(e.target.value))} /></label>
            <label className="text-sm block">Optimizer iterations<input className="field mt-1" type="number" min={5} max={200} value={iters} onChange={(e) => setIters(Number(e.target.value))} /></label>
            <button className="btn btn-q" disabled={!!busy || ds === ""} onClick={runQuantum}>{busy === "quantum" ? "Running on simulator" : "Run quantum experiment"}</button>
          </section>
        </div>
        {msg && <p role="status" className="text-sm text-cyan">{msg}</p>}
        {err && <p role="alert" className="text-sm text-bad">{err}</p>}
        <section className="space-y-3">
          <h2 className="font-medium">Stored results for this dataset</h2>
          {results.length === 0 ? <p className="text-mute text-sm">No completed experiments yet. Run one above.</p> : (<>
            <div className="overflow-x-auto bg-panel border border-line rounded-lg"><table className="w-full text-sm">
              <thead className="text-mute text-left"><tr><th className="p-3">Model</th><th>Type</th><th>Accuracy</th><th>Precision</th><th>Recall</th><th>F1</th><th>ROC-AUC</th><th>Train (s)</th></tr></thead>
              <tbody>{results.map((r) => <tr key={r.experiment_id} className="border-t border-line"><td className="p-3">{r.algorithm} #{r.experiment_id}</td>
                <td className={r.model_family === "QUANTUM" ? "text-quantum" : ""}>{r.model_family.toLowerCase()}</td><td>{f4(r.accuracy)}</td><td>{f4(r.precision_score)}</td><td>{f4(r.recall)}</td><td>{f4(r.f1_score)}</td><td>{f4(r.roc_auc)}</td><td>{r.train_seconds}</td></tr>)}</tbody></table></div>
            <div className="h-64 bg-panel border border-line rounded-lg p-3"><ResponsiveContainer><BarChart data={chart}><CartesianGrid stroke="#26334f" /><XAxis dataKey="name" stroke="#94a3b8" fontSize={11} /><YAxis domain={[0, 1]} stroke="#94a3b8" fontSize={11} /><Tooltip contentStyle={{ background: "#19243b", border: "1px solid #26334f" }} /><Legend />
              <Bar dataKey="Accuracy" fill="#3978f6" /><Bar dataKey="F1" fill="#8b5cf6" /></BarChart></ResponsiveContainer></div>
            <p className="text-xs text-mute">These numbers are read from IBM Db2. One small simulator run does not show that quantum models are better or worse in general.</p>
          </>)}
        </section>
        {diagram && <section className="space-y-2"><h2 className="font-medium">Quantum circuit (last run)</h2><pre className="bg-panel border border-line rounded-lg p-3 text-[11px] leading-tight overflow-x-auto font-mono">{diagram}</pre></section>}
      </>)}
    </div>
  );
}
