import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  FileText,
  User,
  Shield,
  ShieldAlert,
  Clock,
  Sparkles,
  CheckCircle,
  XCircle,
  AlertTriangle,
  FileCheck,
  Building,
  RefreshCw,
  Hash,
  ArrowLeft,
  DollarSign
} from 'lucide-react';
import { apiClient } from '../api/client';
import RiskScoreBadge from '../components/RiskScoreBadge';

export default function ClaimDetails() {
  const { claimId } = useParams();
  const [data, setData] = useState(null);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [decisionNotes, setDecisionNotes] = useState('');
  const [decisionAmount, setDecisionAmount] = useState('');
  const [submittingDecision, setSubmittingDecision] = useState(false);
  const [showDecisionModal, setShowDecisionModal] = useState(false);
  const [decisionType, setDecisionType] = useState('APPROVED');

  const fetchClaimData = async () => {
    try {
      setLoading(true);
      const [detailRes, reportRes] = await Promise.all([
        apiClient.getClaim(claimId),
        apiClient.getReport(claimId).catch(() => ({ data: null }))
      ]);
      setData(detailRes.data);
      setReport(reportRes?.data);
      if (detailRes.data?.claim) {
        setDecisionAmount(detailRes.data.claim.claim_amount);
      }
    } catch (err) {
      console.error('Failed to load claim detail:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClaimData();
  }, [claimId]);

  const handleRunAgents = async () => {
    try {
      setVerifying(true);
      await apiClient.triggerVerification(claimId);
      await fetchClaimData();
    } catch (err) {
      console.error('Agent execution failed:', err);
    } finally {
      setVerifying(false);
    }
  };

  const handleOpenDecision = (type) => {
    setDecisionType(type);
    setShowDecisionModal(true);
  };

  const handleSubmitDecision = async () => {
    setSubmittingDecision(true);
    try {
      const payload = {
        status: decisionType,
        decision_notes: decisionNotes,
        approved_amount: decisionType === 'APPROVED' ? parseFloat(decisionAmount) : 0.0
      };
      await apiClient.submitDecision(claimId, payload);
      setShowDecisionModal(false);
      setDecisionNotes('');
      await fetchClaimData();
    } catch (err) {
      alert(err.message || 'Failed to submit decision.');
    } finally {
      setSubmittingDecision(false);
    }
  };

  if (loading) {
    return (
      <div className="py-16 text-center text-xs text-gray-400">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-[#0F62FE]" />
        <span>Loading claim record from IBM Db2...</span>
      </div>
    );
  }

  if (!data || !data.claim) {
    return (
      <div className="bg-white border border-[#E0E0E0] p-8 text-center rounded-sm">
        <p className="text-sm font-semibold text-gray-800">Claim not found in IBM Db2.</p>
        <Link to="/claims" className="text-xs text-[#0F62FE] hover:underline mt-2 inline-block">
          Return to Claims Repository
        </Link>
      </div>
    );
  }

  const { claim, policy, customer, documents, fraud_alerts, verification_logs } = data;

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Action Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b border-[#E0E0E0]">
        <div>
          <Link to="/claims" className="text-xs text-[#0F62FE] hover:underline flex items-center space-x-1 mb-1">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Claims</span>
          </Link>
          <div className="flex items-center space-x-3">
            <h1 className="text-xl font-bold text-[#161616] font-mono">{claim.claim_number}</h1>
            <span
              className={`px-2.5 py-0.5 rounded text-xs font-semibold uppercase ${
                claim.status === 'APPROVED'
                  ? 'bg-emerald-100 text-emerald-800'
                  : claim.status === 'REJECTED'
                  ? 'bg-red-100 text-red-800'
                  : claim.status === 'FLAGGED'
                  ? 'bg-amber-100 text-amber-800'
                  : 'bg-blue-100 text-blue-800'
              }`}
            >
              {claim.status}
            </span>
            <RiskScoreBadge score={claim.risk_score} level={claim.risk_level} />
          </div>
          <p className="text-xs text-[#525252] mt-0.5">
            Internal ID: <span className="font-mono text-gray-700">{claim.claim_id}</span> • Submitted: {claim.submitted_at}
          </p>
        </div>

        {/* Adjudication & Agent Triggers */}
        <div className="flex items-center space-x-2">
          <button
            onClick={handleRunAgents}
            disabled={verifying}
            className="flex items-center space-x-1.5 px-3 py-2 bg-[#EDF5FF] text-[#0F62FE] hover:bg-[#D0E2FF] border border-[#0F62FE] text-xs font-semibold rounded-sm transition-colors"
          >
            <Sparkles className={`w-3.5 h-3.5 ${verifying ? 'animate-spin' : ''}`} />
            <span>{verifying ? 'Running Multi-Agent Workflow...' : 'Run Agentic Verification'}</span>
          </button>

          <button
            onClick={() => handleOpenDecision('APPROVED')}
            className="px-3 py-2 bg-[#198038] hover:bg-[#15672E] text-white text-xs font-semibold rounded-sm transition-colors shadow-sm"
          >
            Approve Claim
          </button>
          <button
            onClick={() => handleOpenDecision('REJECTED')}
            className="px-3 py-2 bg-[#DA1E28] hover:bg-[#B81922] text-white text-xs font-semibold rounded-sm transition-colors shadow-sm"
          >
            Reject Claim
          </button>
          <button
            onClick={() => handleOpenDecision('FLAGGED')}
            className="px-3 py-2 bg-amber-500 hover:bg-amber-600 text-white text-xs font-semibold rounded-sm transition-colors shadow-sm"
          >
            Flag
          </button>
        </div>
      </div>

      {/* Grid: Claimant & Policy Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Claimant Info */}
        <div className="bg-white border border-[#E0E0E0] p-4 rounded-sm shadow-sm">
          <div className="flex items-center space-x-2 pb-2.5 mb-3 border-b border-gray-100">
            <User className="w-4 h-4 text-[#0F62FE]" />
            <h2 className="text-xs font-bold uppercase tracking-wider font-mono text-[#161616]">
              Claimant Profile (IBM Db2: CUSTOMER_DETAILS)
            </h2>
          </div>
          <div className="grid grid-cols-2 gap-y-2 text-xs">
            <div>
              <span className="text-gray-500 block text-[11px]">Full Name:</span>
              <span className="font-semibold text-gray-900">{customer?.first_name} {customer?.last_name}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-[11px]">Customer ID:</span>
              <span className="font-mono text-gray-800">{claim.customer_id}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-[11px]">Email:</span>
              <span className="text-gray-800">{customer?.email || 'N/A'}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-[11px]">Phone:</span>
              <span className="text-gray-800">{customer?.phone || 'N/A'}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-[11px]">National ID:</span>
              <span className="font-mono text-gray-800">{customer?.national_id || 'N/A'}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-[11px]">Address:</span>
              <span className="text-gray-800 truncate block">{customer?.address || 'N/A'}</span>
            </div>
          </div>
        </div>

        {/* Policy Coverage Info */}
        <div className="bg-white border border-[#E0E0E0] p-4 rounded-sm shadow-sm">
          <div className="flex items-center space-x-2 pb-2.5 mb-3 border-b border-gray-100">
            <Shield className="w-4 h-4 text-[#0F62FE]" />
            <h2 className="text-xs font-bold uppercase tracking-wider font-mono text-[#161616]">
              Policy Limits (IBM Db2: POLICY_DETAILS)
            </h2>
          </div>
          <div className="grid grid-cols-2 gap-y-2 text-xs">
            <div>
              <span className="text-gray-500 block text-[11px]">Policy Number:</span>
              <span className="font-mono font-semibold text-gray-900">{policy?.policy_number}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-[11px]">Policy Status:</span>
              <span className="font-semibold text-emerald-700">{policy?.status}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-[11px]">Max Coverage:</span>
              <span className="font-mono font-semibold">₹{parseFloat(policy?.max_coverage_amount || 0).toLocaleString()}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-[11px]">Remaining Coverage:</span>
              <span className="font-mono font-semibold text-[#0F62FE]">₹{parseFloat(policy?.remaining_coverage || 0).toLocaleString()}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-[11px]">Deductible:</span>
              <span className="font-mono">₹{parseFloat(policy?.deductible || 0).toLocaleString()}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-[11px]">Coverage Window:</span>
              <span className="font-mono text-[11px] text-gray-600">{policy?.start_date} to {policy?.end_date}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Claim Particulars & Explainable Decision Card */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Claim Particulars */}
        <div className="lg:col-span-2 bg-white border border-[#E0E0E0] p-4 rounded-sm shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-2.5 border-b border-gray-100">
            <div className="flex items-center space-x-2">
              <Building className="w-4 h-4 text-[#0F62FE]" />
              <h2 className="text-xs font-bold uppercase tracking-wider font-mono text-[#161616]">
                Billing & Hospitalization Records
              </h2>
            </div>
            <span className="text-base font-bold text-gray-900 font-mono">
              ₹{parseFloat(claim.claim_amount).toLocaleString('en-IN')}
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
            <div>
              <span className="text-gray-500 block text-[11px]">Hospital Name:</span>
              <span className="font-semibold text-gray-900">{claim.hospital_name || 'N/A'}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-[11px]">Hospital Invoice #:</span>
              <span className="font-mono font-semibold text-gray-900">{claim.hospital_invoice_number || 'N/A'}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-[11px]">Diagnosis Code:</span>
              <span className="font-mono font-semibold text-[#0F62FE]">{claim.diagnosis_code || 'N/A'}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-[11px]">Incident Date:</span>
              <span className="font-mono">{claim.incident_date}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-[11px]">Admission Date:</span>
              <span className="font-mono">{claim.admission_date || 'N/A'}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-[11px]">Discharge Date:</span>
              <span className="font-mono">{claim.discharge_date || 'N/A'}</span>
            </div>
          </div>

          <div>
            <span className="text-gray-500 block text-[11px]">Diagnosis Description:</span>
            <p className="text-xs text-gray-800 mt-0.5 bg-gray-50 p-2 rounded border border-gray-100">
              {claim.diagnosis_description || 'No diagnosis narrative recorded.'}
            </p>
          </div>

          {claim.decision_notes && (
            <div className="p-3 bg-blue-50 border border-blue-200 rounded text-xs">
              <span className="font-semibold text-blue-900 block">Adjudication Notes by {claim.reviewed_by || 'Examiner'}:</span>
              <p className="text-blue-800 mt-1">{claim.decision_notes}</p>
            </div>
          )}
        </div>

        {/* AI Explainable Recommendation Box */}
        <div className="bg-white border border-[#E0E0E0] p-4 rounded-sm shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center space-x-2 pb-2.5 border-b border-gray-100 text-[#0F62FE]">
              <Sparkles className="w-4 h-4" />
              <h2 className="text-xs font-bold uppercase tracking-wider font-mono">
                AI Advisory Recommendation
              </h2>
            </div>

            <div className="mt-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-600">Calculated Risk:</span>
                <RiskScoreBadge score={claim.risk_score} level={claim.risk_level} />
              </div>

              <div className="p-2.5 rounded bg-gray-50 border border-gray-100 mt-2">
                <span className="text-[10px] font-mono text-gray-500 uppercase">Recommendation:</span>
                <p className="text-sm font-bold text-gray-900">
                  {report?.risk_assessment?.recommendation || 'ADVISORY READY'}
                </p>
              </div>

              {report?.risk_assessment?.reasons?.length > 0 && (
                <div className="mt-3">
                  <span className="text-[11px] font-semibold text-gray-700 block mb-1">Identified Factors:</span>
                  <ul className="text-[11px] text-[#525252] space-y-1 list-disc list-inside">
                    {report.risk_assessment.reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

          <div className="pt-3 border-t border-gray-100 mt-4">
            <p className="text-[10px] text-gray-400 italic">
              Human-in-the-Loop Required: AI outputs are advisory only. Final decision belongs to an authorized claims examiner.
            </p>
          </div>
        </div>
      </div>

      {/* Documents & SHA-256 Hashes Table */}
      <div className="bg-white border border-[#E0E0E0] rounded-sm shadow-sm overflow-hidden">
        <div className="p-3 bg-[#FAFAFA] border-b border-[#E0E0E0] flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <FileText className="w-4 h-4 text-[#0F62FE]" />
            <h2 className="text-xs font-bold uppercase tracking-wider font-mono text-[#161616]">
              Attached Medical Evidence (IBM Db2: DOCUMENT_RECORDS)
            </h2>
          </div>
          <span className="text-[11px] text-gray-500">{documents?.length || 0} document(s) uploaded</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F4F4F4] text-[#525252] border-b border-[#E0E0E0] uppercase font-mono text-[10px]">
              <tr>
                <th className="py-2.5 px-3">Document Name</th>
                <th className="py-2.5 px-3">Category</th>
                <th className="py-2.5 px-3">File Size</th>
                <th className="py-2.5 px-3">Cryptographic SHA-256 Hash</th>
                <th className="py-2.5 px-3">Uploaded At</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {documents?.length === 0 ? (
                <tr>
                  <td colSpan="5" className="py-6 text-center text-gray-400 text-xs">
                    No documents attached to this claim.
                  </td>
                </tr>
              ) : (
                documents.map((d) => (
                  <tr key={d.DOCUMENT_ID || d.document_id} className="hover:bg-gray-50">
                    <td className="py-2.5 px-3 font-medium text-gray-900 flex items-center space-x-1.5">
                      <FileCheck className="w-3.5 h-3.5 text-emerald-600" />
                      <span>{d.DOCUMENT_NAME || d.document_name}</span>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-gray-600">{d.DOCUMENT_TYPE || d.document_type}</td>
                    <td className="py-2.5 px-3 text-gray-600 font-mono">
                      {((d.FILE_SIZE_BYTES || d.file_size_bytes || 0) / 1024).toFixed(1)} KB
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-gray-500 max-w-xs truncate" title={d.FILE_HASH || d.file_hash}>
                      {d.FILE_HASH || d.file_hash}
                    </td>
                    <td className="py-2.5 px-3 text-gray-500 font-mono text-[11px]">
                      {(d.UPLOADED_AT || d.uploaded_at)?.slice(0, 19)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Multi-Agent Audit Trail (Db2 VERIFICATION_LOGS) */}
      <div className="bg-white border border-[#E0E0E0] rounded-sm shadow-sm overflow-hidden">
        <div className="p-3 bg-[#FAFAFA] border-b border-[#E0E0E0] flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Clock className="w-4 h-4 text-[#0F62FE]" />
            <h2 className="text-xs font-bold uppercase tracking-wider font-mono text-[#161616]">
              Agentic Verification Trail (IBM Db2: VERIFICATION_LOGS)
            </h2>
          </div>
          <span className="text-[11px] text-gray-500">{verification_logs?.length || 0} step(s) recorded</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F4F4F4] text-[#525252] border-b border-[#E0E0E0] uppercase font-mono text-[10px]">
              <tr>
                <th className="py-2.5 px-3">Agent Name</th>
                <th className="py-2.5 px-3">Action Executed</th>
                <th className="py-2.5 px-3">Outcome</th>
                <th className="py-2.5 px-3">Details / Audit Evidence</th>
                <th className="py-2.5 px-3">Latency</th>
                <th className="py-2.5 px-3">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 font-mono">
              {verification_logs?.length === 0 ? (
                <tr>
                  <td colSpan="6" className="py-6 text-center text-gray-400 text-xs">
                    No verification steps recorded yet. Click "Run Agentic Verification" above.
                  </td>
                </tr>
              ) : (
                verification_logs.map((log) => (
                  <tr key={log.LOG_ID || log.log_id} className="hover:bg-gray-50 text-[11px]">
                    <td className="py-2.5 px-3 font-semibold text-[#0F62FE]">{log.AGENT_NAME || log.agent_name}</td>
                    <td className="py-2.5 px-3 text-gray-800">{log.ACTION || log.action}</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                          (log.STATUS || log.status) === 'SUCCESS'
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {log.STATUS || log.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-gray-600 font-sans max-w-sm truncate" title={log.DETAILS || log.details}>
                      {log.DETAILS || log.details}
                    </td>
                    <td className="py-2.5 px-3 text-gray-500">
                      {log.EXECUTION_TIME_MS || log.execution_time_ms || 0}ms
                    </td>
                    <td className="py-2.5 px-3 text-gray-400">
                      {(log.CREATED_AT || log.created_at)?.slice(11, 19)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Human Adjudication Modal */}
      {showDecisionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white border border-[#E0E0E0] shadow-xl rounded-sm max-w-md w-full p-6 text-left">
            <h3 className="font-bold text-base text-[#161616]">
              Confirm Claim Adjudication: <span className="uppercase text-[#0F62FE]">{decisionType}</span>
            </h3>
            <p className="text-xs text-gray-500 mt-1">
              Authorized human examiner decision. Updates IBM Db2 CLAIM_RECORDS and deducts remaining coverage if approved.
            </p>

            <div className="mt-4 space-y-3">
              {decisionType === 'APPROVED' && (
                <div>
                  <label className="block text-xs font-semibold text-[#161616] uppercase font-mono">
                    Approved Amount (INR ₹)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={decisionAmount}
                    onChange={(e) => setDecisionAmount(e.target.value)}
                    className="mt-1 w-full p-2 bg-[#F4F4F4] border border-[#E0E0E0] text-xs font-mono font-semibold text-[#161616] rounded-sm focus:outline-none focus:border-[#0F62FE]"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-[#161616] uppercase font-mono">
                  Adjudication Narrative & Notes
                </label>
                <textarea
                  rows="3"
                  value={decisionNotes}
                  onChange={(e) => setDecisionNotes(e.target.value)}
                  placeholder="Explain rationale for this decision..."
                  className="mt-1 w-full p-2 bg-[#F4F4F4] border border-[#E0E0E0] text-xs text-[#161616] rounded-sm focus:outline-none focus:border-[#0F62FE]"
                ></textarea>
              </div>
            </div>

            <div className="mt-5 flex justify-end space-x-2">
              <button
                onClick={() => setShowDecisionModal(false)}
                className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100 rounded-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitDecision}
                disabled={submittingDecision}
                className="px-4 py-1.5 bg-[#0F62FE] text-white text-xs font-medium hover:bg-[#0353E9] rounded-sm shadow-sm"
              >
                {submittingDecision ? 'Persisting to Db2...' : 'Commit Adjudication'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
