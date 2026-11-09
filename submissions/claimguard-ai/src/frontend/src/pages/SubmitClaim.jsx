import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FilePlus,
  Upload,
  FileCheck,
  AlertCircle,
  Building,
  User,
  Shield,
  Calendar,
  Sparkles,
  ArrowRight
} from 'lucide-react';
import { apiClient } from '../api/client';

export default function SubmitClaim() {
  const navigate = useNavigate();
  const [customers, setCustomers] = useState([]);
  const [policies, setPolicies] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Form Fields
  const [customerId, setCustomerId] = useState('CUST-001');
  const [policyId, setPolicyId] = useState('POL-1001');
  const [hospitalName, setHospitalName] = useState('Apollo Hospitals Lucknow');
  const [invoiceNumber, setInvoiceNumber] = useState(`INV-${Math.floor(1000 + Math.random() * 9000)}`);
  const [claimAmount, setClaimAmount] = useState('45000.00');
  const [incidentDate, setIncidentDate] = useState('2026-10-15');
  const [admissionDate, setAdmissionDate] = useState('2026-10-15');
  const [dischargeDate, setDischargeDate] = useState('2026-10-18');
  const [diagnosisCode, setDiagnosisCode] = useState('A09');
  const [diagnosisDesc, setDiagnosisDesc] = useState('Infectious gastroenteritis and colitis');
  const [selectedFile, setSelectedFile] = useState(null);
  const [docType, setDocType] = useState('MEDICAL_BILL');

  useEffect(() => {
    async function loadMetadata() {
      try {
        const [custRes, polRes] = await Promise.all([
          apiClient.getCustomers(),
          apiClient.getPolicies()
        ]);
        setCustomers(custRes.data);
        setPolicies(polRes.data);
      } catch (err) {
        console.error('Failed to prefetch metadata:', err);
      }
    }
    loadMetadata();
  }, []);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      // 1. Create Claim in Db2
      const claimPayload = {
        customer_id: customerId,
        policy_id: policyId,
        claim_amount: parseFloat(claimAmount),
        incident_date: incidentDate,
        admission_date: admissionDate,
        discharge_date: dischargeDate,
        hospital_name: hospitalName,
        hospital_invoice_number: invoiceNumber,
        diagnosis_code: diagnosisCode,
        diagnosis_description: diagnosisDesc
      };

      const res = await apiClient.submitClaim(claimPayload);
      const claimId = res.data.claim_id;

      // 2. Upload Document if provided
      if (selectedFile) {
        await apiClient.uploadDocument(claimId, selectedFile, docType);
      }

      // 3. Automatically trigger multi-agent LangGraph workflow
      try {
        await apiClient.triggerVerification(claimId);
      } catch (agentErr) {
        console.warn('Initial agent trigger warning:', agentErr);
      }

      // Navigate to detail view
      navigate(`/claims/${claimId}`);
    } catch (err) {
      setError(err.message || 'Failed to submit claim. Verify inputs.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Title */}
      <div className="pb-3 border-b border-[#E0E0E0]">
        <div className="flex items-center space-x-2">
          <div className="p-1.5 bg-[#EDF5FF] text-[#0F62FE] rounded">
            <FilePlus className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-[#161616]">Submit New Insurance Claim</h1>
            <p className="text-xs text-[#525252]">
              Ingest claim records into IBM Db2 and initiate LangGraph autonomous verification
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Section 1: Customer & Policy Information */}
        <div className="bg-white border border-[#E0E0E0] p-5 rounded-sm shadow-sm">
          <div className="flex items-center space-x-2 pb-3 mb-4 border-b border-gray-100">
            <User className="w-4 h-4 text-[#0F62FE]" />
            <h2 className="text-xs font-bold uppercase tracking-wider font-mono text-[#161616]">
              1. Policyholder & Coverage Details
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#161616] uppercase font-mono">
                Select Customer ID
              </label>
              <select
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
                className="mt-1 w-full p-2 bg-[#F4F4F4] border border-[#E0E0E0] text-xs text-[#161616] rounded-sm focus:outline-none focus:border-[#0F62FE] font-mono"
              >
                {customers.map((c) => (
                  <option key={c.customer_id} value={c.customer_id}>
                    {c.customer_id} — {c.first_name} {c.last_name}
                  </option>
                ))}
                {!customers.length && <option value="CUST-001">CUST-001 — Aarav Sharma</option>}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#161616] uppercase font-mono">
                Select Insurance Policy
              </label>
              <select
                value={policyId}
                onChange={(e) => setPolicyId(e.target.value)}
                className="mt-1 w-full p-2 bg-[#F4F4F4] border border-[#E0E0E0] text-xs text-[#161616] rounded-sm focus:outline-none focus:border-[#0F62FE] font-mono"
              >
                {policies.map((p) => (
                  <option key={p.policy_id} value={p.policy_id}>
                    {p.policy_id} — {p.policy_number} (₹{p.remaining_coverage.toLocaleString()} remaining)
                  </option>
                ))}
                {!policies.length && <option value="POL-1001">POL-1001 — POL-MED-2026-001</option>}
              </select>
            </div>
          </div>
        </div>

        {/* Section 2: Hospital & Financial Particulars */}
        <div className="bg-white border border-[#E0E0E0] p-5 rounded-sm shadow-sm">
          <div className="flex items-center space-x-2 pb-3 mb-4 border-b border-gray-100">
            <Building className="w-4 h-4 text-[#0F62FE]" />
            <h2 className="text-xs font-bold uppercase tracking-wider font-mono text-[#161616]">
              2. Hospitalization & Billing Particulars
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#161616] uppercase font-mono">
                Hospital / Provider Name
              </label>
              <input
                type="text"
                value={hospitalName}
                onChange={(e) => setHospitalName(e.target.value)}
                required
                className="mt-1 w-full p-2 bg-[#F4F4F4] border border-[#E0E0E0] text-xs text-[#161616] rounded-sm focus:outline-none focus:border-[#0F62FE]"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#161616] uppercase font-mono">
                Hospital Invoice #
              </label>
              <input
                type="text"
                value={invoiceNumber}
                onChange={(e) => setInvoiceNumber(e.target.value)}
                required
                className="mt-1 w-full p-2 bg-[#F4F4F4] border border-[#E0E0E0] text-xs text-[#161616] rounded-sm focus:outline-none focus:border-[#0F62FE] font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#161616] uppercase font-mono">
                Claim Amount (INR ₹)
              </label>
              <input
                type="number"
                step="0.01"
                value={claimAmount}
                onChange={(e) => setClaimAmount(e.target.value)}
                required
                className="mt-1 w-full p-2 bg-[#F4F4F4] border border-[#E0E0E0] text-xs text-[#161616] rounded-sm focus:outline-none focus:border-[#0F62FE] font-mono font-semibold"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
            <div>
              <label className="block text-xs font-semibold text-[#161616] uppercase font-mono">
                Incident Date
              </label>
              <input
                type="date"
                value={incidentDate}
                onChange={(e) => setIncidentDate(e.target.value)}
                required
                className="mt-1 w-full p-2 bg-[#F4F4F4] border border-[#E0E0E0] text-xs text-[#161616] rounded-sm focus:outline-none focus:border-[#0F62FE]"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#161616] uppercase font-mono">
                Admission Date
              </label>
              <input
                type="date"
                value={admissionDate}
                onChange={(e) => setAdmissionDate(e.target.value)}
                className="mt-1 w-full p-2 bg-[#F4F4F4] border border-[#E0E0E0] text-xs text-[#161616] rounded-sm focus:outline-none focus:border-[#0F62FE]"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#161616] uppercase font-mono">
                Discharge Date
              </label>
              <input
                type="date"
                value={dischargeDate}
                onChange={(e) => setDischargeDate(e.target.value)}
                className="mt-1 w-full p-2 bg-[#F4F4F4] border border-[#E0E0E0] text-xs text-[#161616] rounded-sm focus:outline-none focus:border-[#0F62FE]"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
            <div>
              <label className="block text-xs font-semibold text-[#161616] uppercase font-mono">
                Diagnosis Code (ICD-10)
              </label>
              <input
                type="text"
                value={diagnosisCode}
                onChange={(e) => setDiagnosisCode(e.target.value)}
                className="mt-1 w-full p-2 bg-[#F4F4F4] border border-[#E0E0E0] text-xs text-[#161616] rounded-sm focus:outline-none focus:border-[#0F62FE] font-mono"
              />
            </div>

            <div className="md:col-span-2">
              <label className="block text-xs font-semibold text-[#161616] uppercase font-mono">
                Diagnosis Description
              </label>
              <input
                type="text"
                value={diagnosisDesc}
                onChange={(e) => setDiagnosisDesc(e.target.value)}
                className="mt-1 w-full p-2 bg-[#F4F4F4] border border-[#E0E0E0] text-xs text-[#161616] rounded-sm focus:outline-none focus:border-[#0F62FE]"
              />
            </div>
          </div>
        </div>

        {/* Section 3: Document Upload */}
        <div className="bg-white border border-[#E0E0E0] p-5 rounded-sm shadow-sm">
          <div className="flex items-center space-x-2 pb-3 mb-4 border-b border-gray-100">
            <Upload className="w-4 h-4 text-[#0F62FE]" />
            <h2 className="text-xs font-bold uppercase tracking-wider font-mono text-[#161616]">
              3. Supporting Document Evidence (PDF or Image)
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#161616] uppercase font-mono">
                Document Category
              </label>
              <select
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
                className="mt-1 w-full p-2 bg-[#F4F4F4] border border-[#E0E0E0] text-xs text-[#161616] rounded-sm focus:outline-none focus:border-[#0F62FE]"
              >
                <option value="MEDICAL_BILL">Hospital / Medical Bill</option>
                <option value="DISCHARGE_SUMMARY">Discharge Summary</option>
                <option value="PRESCRIPTION">Physician Prescription</option>
                <option value="IDENTITY_PROOF">Government Identity Proof</option>
              </select>
            </div>

            <div className="md:col-span-2">
              <label className="block text-xs font-semibold text-[#161616] uppercase font-mono">
                Upload File (PDF, PNG, JPG)
              </label>
              <div className="mt-1 flex items-center space-x-3">
                <input
                  type="file"
                  accept=".pdf,image/png,image/jpeg"
                  onChange={handleFileChange}
                  className="text-xs text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-sm file:border-0 file:text-xs file:font-semibold file:bg-[#EDF5FF] file:text-[#0F62FE] hover:file:bg-[#D0E2FF]"
                />
              </div>
              {selectedFile && (
                <p className="text-[11px] text-emerald-700 mt-1 flex items-center space-x-1">
                  <FileCheck className="w-3.5 h-3.5" />
                  <span>Selected: {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)</span>
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <div className="flex justify-end space-x-3">
          <button
            type="submit"
            disabled={submitting}
            className="flex items-center space-x-2 px-5 py-2.5 bg-[#0F62FE] hover:bg-[#0353E9] text-white text-xs font-semibold rounded-sm shadow-sm transition-colors"
          >
            <Sparkles className="w-4 h-4" />
            <span>{submitting ? 'Submitting & Initiating Agents...' : 'Submit Claim & Launch AI Verification'}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
