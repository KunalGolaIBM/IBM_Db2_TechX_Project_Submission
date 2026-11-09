import React, { useState } from 'react';
import { useProjects } from '../hooks/useApi';
import {
  Award,
  ShieldCheck,
  FileCheck2,
  AlertTriangle,
  HelpCircle,
  TrendingUp,
  Download,
  ExternalLink,
  CheckCircle2,
  Clock,
  Coins,
  Sparkles,
} from 'lucide-react';
import AiAssistantDrawer from '../components/common/AiAssistantDrawer';

const PROJECT_STAGES = ['Draft', 'Data collection', 'Assessment', 'Validation pending', 'Verification pending', 'Independently verified', 'Registered / issued', 'Retired'];

export const CarbonCreditsPage = () => {
  const [isAiOpen, setIsAiOpen] = useState(false);
  const projectsQ = useProjects();
  const projects = projectsQ.data?.projects || [];

  return (
    <div className="max-w-7xl mx-auto space-y-6">

      {/* Mandatory Integrity Disclosure Alert */}
      <div className="bg-[#FAFBF9] border border-[#CCD8CD] p-5 rounded-2xl flex items-start gap-3.5 shadow-xs">
        <ShieldCheck size={22} className="text-[#0A7B4E] shrink-0 mt-0.5" />
        <div className="text-xs text-[#3E5C4D]">
          <h4 className="font-bold text-[#10271E] text-sm">
            dMRV Scientific & Regulatory Integrity Policy
          </h4>
          <p className="mt-1 leading-relaxed">
            CarbonNova distinguishes modeled carbon potential from verified and issued credits. <strong>Modeled estimates cannot be traded as compliance or voluntary credits</strong> until independently validated and audited by an ISO 14065 accredited validation/verification body (VVB) and serialized on an official carbon registry (e.g., Verra, Gold Standard, Puro.earth).
          </p>
        </div>
      </div>

      <div className="cn-card p-6">
        <h3 className="font-bold text-lg text-[#0E2018] mb-1">Project readiness and credit records</h3>
        <p className="text-xs text-[#638071] mb-5">Stages require supporting records. No independent validation, registry reference, issuance, or retirement is recorded in this prototype.</p>
        {projectsQ.isLoading ? <p role="status">Loading project records…</p> : projectsQ.isError ? <p role="alert" className="text-red-800">Could not load projects: {projectsQ.error.message}</p> : !projects.length ? <p className="text-sm text-[#638071]">No saved projects.</p> : <div className="space-y-3">{projects.map((project) => <div key={project.id} className="rounded-xl border border-[#E3E9E3] p-4"><div className="flex flex-wrap justify-between gap-2"><strong>{project.name}</strong><span className="badge-sage">{project.status || 'Draft'}</span></div><p className="mt-2 text-xs text-[#638071]">Stage recorded: {project.status}. No verification, registry, issued, or retired-credit records are attached.</p><p className="mt-1 text-xs text-[#638071]">Outstanding: baseline and methodology evidence, field sampling, monitoring plan, independent validation/verification, registry identifier.</p></div>)}</div>}
      </div>
      <div className="cn-card p-6"><h3 className="font-bold text-lg text-[#0E2018] mb-3">Possible lifecycle states</h3><div className="flex flex-wrap gap-2">{PROJECT_STAGES.map((stage) => <span key={stage} className="badge-sage">{stage}</span>)}</div><p className="mt-3 text-xs text-[#638071]">These are vocabulary labels only; the UI does not advance a project without a supporting record.</p></div>

      {/* Historic/demo evidence and revenue assumptions were removed: none are in saved records. */}
      <div className="cn-card p-6"><h3 className="font-bold text-base text-[#0E2018]">Evidence gaps</h3><p className="mt-2 text-sm text-[#638071]">No Sentinel-2 record, soil laboratory attachment, land-title upload, validation submission, registry ID, or issued/retired credits are currently stored. CarbonNova organizes evidence; it does not certify or issue credits.</p></div>
      {/* AI Assistant Context Drawer */}
      <AiAssistantDrawer
        isOpen={isAiOpen}
        onClose={() => setIsAiOpen(false)}
      />
    </div>
  );
};

export default CarbonCreditsPage;
