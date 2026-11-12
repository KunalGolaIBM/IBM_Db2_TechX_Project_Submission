import React, { useState } from 'react';
import { Network, AlertOctagon, TrendingUp, Search, ShieldAlert, Award, FileSpreadsheet } from 'lucide-react';
import { DOCTORS, DIAGNOSTIC_LABS, LAB_COMMISSION_CONTRACTS } from '../data/db2MockDatabase';

export const KickbackMatrix: React.FC = () => {
  const [searchDoctor, setSearchDoctor] = useState<string>('');
  const [selectedSpecialty, setSelectedSpecialty] = useState<string>('all');
  const [minCommission, setMinCommission] = useState<number>(0);

  const filteredDoctors = DOCTORS.filter(doc => {
    const matchSearch = doc.name.toLowerCase().includes(searchDoctor.toLowerCase()) || doc.hospital.toLowerCase().includes(searchDoctor.toLowerCase());
    const matchSpec = selectedSpecialty === 'all' || doc.specialty.includes(selectedSpecialty);
    return matchSearch && matchSpec;
  });

  const filteredContracts = LAB_COMMISSION_CONTRACTS.filter(c => {
    const matchSearch = c.doctorName.toLowerCase().includes(searchDoctor.toLowerCase()) || c.labName.toLowerCase().includes(searchDoctor.toLowerCase());
    return matchSearch && c.commissionPct >= minCommission;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      
      {/* Financial Impact Summary Banner */}
      {(() => {
        const totalDoctors = DOCTORS.length;
        const highRiskDoctors = DOCTORS.filter(d => d.suspicionScore > 75).length;
        const totalContracts = LAB_COMMISSION_CONTRACTS.length;
        const avgCommission = Math.round(LAB_COMMISSION_CONTRACTS.reduce((s, c) => s + c.commissionPct, 0) / totalContracts * 10) / 10;
        const maxCommission = Math.max(...LAB_COMMISSION_CONTRACTS.map(c => c.commissionPct));
        const unaccreditedLabs = DIAGNOSTIC_LABS.filter(l => l.accreditation === 'Unaccredited').length;
        return (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {[
              { label: 'Doctors Monitored', value: totalDoctors, color: 'text-slate-900', bg: 'bg-white border-slate-200' },
              { label: 'High-Risk Physicians', value: highRiskDoctors, color: 'text-red-700', bg: 'bg-red-50 border-red-200' },
              { label: 'Active Kickback Ties', value: totalContracts, color: 'text-rose-700', bg: 'bg-rose-50 border-rose-200' },
              { label: 'Avg Commission Rate', value: `${avgCommission}%`, color: 'text-orange-700', bg: 'bg-orange-50 border-orange-200' },
              { label: 'Max Commission Found', value: `${maxCommission}%`, color: 'text-red-800', bg: 'bg-red-100 border-red-300' },
              { label: 'Unaccredited Labs', value: unaccreditedLabs, color: 'text-slate-700', bg: 'bg-slate-50 border-slate-200' },
            ].map(stat => (
              <div key={stat.label} className={`p-3.5 rounded-xl border ${stat.bg} text-center`}>
                <span className={`text-xl font-extrabold font-mono tabular-nums block ${stat.color}`}>{stat.value}</span>
                <span className="text-[10px] text-slate-500 mt-0.5 block leading-tight">{stat.label}</span>
              </div>
            ))}
          </div>
        );
      })()}

      {/* Header & Context */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 sm:p-8 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-rose-700 uppercase tracking-wider mb-1">
              <span>IBM DB2 Fraud & Kickback Detection System</span>
              <span aria-hidden="true">·</span>
              <span>Table: LAB_COMMISSION_CONTRACTS</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
              Diagnostic Lab Kickback & Referral Matrix
            </h1>
            <p className="mt-1 text-sm text-slate-600 max-w-3xl">
              Exposing hidden commission agreements where diagnostic laboratories funnel 25% to 45% of test fees back to referring doctors, driving unnecessary high-cost scans.
            </p>
          </div>

          <div className="p-3 bg-rose-50 border border-rose-100 rounded-lg text-xs flex items-center gap-3">
            <AlertOctagon className="w-5 h-5 text-rose-600 shrink-0" />
            <div>
              <span className="font-bold text-rose-900 block">Avg Flagged Referral Commission</span>
              <span className="font-mono text-base font-extrabold text-rose-700 tabular-nums">{Math.round(LAB_COMMISSION_CONTRACTS.reduce((s, c) => s + c.commissionPct, 0) / LAB_COMMISSION_CONTRACTS.length * 10) / 10}% per test</span>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div>
            <label className="block font-medium text-slate-700 mb-1">Search Doctor or Lab</label>
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="e.g. Dr. Sharma or MetroScan"
                value={searchDoctor}
                onChange={(e) => setSearchDoctor(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 border border-slate-200 rounded-lg text-slate-900 bg-slate-50/50 focus:outline-none focus:ring-1 focus:ring-sky-500"
              />
            </div>
          </div>

          <div>
            <label className="block font-medium text-slate-700 mb-1">Specialty Filter</label>
            <select
              value={selectedSpecialty}
              onChange={(e) => setSelectedSpecialty(e.target.value)}
              className="w-full px-3 py-1.5 border border-slate-200 rounded-lg text-slate-900 bg-slate-50/50 focus:outline-none focus:ring-1 focus:ring-sky-500"
            >
              <option value="all">All Specialties</option>
              <option value="Internal Medicine">Internal Medicine</option>
              <option value="Orthopedics">Orthopedics</option>
              <option value="Neurology">Neurology</option>
              <option value="Family Medicine">Family Medicine</option>
            </select>
          </div>

          <div>
            <label className="block font-medium text-slate-700 mb-1">
              Min Commission Rate: <span className="font-mono font-bold text-slate-900">{minCommission}%</span>
            </label>
            <input
              type="range"
              min="0"
              max="40"
              step="5"
              value={minCommission}
              onChange={(e) => setMinCommission(Number(e.target.value))}
              className="w-full accent-sky-600 mt-2"
            />
          </div>
        </div>
      </div>

      {/* Grid: Monitored Physicians & Active Kickback Ties */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        
        {/* Left: Active Contracts Registry (7 cols) */}
        <div className="lg:col-span-7 bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Network className="w-4 h-4 text-rose-600" />
              Active Lab Commission Agreements ({filteredContracts.length})
            </h2>
            <span className="text-xs text-slate-500 font-mono">DB2: LAB_COMMISSION_CONTRACTS</span>
          </div>

          <div className="divide-y divide-slate-100 border border-slate-200 rounded-lg overflow-hidden">
            {filteredContracts.map((contract) => (
              <div key={contract.contractId} className="p-4 hover:bg-slate-50/60 transition-colors space-y-2">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-xs">
                  <div>
                    <span className="font-bold text-slate-900 text-sm">{contract.doctorName}</span>
                    <span className="text-slate-400 mx-2">→</span>
                    <span className="font-medium text-slate-700">{contract.labName}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-extrabold text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded">
                      {contract.commissionPct}% Kickback
                    </span>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500">
                  <span>Category: <strong className="text-slate-700">{contract.testCategory}</strong></span>
                  <span aria-hidden="true">·</span>
                  <span>Modality: <strong className="text-slate-700">{contract.kickbackType}</strong></span>
                  <span aria-hidden="true">·</span>
                  <span className="font-mono">Audited: {contract.lastAuditDate}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="p-3.5 bg-slate-50 rounded-lg text-xs text-slate-600 space-y-1">
            <span className="font-bold text-slate-800 block">How Diagnostic Lab Kickbacks Work:</span>
            <p className="leading-relaxed">
              Commercial scan centers and pathology labs enter unrecorded agreements with doctors to refund 20% to 45% of the patient&apos;s invoice. This incentivizes clinicians to order MRI, CT, and genetic tests even when patient symptoms are benign.
            </p>
          </div>
        </div>

        {/* Right: Monitored Physicians Suspicion Scoring (5 cols) */}
        <div className="lg:col-span-5 bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-sky-600" />
              Physician Suspicion Scoring
            </h2>
            <span className="text-xs text-slate-500 font-mono">DB2: DOCTORS</span>
          </div>

          <div className="space-y-3">
            {filteredDoctors.map((doc) => {
              const isHigh = doc.suspicionScore > 75;
              const isLow = doc.suspicionScore < 20;

              return (
                <div key={doc.doctorId} className="p-3.5 border border-slate-200 rounded-lg space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-bold text-slate-900 block">{doc.name}</span>
                      <span className="text-[11px] text-slate-500">{doc.specialty}</span>
                    </div>
                    <div className="text-right">
                      <span className={`font-mono font-bold px-2 py-0.5 rounded ${
                        isHigh ? 'bg-red-50 text-red-700 border border-red-200' : isLow ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'
                      }`}>
                        Score: {doc.suspicionScore}/100
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-100 text-[11px] text-slate-600">
                    <div>
                      <span>Unnecessary Order Rate:</span>
                      <span className="font-mono font-bold text-slate-800 ml-1">{doc.unnecessaryPrescriptionRate}%</span>
                    </div>
                    <div>
                      <span>Prescriptions Audited:</span>
                      <span className="font-mono font-bold text-slate-800 ml-1">{doc.totalPrescriptionsAudited}</span>
                    </div>
                  </div>

                  <div className="text-[11px] text-slate-500 flex items-center justify-between pt-1">
                    <span>{doc.hospital}</span>
                    <span className="text-rose-600 font-semibold">{doc.activeContractsCount} Flagged Lab Contracts</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Diagnostic Labs Registry */}
          <div className="pt-2 border-t border-slate-100 space-y-2">
            <span className="text-xs font-bold text-slate-900 block">
              Monitored Diagnostic Centers (DB2: DIAGNOSTIC_LABS)
            </span>
            <div className="space-y-1.5 text-xs">
              {DIAGNOSTIC_LABS.map(lab => (
                <div key={lab.labId} className="p-2.5 bg-slate-50 rounded flex items-center justify-between">
                  <div>
                    <span className="font-medium text-slate-800 block">{lab.name}</span>
                    <span className="text-[11px] text-slate-500">{lab.accreditation} · {lab.city}</span>
                  </div>
                  <div className="text-right font-mono text-[11px]">
                    <span className="font-bold text-slate-700">+{lab.avgMarkupPct}% Markup</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>

      </div>

    </div>
  );
};
