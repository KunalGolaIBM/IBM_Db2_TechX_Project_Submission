import React, { useState } from 'react';
import {
  FileText,
  Download,
  Printer,
  Sparkles,
  Calendar,
  CheckCircle2,
  FileSpreadsheet,
  Layers,
  MapPin,
  Info,
} from 'lucide-react';
import api from '../lib/api';
import { useProjects } from '../hooks/useApi';
import AiAssistantDrawer from '../components/common/AiAssistantDrawer';

const REPORT_TEMPLATES = [
  {
    id: 'rep-land',
    title: 'Saved project monitoring report',
    type: 'Saved project data',
    date: null,
    format: 'PDF / CSV',
    desc: 'PDF assessment summary or CSV observations built from the currently selected saved project.',
  },
  {
    id: 'rep-carbon',
    title: 'Indicative carbon engine output (CSV)',
    type: 'Deterministic estimate',
    date: null,
    format: 'CSV',
    desc: 'Current saved-project carbon engine output, formula notes, source labels, assumptions, and limitations. Not a credit certification.',
  },
  {
    id: 'rep-monitoring',
    title: 'Stored sensor observations (CSV)',
    type: 'Field sensor observations',
    date: null,
    format: 'CSV',
    desc: 'Timestamped sensor records from the currently selected saved project, including source and synthetic-data labels.',
  },
  {
    id: 'rep-dmrv',
    title: 'Saved project monitoring report',
    type: 'Review draft',
    date: null,
    format: 'PDF',
    desc: 'A traceable project report. No external verifier, registry, or compliance state is implied.',
  },
];

export const ReportsPage = () => {
  const [downloadingId, setDownloadingId] = useState(null);
  const [isAiOpen, setIsAiOpen] = useState(false);
  const projectsQ = useProjects();
  const projects = projectsQ.data?.projects || [];
  const [projectId, setProjectId] = useState('');
  const activeProjectId = projectId || projects[0]?.id || '';

  const handleDownload = async (report) => {
    setDownloadingId(report.id);
    try {
      if (!activeProjectId) throw new Error('Select a saved project before generating a report.');
      if (report.id === 'rep-carbon') await api.downloadCsv(activeProjectId, 'carbon');
      else if (report.id === 'rep-monitoring') await api.downloadCsv(activeProjectId, 'readings');
      else await api.downloadPdf(activeProjectId, { includeAiSummary: false });
    } catch (err) {
      window.alert(`Report unavailable: ${err.message}`);
    } finally {
      setDownloadingId(null);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6">

      {/* Header and Print CTA */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-[#0E2018]">Audit & Calculation Reports</h2>
          <p className="text-xs text-[#638071]">
            Downloadable outputs generated from saved project records; not official verification documents
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handlePrint}
            className="btn-outline-forest text-xs py-2 px-3.5 flex items-center gap-1.5"
          >
            <Printer size={14} />
            <span>Print Current Page</span>
          </button>

          <button
            onClick={() => setIsAiOpen(true)}
            className="btn-forest text-xs py-2 px-4 flex items-center gap-1.5"
          >
            <Sparkles size={14} className="text-[#34D399]" />
            <span>Draft AI Summary</span>
          </button>
        </div>
      </div>

      <div className="cn-card p-4 flex items-center gap-3"><label htmlFor="report-project" className="text-xs font-semibold">Saved project</label><select id="report-project" className="cn-input max-w-md" value={activeProjectId} onChange={(event) => setProjectId(event.target.value)}><option value="">Select a project</option>{projects.map((project) => <option value={project.id} key={project.id}>{project.name}</option>)}</select></div>
      {projectsQ.isError && <p role="alert" className="text-sm text-red-800">Could not load projects: {projectsQ.error.message}</p>}
      {!projectsQ.isLoading && !projects.length && <p className="cn-card p-4 text-sm text-[#638071]">No saved projects available to report.</p>}

      {/* Reports Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {REPORT_TEMPLATES.map((rep) => (
          <div
            key={rep.id}
            className="cn-card-hover p-6 flex flex-col justify-between bg-white"
          >
            <div>
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="w-10 h-10 rounded-xl bg-[#E8F7F0] text-[#0A7B4E] flex items-center justify-center shrink-0">
                  <FileText size={20} />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-gray-100 text-gray-700">
                  {rep.type}
                </span>
              </div>

              <h3 className="font-bold text-base text-[#0E2018] mb-1.5">
                {rep.title}
              </h3>
              <p className="text-xs text-[#526F60] leading-relaxed mb-4">
                {rep.desc}
              </p>
            </div>

            <div className="pt-4 border-t border-[#EDF2EE] flex items-center justify-between">
              <span className="text-[11px] text-gray-400">
                {rep.date ? `Updated: ${rep.date}` : 'Generated on download from saved data'}
              </span>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleDownload(rep)}
                  disabled={downloadingId === rep.id || !activeProjectId}
                  className="btn-forest text-xs py-2 px-3.5 flex items-center gap-1.5"
                >
                  <Download size={13} />
                  <span>{downloadingId === rep.id ? 'Exporting...' : 'Download'}</span>
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Methodology and Uncertainty Notice */}
      <div className="cn-card p-6 bg-[#FAFBF9] border border-[#CCD8CD] flex items-start gap-3">
        <Info size={18} className="text-[#0A7B4E] shrink-0 mt-0.5" />
        <div className="text-xs text-[#4F6C5D] space-y-1">
          <p className="font-bold text-[#142E21]">Data Provenance & Uncertainty Standards</p>
          <p>
            Reports contain only saved project and sensor information plus the deterministic engine output. Remote-sensing evidence, laboratory samples, and approved methodology data are not configured. A report is not an audit or verification certificate.
          </p>
        </div>
      </div>

      {/* AI Assistant Context Drawer */}
      <AiAssistantDrawer
        isOpen={isAiOpen}
        onClose={() => setIsAiOpen(false)}
      />
    </div>
  );
};

export default ReportsPage;
