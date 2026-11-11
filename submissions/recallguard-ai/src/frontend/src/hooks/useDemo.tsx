/* "Run Tomato Contamination Demo": executes the real workflow step by step through the public API
   and exposes genuine progress (each step reports what the backend actually returned). */
import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import type { Investigation } from "@/types";

export type StepState = "pending" | "running" | "done" | "error";
export interface DemoStep { key: string; label: string; state: StepState; detail?: string }

const INITIAL: DemoStep[] = [
  { key: "incident", label: "Register contamination incident for TOM-2026-041", state: "pending" },
  { key: "upload", label: "Upload laboratory report & extract grounded claims", state: "pending" },
  { key: "investigate", label: "Run 5 AI agents (Db2 recursive trace, risk, plan, verification)", state: "pending" },
  { key: "recall", label: "Generate evidence-backed recall plan", state: "pending" },
  { key: "approval", label: "Await human approval (recall manager)", state: "pending" },
];

interface DemoCtx {
  open: boolean; setOpen: (b: boolean) => void; running: boolean; steps: DemoStep[];
  investigation: Investigation | null; incidentId: string | null; recallId: string | null; error: string | null; run: () => Promise<void>;
}
const Ctx = createContext<DemoCtx | null>(null);

export function DemoProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState<DemoStep[]>(INITIAL);
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [incidentId, setIncidentId] = useState<string | null>(null);
  const [recallId, setRecallId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);

  const mark = (key: string, state: StepState, detail?: string) =>
    setSteps((s) => s.map((x) => (x.key === key ? { ...x, state, detail: detail ?? x.detail } : x)));

  const run = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    setRunning(true); setOpen(true); setError(null); setSteps(INITIAL); setInvestigation(null); setIncidentId(null); setRecallId(null);
    let current = "incident";
    try {
      mark("incident", "running");
      const tpl = await api.tomatoTemplate();
      const inc = await api.createIncident(tpl);
      setIncidentId(inc.incident_id);
      mark("incident", "done", `${inc.incident_id} · ${inc.severity} · supplier ${inc.supplier_name ?? inc.supplier_id}`);

      current = "upload";
      mark("upload", "running");
      const blob = await api.sampleReport();
      const doc = await api.upload(blob, "lab_report_TOM-2026-041.pdf", inc.incident_id, "LAB_REPORT");
      const s = doc.extracted.summary;
      mark("upload", "done", `${doc.document_id} · ${doc.extracted.claims.length} claims · ${s.positive_results} positive result(s) · lots ${s.lot_ids.join(", ")}${doc.duplicate ? " (already in vault)" : ""}`);

      current = "investigate";
      mark("investigate", "running");
      await api.investigate(inc.incident_id);
      let inv: Investigation;
      for (;;) {
        inv = await api.investigation(inc.incident_id);
        setInvestigation(inv);
        const doneN = inv.agents.filter((a) => a.run_status === "COMPLETED").length;
        const active = inv.agents.find((a) => a.run_status === "RUNNING");
        mark("investigate", "running", `${doneN}/5 agents complete${active ? ` · ${active.title} running` : ""} · ${inv.mode}`);
        if (inv.status === "COMPLETED" || inv.status === "FAILED") break;
        await new Promise((r) => setTimeout(r, 500));
      }
      if (inv.status === "FAILED") throw new Error("Investigation failed — see AI Investigation Centre for the agent log");
      const ver = inv.agents.find((a) => a.agent_name === "verification")?.output;
      const risk = inv.agents.find((a) => a.agent_name === "risk_assessment")?.output;
      mark("investigate", "done", `Risk ${risk?.score}/100 ${risk?.classification} · verification ${ver?.verdict} · ${inv.mode === "DETERMINISTIC_FALLBACK" ? "deterministic fallback (no LLM)" : "CrewAI LLM"}`);

      current = "recall";
      mark("recall", "running");
      const rc = await api.generateRecall(inc.incident_id);
      setRecallId(rc.recall_id);
      mark("recall", "done", `${rc.recall_id} · ${rc.recall_class.replace("_", " ")} · ${rc.items.length} items · ${rc.plan.total_units.toLocaleString("en-IN")} units · ${rc.plan.excluded_batches.length} same-SKU batches excluded`);

      current = "approval";
      mark("approval", "running", "Open the recall plan and approve as Recall Manager. AI never issues notices on its own.");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      mark(current, "error", msg);
    } finally {
      busy.current = false;
      setRunning(false);
      qc.invalidateQueries();
    }
  }, [qc]);

  return <Ctx.Provider value={{ open, setOpen, running, steps, investigation, incidentId, recallId, error, run }}>{children}</Ctx.Provider>;
}

export function useDemo() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useDemo must be used within DemoProvider");
  return c;
}
