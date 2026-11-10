import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  Printer, 
  Copy, 
  Check, 
  Download, 
  ShieldAlert, 
  ChevronDown 
} from 'lucide-react';
import { SentinelApi } from '../services/api';

export default function ReportViewPage({ incidents = [], defaultIncidentId }) {
  const [selectedIncidentId, setSelectedIncidentId] = useState(defaultIncidentId || (incidents[0]?.incident_id || ''));
  const [reportMarkdown, setReportMarkdown] = useState('');
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (selectedIncidentId) {
      loadReport(selectedIncidentId);
    }
  }, [selectedIncidentId]);

  const loadReport = async (incId) => {
    setLoading(true);
    try {
      const res = await SentinelApi.getIncidentReport(incId);
      setReportMarkdown(res.markdown || '');
    } catch (e) {
      setReportMarkdown('Failed to generate report for selected incident.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(reportMarkdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-xl font-bold font-tech text-white uppercase tracking-wide flex items-center space-x-2">
            <FileText className="w-5 h-5 text-cyan-400" />
            <span>Executive AI Security Report Generator</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Cryptographically sealed intelligence briefing synthesized by the LangGraph Incident Response Agent
          </p>
        </div>

        {/* Incident Selector & Actions */}
        <div className="flex items-center space-x-3">
          <select
            value={selectedIncidentId}
            onChange={(e) => setSelectedIncidentId(e.target.value)}
            className="bg-[#070d18] border border-[#1a2f55] rounded-lg px-3 py-2 text-xs font-mono-code text-cyan-300 focus:outline-none focus:border-blue-500"
          >
            {incidents.map((inc) => (
              <option key={inc.incident_id} value={inc.incident_id}>
                {inc.incident_id} — {inc.full_name || inc.user_id} ({inc.severity})
              </option>
            ))}
          </select>

          <button
            onClick={handleCopy}
            className="flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-[#0b1528] border border-[#1a2f55] text-slate-300 hover:text-white hover:border-blue-500 text-xs transition-all"
            title="Copy Report to Clipboard"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>

          <button
            onClick={handlePrint}
            className="flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-lg shadow-blue-900/40 transition-all"
          >
            <Printer className="w-3.5 h-3.5" />
            <span>Print / PDF</span>
          </button>
        </div>
      </div>

      {/* Report Document Box */}
      <div className="cyber-card p-8 bg-[#091120] border border-[#1a2f55] rounded-xl max-w-4xl mx-auto shadow-2xl relative">
        {/* Defence Watermark Header */}
        <div className="border-b-2 border-[#1a2f55] pb-4 mb-6 flex justify-between items-start text-xs font-mono-code">
          <div>
            <p className="text-rose-400 font-bold uppercase tracking-widest text-[11px]">
              RESTRICTED // SPECIAL ACCESS REQUIRED
            </p>
            <p className="text-slate-400">JOINT DEFENCE CYBERSECURITY INTELLIGENCE COMMAND</p>
          </div>
          <div className="text-right text-slate-500">
            <p>SENTINEL AI PROTOCOL v1.0</p>
            <p>SYSTEM ID: DEF-SOC-NODE-01</p>
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className="py-20 text-center font-mono-code text-cyan-400 text-xs">
            Synthesizing intelligence dossier via Agent 5...
          </div>
        ) : (
          <div className="prose prose-invert max-w-none text-slate-200 text-xs leading-relaxed font-sans space-y-4">
            <pre className="font-mono-code bg-[#060b14] p-5 rounded-lg border border-[#152642] whitespace-pre-wrap text-[11px] text-slate-200 leading-relaxed overflow-x-auto">
              {reportMarkdown}
            </pre>
          </div>
        )}

        {/* Security Footer Notice */}
        <div className="mt-8 pt-4 border-t border-[#1a2f55] flex justify-between items-center text-[10px] font-mono-code text-slate-500">
          <span>CLASSIFIED DEFENCE CYBER COMMAND DOCUMENT</span>
          <span>AUTONOMOUS AGENT ORCHESTRATION: LANGGRAPH 1.2</span>
        </div>
      </div>
    </div>
  );
}

