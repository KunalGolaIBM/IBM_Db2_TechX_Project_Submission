import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
} from 'recharts';
import {
  ArrowRight,
  Download,
  Sparkles,
  Info,
} from 'lucide-react';
import AiAssistantDrawer from '../components/common/AiAssistantDrawer';
import api from '../lib/api';
import { useProjects } from '../hooks/useApi';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

export const CarbonEstimates = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const projectsQ = useProjects();
  const projectId = searchParams.get('project') || projectsQ.data?.projects?.[0]?.id || '';
  const carbonQ = useQuery({ queryKey: ['carbon', projectId, '30d'], queryFn: () => api.getCarbon(projectId, '30d'), enabled: Boolean(projectId) });
  const [assessmentMessage, setAssessmentMessage] = useState('');
  const [assessmentLoading, setAssessmentLoading] = useState(false);
  const [assessments, setAssessments] = useState([]);
  const estimate = carbonQ.data?.estimate;
  const metrics = estimate?.metrics;
  const indicators = metrics ? [
    { name: 'Soil organic carbon stock (0–30 cm)', value: metrics.soc_stock_total_tCO2e, unit: 'tCO₂e stock' },
    { name: 'Soil respiration (loss flux)', value: metrics.soil_respiration_project_tCO2e_yr, unit: 'tCO₂e/year flux' },
    { name: 'Indicative net sequestration model output', value: metrics.net_sequestration_project_tCO2e_yr, unit: 'tCO₂e/year estimate' },
  ] : [];
  const series = (carbonQ.data?.trend || []).map((item) => ({ year: item.date, potential: item.net_sequestration_tCO2e_yr }));

  useEffect(() => {
    if (projectId) api.listAssessments(projectId).then((result) => setAssessments(result.assessments || [])).catch((err) => setAssessmentMessage(`Evidence ledger unavailable: ${err.message}`));
  }, [projectId]);

  const saveAssessment = async () => {
    setAssessmentLoading(true);
    setAssessmentMessage('');
    try {
      const result = await api.createAssessment(projectId);
      setAssessments((previous) => [result.assessment, ...previous]);
      setAssessmentMessage(`Saved assessment ${result.assessment.id} · revision ${result.assessment.revision}. Human review pending.`);
    } catch (err) {
      setAssessmentMessage(`Assessment was not saved: ${err.message}`);
    } finally { setAssessmentLoading(false); }
  };
  const [isAiOpen, setIsAiOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const handleDownloadReport = async () => {
    setDownloading(true);
    try {
      if (!projectId) throw new Error('No saved project is available to export.');
      await api.downloadCsv(projectId, 'carbon');
      setAssessmentMessage('Carbon estimate CSV downloaded from saved project data.');
    } catch (err) {
      setAssessmentMessage(`Export unavailable: ${err.message}`);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      
      {/* 4-CARD RESPONSIVE GRID - EXACT REPRODUCTION OF REFERENCE IMAGE (Bottom-Left) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* CARD 1: Estimated Carbon Storage (Top-Left) */}
        <div className="cn-card p-7 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-lg text-[#0E2018]">
                Estimated Carbon Storage
              </h3>
              <button
                onClick={() => setIsAiOpen(true)}
                className="text-xs font-semibold text-[#0A7B4E] hover:underline flex items-center gap-1"
                title="Explain with AI"
              >
                <Sparkles size={13} /> Explain
              </button>
            </div>

            {/* Giant Stat Display matching image */}
            <div className="mt-3">
              <div className="flex items-baseline gap-2">
                <span className="text-5xl font-extrabold text-[#0E2018] tracking-tight">
                  {carbonQ.isLoading ? '…' : metrics ? Number(metrics.soc_stock_total_tCO2e).toLocaleString() : '—'}
                </span>
                <span className="text-xl font-semibold text-[#446654]">
                  tCO₂e
                </span>
              </div>

              <p className="text-xs text-[#617D6E] mt-2 font-medium">
                Modeled soil organic carbon stock equivalent (0–30 cm); not credits
              </p>
            </div>
          </div>

          {/* Growth Pill Badge matching reference image */}
          <div className="mt-6 pt-5 border-t border-[#EDF2EE] flex items-center justify-between">
            <span className="text-xs text-[#2E6B4F]">{estimate?.data_source || 'Waiting for project data'}</span>
            <span className="text-[11px] text-[#718F80]">Engine v{carbonQ.data?.methodology?.engine_version || '—'} · deterministic</span>
          </div>
        </div>

        {/* Observed/estimated indicators are kept separate because stock and annual flows are not additive. */}
        <div className="cn-card p-7">
          <h3 className="font-bold text-lg text-[#0E2018] mb-2">Distinct carbon indicators</h3>
          <p className="text-xs text-[#617D6E] mb-4">Stock, respiration flux, and modeled sequestration are different quantities; they are not stacked or treated as credits.</p>
          <div className="space-y-3">
            {indicators.map((item) => <div key={item.name} className="flex items-start justify-between gap-3 rounded-xl bg-[#FAFBF9] border border-[#E9EFEA] p-3"><span className="text-sm text-[#1A382A]">{item.name}</span><span className="text-right text-sm font-bold text-[#0E2018]">{item.value}<small className="block font-normal text-[#638071]">{item.unit}</small></span></div>)}
          </div>
          <p className="mt-4 text-xs text-amber-800">Missing laboratory SOC / bulk-density input remains flagged below; this is a default-driven estimate, not measured soil carbon.</p>
        </div>

        {/* CARD 3: Carbon Storage Potential Line Chart (Bottom-Left) */}
        <div className="cn-card p-7">
          <div className="flex items-center justify-between mb-2">
            <div>
              <h3 className="font-bold text-lg text-[#0E2018]">
                Daily model output variation
              </h3>
              <p className="text-xs text-[#617D6E]">Deterministic annualized estimate from sensor context; not measured carbon-stock change</p>
            </div>
            <span className="text-xs font-semibold text-[#0A7B4E] bg-[#E8F7F0] px-2.5 py-0.5 rounded-full">
              tCO₂e/year (project)
            </span>
          </div>

          {series.length ? <div className="h-56 mt-4 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={series}
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="potentialGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10B981" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#10B981" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="year"
                  stroke="#87A292"
                  fontSize={11}
                  tickLine={false}
                  axisLine={{ stroke: '#E3E9E3' }}
                />
                <YAxis
                  stroke="#87A292"
                  fontSize={11}
                  domain={[0, 30]}
                  ticks={[0, 10, 20, 30]}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  formatter={(val) => [`${val} tCO₂e/year`, 'Indicative annualized model output']}
                  contentStyle={{
                    backgroundColor: '#FFFFFF',
                    borderRadius: '12px',
                    border: '1px solid #DCE6DE',
                    fontSize: '12px',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="potential"
                  stroke="#0A8754"
                  strokeWidth={3}
                  fillOpacity={1}
                  fill="url(#potentialGradient)"
                  dot={{ r: 4, fill: '#0A8754', stroke: '#FFFFFF', strokeWidth: 2 }}
                  activeDot={{ r: 6, fill: '#10B981', stroke: '#0C3327', strokeWidth: 2 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div> : <p className="mt-4 rounded-xl border border-dashed border-[#D5E0D7] p-5 text-sm text-[#638071]">No historical sensor-derived model outputs available for this period.</p>}
        </div>

        {/* CARD 4: Recommendations (Bottom-Right) */}
        <div className="cn-card p-7 flex flex-col justify-between">
          <div>
            <h3 className="font-bold text-lg text-[#0E2018] mb-4">
              Recommendations
            </h3>

            {/* List with Circular Botanical Icons */}
            <div className="space-y-4 text-sm text-[#526F60]">
              <p>Recommended next step: collect georeferenced soil samples and measured bulk density using a documented sampling design.</p>
              <p>Attach field methods and source metadata before interpreting default-based carbon estimates.</p>
              <p>Independent validation and registry records are required before any credit can be described as verified or issued.</p>
            </div>
          </div>

          {/* Full Width Deep Forest Button matching image */}
          <div className="mt-6 pt-4 border-t border-[#EDF2EE]">
            <button
              onClick={() => navigate('/reports')}
              className="w-full btn-forest py-3.5 rounded-xl font-semibold text-sm flex items-center justify-center gap-2"
            >
              <span>View Detailed Report</span>
              <ArrowRight size={16} />
            </button>
          </div>
        </div>

      </div>

      {carbonQ.isError && <div role="alert" className="cn-card p-4 text-sm text-red-800">Assessment unavailable: {carbonQ.error.message}</div>}
      {carbonQ.isLoading && <div role="status" className="cn-card p-4 text-sm text-[#638071]">Loading the saved deterministic project estimate…</div>}
      {!projectsQ.isLoading && !projectId && <div className="cn-card p-4 text-sm text-[#638071]">No saved project. Map and save a parcel before requesting an estimate.</div>}
      {assessmentMessage && <div role="status" className="cn-card p-4 text-sm text-[#285D45]">{assessmentMessage}</div>}

      <section className="cn-card p-6 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><h3 className="font-bold text-lg text-[#0E2018]">Carbon Evidence Ledger</h3><p className="text-xs text-[#638071]">Saved deterministic snapshots with observation references, method version, assumptions, missing inputs, and review status.</p></div>
          <button onClick={saveAssessment} disabled={!projectId || assessmentLoading || carbonQ.isLoading} className="btn-forest text-xs">{assessmentLoading ? 'Saving assessment…' : 'Save assessment'}</button>
        </div>
        {!assessments.length ? <p className="text-sm text-[#638071]">No assessment snapshots saved yet. Save one to create the initial ledger revision.</p> : <div className="space-y-3">{assessments.map((assessment) => <details key={assessment.id} className="rounded-xl border border-[#DCE6DE] p-4"><summary className="cursor-pointer text-sm font-semibold">Revision {assessment.revision} · {new Date(assessment.assessment_date).toLocaleString()} · {assessment.human_review_status} · {assessment.id}</summary><div className="mt-3 grid gap-3 text-xs text-[#526F60] md:grid-cols-2"><p><strong>Observation references:</strong> {assessment.input_observation_ids.length ? assessment.input_observation_ids.join(', ') : 'None stored'}</p><p><strong>Sources:</strong> {assessment.data_source_references.join(', ') || 'No source observations'}</p><p><strong>Method:</strong> {assessment.calculation_method.name} · v{assessment.calculation_method.version}</p><p><strong>Revision link:</strong> {assessment.previous_assessment_id || 'Initial snapshot'}</p><p className="md:col-span-2"><strong>Missing evidence:</strong> {assessment.missing_information.join(' ') || 'No known missing inputs recorded.'}</p><p className="md:col-span-2"><strong>Limitations:</strong> {assessment.uncertainty_and_quality_limitations.join(' ')}</p></div></details>)}</div>}
      </section>

      {/* SCIENTIFIC PROVENANCE & UNCERTAINTY FOOTNOTE (Non-invented standards) */}
      <div className="cn-card p-6 bg-[#FAFBF9] border border-[#E3EAE4] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <Info size={18} className="text-[#0A7B4E] shrink-0 mt-0.5" />
          <div className="text-xs text-[#4F6C5D]">
            <p className="font-semibold text-[#142E21]">Methodology & Verification Disclosure</p>
            <p className="mt-0.5">
              This deterministic prototype uses land-type defaults unless project inputs and timestamped sensor readings are supplied. It does not retrieve HWSD or satellite observations, and it is not an approved carbon-credit methodology. Outputs are indicative only, with explicit missing inputs and limitations.
            </p>
          </div>
        </div>

        <button
          onClick={handleDownloadReport}
          disabled={downloading}
          className="btn-outline-forest shrink-0 text-xs py-2 px-4 flex items-center gap-2"
        >
          <Download size={14} />
          <span>{downloading ? 'Exporting...' : 'Export CSV Dataset'}</span>
        </button>
      </div>

      {/* AI Assistant Context Drawer */}
      <AiAssistantDrawer
        isOpen={isAiOpen}
        onClose={() => setIsAiOpen(false)}
      />
    </div>
  );
};

export default CarbonEstimates;
