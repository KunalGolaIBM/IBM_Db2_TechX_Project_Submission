import React, { useState } from 'react';
import { 
  AlertTriangle, 
  CheckCircle2, 
  HelpCircle, 
  DollarSign, 
  Plus, 
  Trash2, 
  Sparkles, 
  FileText, 
  ArrowRight, 
  ShieldCheck, 
  Building2, 
  Printer, 
  Check, 
  Info,
  Clock
} from 'lucide-react';
import { CLINICAL_PRESETS } from '../data/db2MockDatabase';
import { AuditReport, PatientPrescription } from '../types/medaudit';

interface AuditWorkspaceProps {
  onOpenDB2: () => void;
}

export const AuditWorkspace: React.FC<AuditWorkspaceProps> = ({ onOpenDB2 }) => {
  const [selectedPresetIndex, setSelectedPresetIndex] = useState<number>(0);
  const [prescription, setPrescription] = useState<PatientPrescription>(CLINICAL_PRESETS[0]);
  const [isAuditing, setIsAuditing] = useState<boolean>(false);
  const [auditStep, setAuditStep] = useState<number>(0);
  const [auditReport, setAuditReport] = useState<AuditReport | null>(null);
  const [newTestName, setNewTestName] = useState<string>('');
  const [newTestCategory, setNewTestCategory] = useState<'Radiology' | 'Biochemistry' | 'Pathology' | 'Genetics' | 'Cardiology'>('Radiology');
  const [newTestPrice, setNewTestPrice] = useState<number>(150);
  const [isAddingTest, setIsAddingTest] = useState<boolean>(false);
  const [printSuccess, setPrintSuccess] = useState<boolean>(false);

  // Load a preset
  const handleSelectPreset = (index: number) => {
    setSelectedPresetIndex(index);
    setPrescription(CLINICAL_PRESETS[index]);
    setAuditReport(null);
  };

  // Add custom test
  const handleAddTest = () => {
    if (!newTestName.trim()) return;
    setPrescription(prev => ({
      ...prev,
      tests: [
        ...prev.tests,
        {
          testName: newTestName.trim(),
          category: newTestCategory,
          price: Number(newTestPrice) || 50
        }
      ]
    }));
    setNewTestName('');
    setIsAddingTest(false);
  };

  // Remove test
  const handleRemoveTest = (indexToRemove: number) => {
    setPrescription(prev => ({
      ...prev,
      tests: prev.tests.filter((_, idx) => idx !== indexToRemove)
    }));
  };

  // Execute LangChain & DB2 Audit
  const handleRunAudit = async () => {
    setIsAuditing(true);
    setAuditStep(1);
    setAuditReport(null);

    // Step animation sequence
    setTimeout(() => setAuditStep(2), 600);
    setTimeout(() => setAuditStep(3), 1200);
    setTimeout(() => setAuditStep(4), 1800);

    try {
      const response = await fetch('/api/audit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(prescription)
      });

      if (!response.ok) {
        throw new Error('Audit request failed');
      }

      const report: AuditReport = await response.json();
      setTimeout(() => {
        setAuditReport(report);
        setIsAuditing(false);
        setAuditStep(0);
      }, 2200);
    } catch (err) {
      console.error('Audit failed:', err);
      setIsAuditing(false);
      setAuditStep(0);
    }
  };

  const handlePrintDossier = () => {
    setPrintSuccess(true);
    setTimeout(() => {
      window.print();
      setPrintSuccess(false);
    }, 300);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      
      {/* Hero Explainer & Quick Preset Selector */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 sm:p-8 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-sky-700 uppercase tracking-wider mb-1">
              <span>IBM DB2 Evidence-Based Clinical Audit</span>
              <span aria-hidden="true">·</span>
              <span>LangChain Reasoning Engine</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
              Prescription Audit & Test Necessity Verifier
            </h1>
            <p className="mt-1 text-sm text-slate-600 max-w-3xl">
              Cross-reference diagnostic tests prescribed by your doctor against evidence-based medical guidelines (NICE, WHO, ICMR) and IBM DB2 lab commission kickback registries.
            </p>
          </div>

          <button
            onClick={onOpenDB2}
            className="self-start md:self-auto px-3.5 py-2 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors flex items-center gap-1.5 whitespace-nowrap shrink-0"
          >
            <span>View DB2 Schema & SQL</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Clinical Scenarios Bar */}
        <div className="mt-6">
          <div className="flex items-center justify-between mb-2.5">
            <label className="block text-xs font-semibold text-slate-700">
              Select a Real-World Audit Case Study:
            </label>
            <span className="text-[11px] text-slate-500 font-mono">{CLINICAL_PRESETS.length} cases · powered by IBM DB2</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {CLINICAL_PRESETS.map((preset, idx) => {
              const totalBill = preset.tests.reduce((acc, t) => acc + t.price, 0);
              const riskColors = [
                'border-red-300 bg-red-50/60',    // High-kickback cases
                'border-orange-300 bg-orange-50/60',
                'border-amber-300 bg-amber-50/60',
                'border-rose-300 bg-rose-50/60',
                'border-purple-300 bg-purple-50/60',
              ];
              return (
                <button
                  key={preset.patientName}
                  onClick={() => handleSelectPreset(idx)}
                  className={`text-left p-3.5 rounded-lg border-2 transition-all ${
                    selectedPresetIndex === idx
                      ? 'border-sky-500 bg-sky-50/70 shadow-md ring-1 ring-sky-500'
                      : `${riskColors[idx % riskColors.length]} hover:opacity-90 hover:shadow-sm`
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-slate-900">
                      Case {idx + 1}: {preset.patientName}
                    </span>
                    <span className="text-[11px] font-mono font-bold text-slate-700 tabular-nums bg-white/70 px-1.5 py-0.5 rounded">
                      ${totalBill}
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] text-slate-700 line-clamp-2 leading-snug">
                    {preset.chiefComplaint}
                  </p>
                  <div className="mt-2 flex items-center justify-between text-[10px] text-slate-500">
                    <span className="truncate max-w-[70%]">{preset.doctorName.replace('Dr. ', '')}</span>
                    <span className="font-mono shrink-0">{preset.tests.length} tests ordered</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main Grid: Left = Prescription Details, Right = Audit & Results */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        
        {/* Left Column: Prescription Form & Tests (5 cols) */}
        <div className="lg:col-span-5 bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-5">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <FileText className="w-4 h-4 text-sky-600" />
              Patient Encounter & Orders
            </h2>
            <span className="text-xs text-slate-500 font-mono">DB2 Table: ENCOUNTERS</span>
          </div>

          {/* Patient Details */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block font-medium text-slate-700 mb-1">Patient Name</label>
              <input
                type="text"
                value={prescription.patientName}
                onChange={(e) => setPrescription({ ...prescription, patientName: e.target.value })}
                className="w-full px-3 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-sky-500 text-slate-900 bg-slate-50/50"
              />
            </div>
            <div>
              <label className="block font-medium text-slate-700 mb-1">Age & Gender</label>
              <div className="flex gap-2">
                <input
                  type="number"
                  value={prescription.age}
                  onChange={(e) => setPrescription({ ...prescription, age: parseInt(e.target.value) || 30 })}
                  className="w-20 px-3 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-sky-500 text-slate-900 bg-slate-50/50"
                />
                <select
                  value={prescription.gender}
                  onChange={(e) => setPrescription({ ...prescription, gender: e.target.value as any })}
                  className="flex-1 px-2.5 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-sky-500 text-slate-900 bg-slate-50/50"
                >
                  <option value="Female">Female</option>
                  <option value="Male">Male</option>
                  <option value="Other">Other</option>
                </select>
              </div>
            </div>
          </div>

          {/* Chief Complaint & Symptoms */}
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Chief Complaint & Symptoms
            </label>
            <textarea
              rows={2}
              value={prescription.chiefComplaint}
              onChange={(e) => setPrescription({ ...prescription, chiefComplaint: e.target.value })}
              className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-sky-500 text-slate-900 bg-slate-50/50"
              placeholder="e.g. Mild sore throat, runny nose for 3 days"
            />
          </div>

          {/* Doctor & Lab Details */}
          <div className="p-3.5 bg-slate-50 border border-slate-100 rounded-lg space-y-2.5 text-xs">
            <div>
              <label className="block font-medium text-slate-700 mb-0.5">Prescribing Doctor</label>
              <input
                type="text"
                value={prescription.doctorName}
                onChange={(e) => setPrescription({ ...prescription, doctorName: e.target.value })}
                className="w-full px-2.5 py-1.5 border border-slate-200 rounded-md bg-white text-slate-900"
              />
            </div>
            <div>
              <label className="block font-medium text-slate-700 mb-0.5">Doctor Specialty</label>
              <input
                type="text"
                value={prescription.doctorSpecialty}
                onChange={(e) => setPrescription({ ...prescription, doctorSpecialty: e.target.value })}
                className="w-full px-2.5 py-1.5 border border-slate-200 rounded-md bg-white text-slate-900"
              />
            </div>
            <div>
              <label className="block font-medium text-slate-700 mb-0.5">Recommended Diagnostic Center</label>
              <input
                type="text"
                value={prescription.recommendedLabName}
                onChange={(e) => setPrescription({ ...prescription, recommendedLabName: e.target.value })}
                className="w-full px-2.5 py-1.5 border border-slate-200 rounded-md bg-white text-slate-900"
              />
            </div>
          </div>

          {/* Prescribed Tests Table */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-900">
                Prescribed Tests ({prescription.tests.length})
              </span>
              <button
                type="button"
                onClick={() => setIsAddingTest(!isAddingTest)}
                className="text-xs text-sky-700 hover:text-sky-800 font-medium flex items-center gap-1"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Test
              </button>
            </div>

            {/* Test adding input box */}
            {isAddingTest && (
              <div className="p-3 bg-sky-50/50 border border-sky-100 rounded-lg space-y-2 text-xs">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Test Name</label>
                  <input
                    type="text"
                    value={newTestName}
                    onChange={(e) => setNewTestName(e.target.value)}
                    placeholder="e.g. Brain MRI, Serum Ferritin"
                    className="w-full px-2.5 py-1 border border-slate-200 rounded-md bg-white"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block font-medium text-slate-700 mb-1">Category</label>
                    <select
                      value={newTestCategory}
                      onChange={(e) => setNewTestCategory(e.target.value as any)}
                      className="w-full px-2 py-1 border border-slate-200 rounded-md bg-white"
                    >
                      <option value="Radiology">Radiology</option>
                      <option value="Biochemistry">Biochemistry</option>
                      <option value="Pathology">Pathology</option>
                      <option value="Genetics">Genetics</option>
                      <option value="Cardiology">Cardiology</option>
                    </select>
                  </div>
                  <div>
                    <label className="block font-medium text-slate-700 mb-1">Price ($)</label>
                    <input
                      type="number"
                      value={newTestPrice}
                      onChange={(e) => setNewTestPrice(Number(e.target.value))}
                      className="w-full px-2.5 py-1 border border-slate-200 rounded-md bg-white font-mono"
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => setIsAddingTest(false)}
                    className="px-2.5 py-1 rounded text-slate-600 hover:bg-slate-100"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleAddTest}
                    className="px-3 py-1 bg-sky-700 text-white rounded font-medium hover:bg-sky-800"
                  >
                    Add
                  </button>
                </div>
              </div>
            )}

            <div className="divide-y divide-slate-100 border border-slate-200 rounded-lg overflow-hidden max-h-64 overflow-y-auto">
              {prescription.tests.map((test, index) => (
                <div key={index} className="p-2.5 flex items-center justify-between text-xs hover:bg-slate-50/80 transition-colors">
                  <div className="pr-2">
                    <p className="font-medium text-slate-900 leading-snug">{test.testName}</p>
                    <p className="text-[11px] text-slate-500">{test.category}</p>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="font-mono tabular-nums font-semibold text-slate-900">
                      ${test.price}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleRemoveTest(index)}
                      className="text-slate-400 hover:text-red-600 p-1 rounded transition-colors"
                      title="Remove test"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* Total Ordered Price */}
            <div className="flex items-center justify-between pt-2 px-1 text-xs">
              <span className="text-slate-600">Total Billed Diagnostic Cost:</span>
              <span className="font-mono tabular-nums text-sm font-bold text-slate-900">
                ${prescription.tests.reduce((acc, t) => acc + t.price, 0)}
              </span>
            </div>
          </div>

          {/* Primary Action Button */}
          <button
            type="button"
            disabled={isAuditing || prescription.tests.length === 0}
            onClick={handleRunAudit}
            className={`w-full py-3 px-4 rounded-lg font-semibold text-sm transition-all shadow-xs flex items-center justify-center gap-2 ${
              isAuditing
                ? 'bg-sky-200 text-sky-800 cursor-wait'
                : 'bg-sky-700 hover:bg-sky-800 active:scale-99 text-white'
            }`}
          >
            {isAuditing ? (
              <>
                <Clock className="w-4 h-4 animate-spin" />
                <span>Running DB2 & LangChain Audit...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Audit Diagnostic Necessity</span>
              </>
            )}
          </button>
        </div>

        {/* Right Column: Audit Timeline & Detailed Report (7 cols) */}
        <div className="lg:col-span-7 space-y-6">

          {/* Loading Animation Card */}
          {isAuditing && (
            <div className="bg-white border border-sky-200 rounded-xl p-6 shadow-xs space-y-4 animate-pulse">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <span className="text-xs font-semibold text-sky-800">
                  LangChain Agent Workflow in Progress
                </span>
                <span className="text-xs font-mono text-sky-600 tabular-nums">Phase {auditStep}/4</span>
              </div>

              <div className="space-y-3 text-xs">
                <div className={`flex items-center gap-2.5 ${auditStep >= 1 ? 'text-slate-900 font-medium' : 'text-slate-400'}`}>
                  <div className={`w-2.5 h-2.5 rounded-full ${auditStep >= 1 ? 'bg-sky-600 animate-ping' : 'bg-slate-300'}`} />
                  <span>1. Parsing clinical symptoms, duration, and doctor examination notes</span>
                </div>
                <div className={`flex items-center gap-2.5 ${auditStep >= 2 ? 'text-slate-900 font-medium' : 'text-slate-400'}`}>
                  <div className={`w-2.5 h-2.5 rounded-full ${auditStep >= 2 ? 'bg-sky-600' : 'bg-slate-300'}`} />
                  <span>2. Querying IBM DB2: Table CLINICAL_GUIDELINES for evidence-based protocols (NICE/WHO)</span>
                </div>
                <div className={`flex items-center gap-2.5 ${auditStep >= 3 ? 'text-slate-900 font-medium' : 'text-slate-400'}`}>
                  <div className={`w-2.5 h-2.5 rounded-full ${auditStep >= 3 ? 'bg-sky-600' : 'bg-slate-300'}`} />
                  <span>3. Querying IBM DB2: Table LAB_COMMISSION_CONTRACTS & suspicious referral ties</span>
                </div>
                <div className={`flex items-center gap-2.5 ${auditStep >= 4 ? 'text-slate-900 font-medium' : 'text-slate-400'}`}>
                  <div className={`w-2.5 h-2.5 rounded-full ${auditStep >= 4 ? 'bg-sky-600' : 'bg-slate-300'}`} />
                  <span>4. Synthesizing itemized necessity breakdown & patient second-opinion report</span>
                </div>
              </div>
            </div>
          )}

          {/* Zero State View (Before Audit) */}
          {!isAuditing && !auditReport && (
            <div className="bg-white border border-slate-200 rounded-xl p-8 text-center space-y-4 shadow-xs">
              <div className="w-12 h-12 rounded-full bg-slate-100 mx-auto flex items-center justify-center text-slate-500">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <div className="max-w-md mx-auto">
                <h3 className="text-base font-bold text-slate-900">
                  Ready to Audit Test Orders
                </h3>
                <p className="mt-1 text-xs text-slate-600 leading-relaxed">
                  Review the patient encounter details on the left, add or modify tests as needed, and click <strong>"Audit Diagnostic Necessity"</strong> to verify against clinical protocols.
                </p>
              </div>
              <div className="pt-2">
                <button
                  type="button"
                  onClick={handleRunAudit}
                  className="px-4 py-2 bg-slate-900 text-white rounded-lg text-xs font-semibold hover:bg-slate-800 transition-colors shadow-xs"
                >
                  Run Audit on Selected Case
                </button>
              </div>
            </div>
          )}

          {/* Results View (After Audit Complete) */}
          {auditReport && (
            <div className="space-y-6">
              
              {/* Financial & Findings KPI Strip */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-100">
                  <div>
                    <span className="text-[11px] font-mono text-slate-500">
                      Audit Reference: {auditReport.auditId}
                    </span>
                    <h3 className="text-lg font-bold text-slate-900">
                      Clinical Audit Summary
                    </h3>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-bold px-2.5 py-1 rounded-md ${
                      auditReport.kickbackRiskLevel === 'High Risk'
                        ? 'bg-red-50 text-red-700 border border-red-200'
                        : auditReport.kickbackRiskLevel === 'Moderate Risk'
                        ? 'bg-amber-50 text-amber-700 border border-amber-200'
                        : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    }`}>
                      {auditReport.kickbackRiskLevel}
                    </span>

                    <button
                      onClick={handlePrintDossier}
                      className="px-3 py-1 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-md transition-colors flex items-center gap-1.5"
                    >
                      {printSuccess ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Printer className="w-3.5 h-3.5" />}
                      Print Dossier
                    </button>
                  </div>
                </div>

                {/* 4-Stat Metric Row */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3 bg-slate-50 rounded-lg">
                    <span className="text-[11px] text-slate-500 block">Total Billed</span>
                    <span className="text-lg font-bold text-slate-900 font-mono tabular-nums">
                      ${auditReport.totalOrderedCost}
                    </span>
                  </div>
                  <div className="p-3 bg-emerald-50/70 border border-emerald-100 rounded-lg">
                    <span className="text-[11px] text-emerald-700 block font-medium">Justified Care</span>
                    <span className="text-lg font-bold text-emerald-800 font-mono tabular-nums">
                      ${auditReport.justifiedCost}
                    </span>
                  </div>
                  <div className="p-3 bg-red-50/70 border border-red-100 rounded-lg">
                    <span className="text-[11px] text-red-700 block font-medium">Unwarranted Waste</span>
                    <span className="text-lg font-bold text-red-800 font-mono tabular-nums">
                      ${auditReport.unwarrantedCost}
                    </span>
                  </div>
                  <div className="p-3 bg-sky-50 border border-sky-100 rounded-lg">
                    <span className="text-[11px] text-sky-700 block font-semibold">Potential Savings</span>
                    <span className="text-lg font-extrabold text-sky-800 font-mono tabular-nums">
                      ${auditReport.potentialSavings}
                    </span>
                  </div>
                </div>

                {/* Savings % Progress Bar */}
                {(() => {
                  const savingsPct = auditReport.totalOrderedCost > 0
                    ? Math.round((auditReport.potentialSavings / auditReport.totalOrderedCost) * 100)
                    : 0;
                  const unwarrantedCount = auditReport.testEvaluations.filter(t => t.necessityTier === 'unwarranted').length;
                  return (
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-slate-600 font-medium">
                          Billing Overcharge Rate: <span className="font-bold text-red-700">{savingsPct}% of total bill is unwarranted</span>
                        </span>
                        <span className="font-mono text-slate-500">
                          {unwarrantedCount}/{auditReport.totalTestsOrdered} tests flagged
                        </span>
                      </div>
                      <div className="h-2.5 bg-slate-200 rounded-full overflow-hidden flex">
                        <div
                          className="h-full bg-emerald-500 rounded-l-full transition-all duration-700"
                          style={{ width: `${100 - savingsPct}%` }}
                        />
                        <div
                          className="h-full bg-red-500 rounded-r-full transition-all duration-700"
                          style={{ width: `${savingsPct}%` }}
                        />
                      </div>
                      <div className="flex items-center gap-4 text-[10px] text-slate-500">
                        <span className="flex items-center gap-1"><span className="w-2 h-2 bg-emerald-500 rounded-full inline-block" />Clinically Justified</span>
                        <span className="flex items-center gap-1"><span className="w-2 h-2 bg-red-500 rounded-full inline-block" />Unwarranted / Kickback-Driven</span>
                      </div>
                    </div>
                  );
                })()}

                {/* Executive Verdict Callout */}
                <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-1.5">
                  <div className="flex items-center gap-1.5 font-bold text-slate-900">
                    <Info className="w-3.5 h-3.5 text-sky-600" />
                    <span>Clinical Reasoning & Guideline Match</span>
                  </div>
                  <p className="text-slate-700 leading-relaxed">
                    {auditReport.executiveSummary}
                  </p>
                  <p className="text-[11px] text-slate-500 pt-1">
                    Guideline Reference: <span className="font-medium text-slate-700">{auditReport.conditionDetected}</span>
                  </p>
                </div>
              </div>

              {/* Itemized Test Evaluation Cards */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
                <h4 className="text-sm font-bold text-slate-900">
                  Itemized Diagnostic Test Evaluations ({auditReport.testEvaluations.length})
                </h4>

                <div className="space-y-3">
                  {auditReport.testEvaluations.map((test) => {
                    const isUnwarranted = test.necessityTier === 'unwarranted';
                    const isEssential = test.necessityTier === 'essential';

                    return (
                      <div
                        key={test.id}
                        className={`p-4 rounded-lg border transition-all ${
                          isUnwarranted
                            ? 'border-red-200 bg-red-50/30'
                            : isEssential
                            ? 'border-emerald-200 bg-emerald-50/20'
                            : 'border-amber-200 bg-amber-50/20'
                        }`}
                      >
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2">
                          <div className="flex items-center gap-2">
                            {isUnwarranted ? (
                              <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
                            ) : isEssential ? (
                              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                            ) : (
                              <HelpCircle className="w-4 h-4 text-amber-600 shrink-0" />
                            )}
                            <span className="text-xs font-bold text-slate-900">
                              {test.testName}
                            </span>
                            <span className="text-[11px] text-slate-500 font-mono">
                              ({test.category})
                            </span>
                          </div>

                          <div className="flex items-center gap-3">
                            <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${
                              isUnwarranted
                                ? 'bg-red-100 text-red-800'
                                : isEssential
                                ? 'bg-emerald-100 text-emerald-800'
                                : 'bg-amber-100 text-amber-800'
                            }`}>
                              {isUnwarranted ? 'UNWARRANTED' : isEssential ? 'ESSENTIAL' : 'CONDITIONAL'}
                            </span>

                            <div className="text-right">
                              <span className="text-xs font-bold text-slate-900 font-mono tabular-nums">
                                ${test.orderedPrice}
                              </span>
                              <span className="text-[10px] text-slate-500 block">
                                Fair: ${test.benchmarkPrice}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Rationale Text */}
                        <p className="text-xs text-slate-700 leading-relaxed mt-1">
                          {test.clinicalReason}
                        </p>

                        {/* Lab Kickback Tag if flagged */}
                        {test.isLabCommissionFlagged && (
                          <div className="mt-2.5 p-2 bg-red-100/70 border border-red-200 rounded text-[11px] text-red-900 flex items-center justify-between">
                            <span className="font-semibold">
                              ⚠️ Lab Referral Kickback Flagged: {test.commissionPct}% commission arrangement in DB2
                            </span>
                            <span className="font-mono tabular-nums font-bold">
                              ~${test.potentialKickbackAmount} kickback
                            </span>
                          </div>
                        )}

                        {test.safeAlternativeRecommendation && (
                          <div className="mt-2 text-[11px] text-sky-800 flex items-center gap-1.5">
                            <span className="font-semibold">Clinical Alternative:</span>
                            <span>{test.safeAlternativeRecommendation}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Patient Actionable Next Steps */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-3">
                <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-sky-600" />
                  Recommended Action Plan for Patient
                </h4>

                <div className="space-y-2 text-xs text-slate-700">
                  {auditReport.patientActionSteps.map((step, idx) => (
                    <div key={idx} className="flex items-start gap-2.5 p-2.5 bg-slate-50 rounded-lg">
                      <span className="w-4 h-4 rounded-full bg-sky-100 text-sky-800 text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                        {idx + 1}
                      </span>
                      <p className="leading-relaxed">{step}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Alternative Accredited Laboratories */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <Building2 className="w-4 h-4 text-emerald-600" />
                    Accredited Alternative Laboratories (No Kickback Contracts)
                  </h4>
                  <span className="text-xs text-slate-500">Benchmark Tier</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {auditReport.alternativeLabs.map((lab) => (
                    <div key={lab.labName} className="p-3.5 bg-slate-50 border border-slate-200 rounded-lg space-y-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-900">{lab.labName}</span>
                      </div>
                      <div className="flex items-center gap-2 text-[11px] text-slate-500">
                        <span className="text-emerald-700 font-semibold">{lab.accreditation}</span>
                        <span aria-hidden="true">·</span>
                        <span>{lab.distance}</span>
                      </div>
                      <div className="flex items-center justify-between pt-1 border-t border-slate-200 font-mono">
                        <span className="text-slate-600">Fair Indicated Cost: ${lab.estimatedCost}</span>
                        <span className="font-bold text-emerald-700">Save ${lab.savings}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

            </div>
          )}

        </div>

      </div>

    </div>
  );
};
