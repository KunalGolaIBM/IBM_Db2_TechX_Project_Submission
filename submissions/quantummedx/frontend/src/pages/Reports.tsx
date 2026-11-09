import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, errText } from "../api";

export default function Reports() {
  const [list, setList] = useState<any[] | null>(null); const [open, setOpen] = useState<any>(null); const [err, setErr] = useState("");
  useEffect(() => { api.get("/api/reports").then((r) => { setList(r.data); }).catch((e) => setErr(errText(e))); }, []);
  const view = (id: number) => api.get(`/api/reports/${id}`).then((r) => setOpen(r.data)).catch((e) => setErr(errText(e)));
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Reports</h1>
      {err && <p role="alert" className="text-sm text-bad">{err}</p>}
      {list === null ? <p className="text-mute text-sm">Loading reports</p> : list.length === 0 ? <p className="text-mute text-sm">No reports yet. Start an agent run to create one.</p> : (
        <ul className="space-y-1 max-w-xl">{list.map((r) => (
          <li key={r.report_id}><button onClick={() => view(r.report_id)} className="w-full text-left rounded-md border border-line px-3 py-2 text-sm hover:bg-lift">
            {r.title} <span className={r.status === "FINAL" ? "text-ok" : "text-warn"}>{r.status === "FINAL" ? "verified" : "needs review"}</span></button></li>))}</ul>)}
      {open && <article className="md bg-panel border border-line rounded-lg p-5"><ReactMarkdown remarkPlugins={[remarkGfm]}>{open.body_md}</ReactMarkdown></article>}
    </div>
  );
}
