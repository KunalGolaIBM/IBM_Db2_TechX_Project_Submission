import { FormEvent, useCallback, useEffect, useState } from "react";
import { Trash2, Upload } from "lucide-react";
import { api, Dataset, errText } from "../api";

export default function Datasets() {
  const [rows, setRows] = useState<Dataset[] | null>(null);
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null); const [target, setTarget] = useState("");
  const [sel, setSel] = useState<number | null>(null);
  const [analysis, setAnalysis] = useState<any>(null); const [preview, setPreview] = useState<any[]>([]);

  const load = useCallback(() => api.get("/api/datasets").then((r) => setRows(r.data)).catch((e) => setErr(errText(e))), []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (sel == null) return;
    setAnalysis(null);
    api.get(`/api/datasets/${sel}/analysis`).then((r) => setAnalysis(r.data)).catch((e) => setErr(errText(e)));
    api.get(`/api/datasets/${sel}/preview?rows=5`).then((r) => setPreview(r.data)).catch(() => setPreview([]));
  }, [sel]);

  async function upload(e: FormEvent) {
    e.preventDefault(); if (!file) return; setErr(""); setBusy(true);
    const fd = new FormData(); fd.append("file", file); fd.append("target_column", target); fd.append("source", "user upload");
    try { const { data } = await api.post("/api/datasets/upload", fd); setFile(null); setTarget(""); await load(); setSel(data.dataset_id); }
    catch (x) { setErr(errText(x)); } finally { setBusy(false); }
  }
  async function remove(id: number) {
    if (!window.confirm("Delete this dataset and its experiments?")) return;
    try { await api.delete(`/api/datasets/${id}`); if (sel === id) { setSel(null); setAnalysis(null); } load(); } catch (x) { setErr(errText(x)); }
  }
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Datasets</h1>
      {err && <p role="alert" className="text-bad text-sm">{err}</p>}
      <form onSubmit={upload} className="bg-panel border border-line rounded-lg p-4 grid gap-3 md:grid-cols-[1fr_200px_auto] items-end">
        <label className="text-sm">CSV file (max 10 MB)<input className="field mt-1" type="file" accept=".csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label>
        <label className="text-sm">Target column<input className="field mt-1" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="e.g. diagnosis" required /></label>
        <button className="btn flex items-center gap-2" disabled={!file || busy}><Upload size={16} />{busy ? "Uploading" : "Upload"}</button>
      </form>
      {rows === null ? <p className="text-mute text-sm">Loading datasets</p> : rows.length === 0 ? (
        <p className="text-mute text-sm">No datasets yet. Upload a CSV with a binary target column to begin.</p>
      ) : (
        <div className="overflow-x-auto bg-panel border border-line rounded-lg">
          <table className="w-full text-sm"><thead className="text-mute text-left"><tr><th className="p-3">Name</th><th>Rows</th><th>Columns</th><th>Duplicates</th><th>Target</th><th /></tr></thead>
            <tbody>{rows.map((d) => (
              <tr key={d.dataset_id} className={`border-t border-line ${sel === d.dataset_id ? "bg-lift" : ""}`}>
                <td className="p-3"><button className="underline" onClick={() => setSel(d.dataset_id)}>{d.name}</button></td>
                <td>{d.row_count}</td><td>{d.column_count}</td><td>{d.duplicate_rows}</td><td>{d.target_column ?? "-"}</td>
                <td><button aria-label={`Delete ${d.name}`} className="p-2 text-mute hover:text-bad" onClick={() => remove(d.dataset_id)}><Trash2 size={15} /></button></td>
              </tr>))}</tbody></table>
        </div>
      )}
      {sel != null && (analysis ? (
        <section className="bg-panel border border-line rounded-lg p-4 space-y-3">
          <h2 className="font-medium">Data quality</h2>
          <p className="text-sm text-mute">{analysis.rows} rows, {analysis.columns} columns. Missing values: {analysis.missing_total}. Duplicate rows: {analysis.duplicate_rows}.</p>
          {analysis.class_distribution && <p className="text-sm">Class balance: {Object.entries(analysis.class_distribution).map(([k, v]) => `${k}: ${v}`).join(", ")}</p>}
          {Object.keys(analysis.missing_values).length > 0 && <p className="text-sm text-warn">Columns with missing values: {Object.entries(analysis.missing_values).map(([k, v]) => `${k} (${v})`).join(", ")}</p>}
          {preview.length > 0 && <div className="overflow-x-auto"><table className="text-xs font-mono"><thead><tr>{Object.keys(preview[0]).slice(0, 8).map((k) => <th key={k} className="pr-4 text-left text-mute">{k}</th>)}</tr></thead>
            <tbody>{preview.map((r, i) => <tr key={i}>{Object.values(r).slice(0, 8).map((v, j) => <td key={j} className="pr-4">{String(v)}</td>)}</tr>)}</tbody></table></div>}
        </section>) : <p className="text-mute text-sm">Loading analysis</p>)}
    </div>
  );
}
