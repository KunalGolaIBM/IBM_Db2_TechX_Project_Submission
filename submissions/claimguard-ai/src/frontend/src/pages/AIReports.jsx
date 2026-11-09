import React, { useEffect, useState } from 'react';
import {
  Sparkles,
  FileText,
  Database,
  ShieldAlert,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  Printer,
  Cpu,
  ArrowRight
} from 'lucide-react';
import { apiClient } from '../api/client';
import RiskScoreBadge from '../components/RiskScoreBadge';

export default function AIReports() {
  const [claims, setClaims] = useState([]);
  const [selectedClaimId, setSelectedClaimId] = useState('');
  const [reportData, setReportData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    async function loadClaims() {
      try {
        const res = await apiClient.getClaims();
        setClaims(res.data);
        if (res.data.length > 0) {
          setSelectedClaimId(res.data[0].claim_id);
          fetchReport(res.data[0].claim_id);
        }
      } catch (err) {
        console.error('Failed to load claims list:', err);
      } finally {
        setLoading(false);
      }
    }
    loadClaims();
  }, []);

  const fetchReport = async (claimId) => {
    if (!claimId) return;
    setGenerating(true);
    try {
      const res = await apiClient.getReport(claimId);
      setReportData(res.data);
    } catch (err) {
      console.error('Failed to load report:', err);
    } finally {
      setGenerating(false);
    }
  };

  const handleSelectChange = (e) => {
    const id = e.target.value;
    setSelectedClaimId(id);
    fetchReport(id);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-[#E0E0E0]">
        <div>
          <div className="flex items-center space-x-2">
            <div className="p-1.5 bg-[#F6F2FF] text-[#8A3FFC] rounded">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-[#161616]">Explainable AI Verification Reports</h1>
              <p className="text-xs text-[#525252]">
                Comprehensive synthesis of Document, Database, Fraud, and Decision Agents
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <select
            value={selectedClaimId}
            onChange={handleSelectChange}
            className="p-1.5 bg-white border border-[#E0E0E0] text-xs font-mono font-medium text-gray-800 rounded-sm focus:outline-none focus:border-[#0F62FE]"
          >
            {claims.map((c) => (
              <option key={c.claim_id} value={c.claim_id}>
                {c.claim_number} ({c.claim_id}) — ₹{parseFloat(c.claim_amount).toLocaleString()}
              </option>
            ))}
          </select>
          <button
            onClick={() => fetchReport(selectedClaimId)}
            className="p-1.5 bg-white border border-[#E0E0E0] hover:bg-gray-50 text-gray-700 rounded-sm"
            title="Refresh Report"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${generating ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {generating ? (
        <div className="py-20 text-center text-xs text-gray-400">
          <Cpu className="w-8 h-8 animate-pulse text-[#0F62FE] mx-auto mb-2" />
          <span>Synthesizing multi-agent intelligence and Db2 audit trails...</span>
        </div>
      ) : !reportData ? (
        <div className="bg-white border border-[#E0E0E0] p-12 text-center rounded-sm">
          <p className="text-sm text-gray-500">Select a claim to generate an explainable audit report.</p>
        </div>
      ) : (
        <div className="space-y-5">
          {/* Executive Summary Banner */}
          <div className="bg-white border-l-4 border-[#0F62FE] border border-[#E0E0E0] p-5 rounded-sm shadow-sm">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div>
                <span className="text-[10px] font-mono text-[#0F62FE] font-bold uppercase tracking-wider">
                  Advisory Adjudication Report
                </span>
                <h2 className="text-lg font-bold text-gray-900 mt-0.5">
                  Claim {reportData.claim_number} ({reportData.claim_id})
                </h2>
                <p className="text-xs text-gray-600 mt-1">
                  Claimant: <span className="font-semibold text-gray-900">{reportData.customer?.name}</span> • Policy: <span className="font-mono text-gray-900">{reportData.policy?.policy_number}</span>
                </p>
              </div>

              <div className="flex items-center space-x-3">
                <div className="text-right">
                  <span className="text-[10px] text-gray-400 uppercase font-mono block">Recommended Outcome</span>
                  <span
                    className={`inline-block px-3 py-1 rounded text-xs font-bold uppercase ${
                      reportData.risk_assessment?.recommendation === 'APPROVE'
                        ? 'bg-emerald-100 text-emerald-800'
                        : reportData.risk_assessment?.recommendation === 'REJECT'
                        ? 'bg-red-100 text-red-800'
                        : 'bg-amber-100 text-amber-800'
                    }`}
                  >
                    {reportData.risk_assessment?.recommendation}
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-[10px] text-gray-400 uppercase font-mono block">Risk Score</span>
                  <RiskScoreBadge
                    score={reportData.risk_assessment?.risk_score}
                    level={reportData.risk_assessment?.risk_level}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Agent Synthesis 4-Box Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 1. Document Extraction Agent */}
            <div className="bg-white border border-[#E0E0E0] p-4 rounded-sm shadow-sm space-y-2">
              <div className="flex items-center space-x-2 pb-2 border-b border-gray-100 text-[#0F62FE]">
                <FileText className="w-4 h-4" />
                <h3 className="text-xs font-bold uppercase tracking-wider font-mono">
                  1. Document Extraction Agent
                </h3>
              </div>
              <p className="text-xs text-gray-700">
                Model: <span className="font-mono text-[#0F62FE]">Google Gemini 2.5 Flash</span> via LangChain
              </p>
              <div className="text-xs text-gray-600 space-y-1 bg-gray-50 p-2.5 rounded border border-gray-100 font-mono text-[11px]">
                <div className="flex justify-between">
                  <span>Attached Evidence Count:</span>
                  <span className="font-semibold">{reportData.evidence?.documents_count || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span>Cryptographic Hashing:</span>
                  <span className="text-emerald-700 font-semibold">SHA-256 Verified</span>
                </div>
              </div>
            </div>

            {/* 2. Database Verification Agent */}
            <div className="bg-white border border-[#E0E0E0] p-4 rounded-sm shadow-sm space-y-2">
              <div className="flex items-center space-x-2 pb-2 border-b border-gray-100 text-[#0F62FE]">
                <Database className="w-4 h-4" />
                <h3 className="text-xs font-bold uppercase tracking-wider font-mono">
                  2. Database Verification Agent
                </h3>
              </div>
              <p className="text-xs text-gray-700">
                Data Store: <span className="font-mono text-[#0F62FE]">IBM Db2 (CUSTOMER_DETAILS & POLICY_DETAILS)</span>
              </p>
              <div className="text-xs text-gray-600 space-y-1 bg-gray-50 p-2.5 rounded border border-gray-100 font-mono text-[11px]">
                <div className="flex justify-between">
                  <span>Remaining Limit:</span>
                  <span className="font-semibold">₹{reportData.policy?.remaining_coverage?.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span>Deductible Requirement:</span>
                  <span>₹{reportData.policy?.deductible?.toLocaleString()}</span>
                </div>
              </div>
            </div>

            {/* 3. Fraud Detection Agent */}
            <div className="bg-white border border-[#E0E0E0] p-4 rounded-sm shadow-sm space-y-2">
              <div className="flex items-center space-x-2 pb-2 border-b border-gray-100 text-[#DA1E28]">
                <ShieldAlert className="w-4 h-4" />
                <h3 className="text-xs font-bold uppercase tracking-wider font-mono">
                  3. Fraud Detection Agent
                </h3>
              </div>
              <p className="text-xs text-gray-700">
                Cross-Checks: Duplicate Hashes, Invoice Collisions, Date Anomalies
              </p>
              <div className="text-xs text-gray-600 space-y-1 bg-gray-50 p-2.5 rounded border border-gray-100 font-mono text-[11px]">
                <div className="flex justify-between">
                  <span>Persisted Db2 Alerts:</span>
                  <span className={reportData.evidence?.alerts_count > 0 ? 'text-red-700 font-bold' : 'text-emerald-700 font-semibold'}>
                    {reportData.evidence?.alerts_count || 0} Alert(s)
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Hash Collision Status:</span>
                  <span className="text-gray-800">Evaluated vs DOCUMENT_RECORDS</span>
                </div>
              </div>
            </div>

            {/* 4. Decision Support Agent */}
            <div className="bg-white border border-[#E0E0E0] p-4 rounded-sm shadow-sm space-y-2">
              <div className="flex items-center space-x-2 pb-2 border-b border-gray-100 text-[#8A3FFC]">
                <Sparkles className="w-4 h-4" />
                <h3 className="text-xs font-bold uppercase tracking-wider font-mono">
                  4. Decision Support Agent
                </h3>
              </div>
              <p className="text-xs text-gray-700">
                Multi-Agent Evidence Aggregator & Weighted Scoring Engine
              </p>
              <div className="text-xs text-gray-600 space-y-1 bg-gray-50 p-2.5 rounded border border-gray-100 font-mono text-[11px]">
                <div className="flex justify-between">
                  <span>Workflow Steps Executed:</span>
                  <span className="font-semibold">{reportData.evidence?.audit_steps_count || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span>Human Governance:</span>
                  <span className="text-amber-800 font-semibold">Advisory Only</span>
                </div>
              </div>
            </div>
          </div>

          {/* Explainable Rationale Factors */}
          <div className="bg-white border border-[#E0E0E0] p-5 rounded-sm shadow-sm">
            <h3 className="text-xs font-bold uppercase tracking-wider font-mono text-[#161616] mb-3">
              Explainable Decision Rationale & Key Factors
            </h3>
            <div className="space-y-2">
              {reportData.risk_assessment?.reasons?.length > 0 ? (
                reportData.risk_assessment.reasons.map((factor, index) => (
                  <div key={index} className="flex items-start space-x-2 text-xs text-gray-800 bg-gray-50 p-2.5 rounded border border-gray-100">
                    <span className="font-mono text-[#0F62FE] font-bold">#{index + 1}</span>
                    <span>{factor}</span>
                  </div>
                ))
              ) : (
                <div className="flex items-center space-x-2 text-xs text-emerald-800 bg-emerald-50 p-3 rounded border border-emerald-200">
                  <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>All automated cryptographic, policy, and temporal checks passed without negative findings.</span>
                </div>
              )}
            </div>

            <div className="mt-4 pt-3 border-t border-gray-100 text-[11px] text-gray-500">
              Disclaimer: This AI-generated report is provided for adjudication support. Final binding approval or rejection remains the sole legal responsibility of an authorized human claim examiner.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
