import React, { useState, useEffect } from 'react';
import {
  FileText,
  Download,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Lock,
  Copy,
  Check,
  X,
  Sparkles,
  Database,
  Building,
  Package,
  Layers,
  FileCheck,
} from 'lucide-react';
import {
  fetchDossierPreview,
  downloadRecallDossier,
  type DossierPreview,
} from '../../services/api';

interface DossierExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  incidentId?: string;
  onDossierGenerated?: () => void;
}

export const DossierExportModal: React.FC<DossierExportModalProps> = ({
  isOpen,
  onClose,
  incidentId = 'INC-2026-001',
  onDossierGenerated,
}) => {
  const [preview, setPreview] = useState<DossierPreview | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [includeFssai, setIncludeFssai] = useState(true);
  const [operatorName, setOperatorName] = useState('Chief Safety Officer');
  const [downloadSuccess, setDownloadSuccess] = useState<{
    filename: string;
    sha256: string;
    reportId: string;
    sizeBytes: number;
  } | null>(null);
  const [copiedHash, setCopiedHash] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (isOpen) {
      setDownloadSuccess(null);
      setErrorMsg(null);
      setIsLoadingPreview(true);
      fetchDossierPreview(incidentId)
        .then((data) => {
          setPreview(data);
          setIsLoadingPreview(false);
        })
        .catch((err) => {
          console.error('Failed to load dossier preview:', err);
          setErrorMsg('Failed to fetch dossier metadata from IBM Db2.');
          setIsLoadingPreview(false);
        });
    }
  }, [isOpen, incidentId]);

  if (!isOpen) return null;

  const handleDownload = async () => {
    setIsGenerating(true);
    setErrorMsg(null);
    try {
      const result = await downloadRecallDossier(incidentId, includeFssai, operatorName);
      setDownloadSuccess(result);
      if (onDossierGenerated) {
        onDossierGenerated();
      }
    } catch (err: any) {
      console.error('Failed to generate dossier:', err);
      setErrorMsg(err.message || 'Failed to generate PDF dossier.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopyHash = () => {
    if (downloadSuccess?.sha256) {
      navigator.clipboard.writeText(downloadSuccess.sha256);
      setCopiedHash(true);
      setTimeout(() => setCopiedHash(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/85 backdrop-blur-md p-3 sm:p-4 animate-in fade-in duration-200">
      <div className="bg-[#0b1320] border border-[#23cad2]/30 rounded-2xl max-w-2xl w-full max-h-[92vh] flex flex-col shadow-[0_16px_50px_rgba(0,0,0,0.8),0_0_30px_rgba(35,202,210,0.15)] overflow-hidden">
        {/* Modal Header */}
        <div className="p-4 sm:p-5 bg-[#08121e] border-b border-white/10 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[#23cad2]/15 border border-[#23cad2]/40 flex items-center justify-center text-[#23cad2] shadow-[0_0_12px_rgba(35,202,210,0.3)]">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm sm:text-base font-bold text-white tracking-wide">
                  Generate Official Recall Dossier
                </h2>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#23cad2]/20 text-[#8ef5e6] border border-[#23cad2]/40">
                  A4 PDF • 6 PAGES
                </span>
              </div>
              <p className="text-[11px] font-mono text-white/50 mt-0.5">
                IBM Db2 Single Source of Truth • SHA-256 Tamper Evident
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body: Scrollable */}
        <div className="p-4 sm:p-6 overflow-y-auto space-y-4 text-xs">
          {errorMsg && (
            <div className="p-3 rounded-lg bg-red-500/15 border border-red-500/30 text-red-200 flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-xs">Generation Error</p>
                <p className="text-[11px] opacity-90 mt-0.5">{errorMsg}</p>
              </div>
            </div>
          )}

          {downloadSuccess && (
            <div className="p-4 rounded-xl bg-emerald-500/15 border border-emerald-500/40 text-emerald-200 space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-emerald-300 font-bold text-xs sm:text-sm">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>Dossier Successfully Generated & Downloaded</span>
                </div>
                <span className="text-[10px] font-mono bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-500/30 text-emerald-300">
                  {(downloadSuccess.sizeBytes / 1024).toFixed(1)} KB
                </span>
              </div>
              <div className="text-[11px] font-mono space-y-1 bg-[#05111d]/80 p-2.5 rounded-lg border border-emerald-500/20">
                <div className="flex justify-between items-center text-white/70">
                  <span>File:</span>
                  <span className="font-bold text-white">{downloadSuccess.filename}</span>
                </div>
                <div className="flex justify-between items-center text-white/70">
                  <span>Report ID:</span>
                  <span className="font-bold text-[#8ef5e6]">{downloadSuccess.reportId}</span>
                </div>
                <div className="flex items-center justify-between pt-1 border-t border-white/10">
                  <span className="text-white/60">SHA-256 Digest:</span>
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-[10px] text-emerald-300 truncate max-w-[220px] sm:max-w-[280px]">
                      {downloadSuccess.sha256}
                    </span>
                    <button
                      onClick={handleCopyHash}
                      title="Copy SHA-256"
                      className="p-1 hover:bg-white/10 rounded cursor-pointer text-white/70 hover:text-white"
                    >
                      {copiedHash ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>
              </div>
              <p className="text-[10px] text-emerald-300/80 font-mono">
                ✓ Permanent event recorded in <span className="font-bold text-white">LOTLINE_APP.AUDIT_LOG</span>.
              </p>
            </div>
          )}

          {/* Dossier Structure Cards */}
          <div className="space-y-2">
            <span className="text-[10px] font-mono uppercase tracking-wider text-white/50 block">
              Dossier Structure (5 Pages A4 Enterprise Format)
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
              <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/10 space-y-1">
                <div className="flex items-center gap-2 font-semibold text-white">
                  <span className="w-5 h-5 rounded-full bg-[#23cad2]/20 text-[#8ef5e6] flex items-center justify-center font-mono text-[10px]">1</span>
                  <span>Executive Incident Brief</span>
                </div>
                <p className="text-white/60 text-[10px] pl-7">
                  Incident details, pathogen metadata, supplier profile, and 4-metric executive KPI dashboard.
                </p>
              </div>

              <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/10 space-y-1">
                <div className="flex items-center gap-2 font-semibold text-white">
                  <span className="w-5 h-5 rounded-full bg-[#23cad2]/20 text-[#8ef5e6] flex items-center justify-center font-mono text-[10px]">2</span>
                  <span>Contamination Traceability</span>
                </div>
                <p className="text-white/60 text-[10px] pl-7">
                  Source lot genealogy, 2-tier tree traversal, 6 downstream batches (WIP & FIN), and facility mappings.
                </p>
              </div>

              <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/10 space-y-1">
                <div className="flex items-center gap-2 font-semibold text-white">
                  <span className="w-5 h-5 rounded-full bg-[#23cad2]/20 text-[#8ef5e6] flex items-center justify-center font-mono text-[10px]">3</span>
                  <span>Exposure Reconciliation</span>
                </div>
                <p className="text-white/60 text-[10px] pl-7">
                  Deterministic breakdown (2,400 units total), retail distribution table, and strict KG vs UNIT separation.
                </p>
              </div>

              <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/10 space-y-1">
                <div className="flex items-center gap-2 font-semibold text-white">
                  <span className="w-5 h-5 rounded-full bg-[#23cad2]/20 text-[#8ef5e6] flex items-center justify-center font-mono text-[10px]">4</span>
                  <span>Response Protocols & Roadmap</span>
                </div>
                <p className="text-white/60 text-[10px] pl-7">
                  Mitigation actions, current approval states (ACT-001..004), operator notes, and execution timeline.
                </p>
              </div>

              <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/10 sm:col-span-2 space-y-1">
                <div className="flex items-center gap-2 font-semibold text-white">
                  <span className="w-5 h-5 rounded-full bg-[#23cad2]/20 text-[#8ef5e6] flex items-center justify-center font-mono text-[10px]">5</span>
                  <span>Immutable Audit Trail & Regulatory Profile</span>
                </div>
                <p className="text-white/60 text-[10px] pl-7">
                  Complete chronological audit event log, Db2 catalog limitations, and FSSAI 2017 Schedule-I draft preparation profile.
                </p>
              </div>
            </div>
          </div>

          {/* Database Verification Facts */}
          <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/10 space-y-2">
            <div className="flex items-center justify-between text-[10px] font-mono text-white/50">
              <span className="uppercase tracking-wider">VERIFIED DB2 EVIDENCE CONTEXT</span>
              <span className="text-[#8ef5e6]">SCHEMA: LOTLINE_APP</span>
            </div>
            {isLoadingPreview ? (
              <div className="py-4 text-center font-mono text-white/40">Loading verified facts from Db2...</div>
            ) : preview ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 font-mono text-[11px]">
                <div className="p-2 rounded bg-black/40 border border-white/5">
                  <span className="text-[9px] text-white/40 block">CONTAMINANT</span>
                  <span className="font-bold text-red-300">{preview.contaminant}</span>
                </div>
                <div className="p-2 rounded bg-black/40 border border-white/5">
                  <span className="text-[9px] text-white/40 block">RAW LOT</span>
                  <span className="font-bold text-white">{preview.source_lot_id} ({preview.raw_quantity} {preview.raw_unit})</span>
                </div>
                <div className="p-2 rounded bg-black/40 border border-white/5">
                  <span className="text-[9px] text-white/40 block">FINISHED EXPOSURE</span>
                  <span className="font-bold text-amber-300">{preview.finished_goods_units} UNITS</span>
                </div>
                <div className="p-2 rounded bg-black/40 border border-white/5">
                  <span className="text-[9px] text-white/40 block">RECALL ACTIONS</span>
                  <span className="font-bold text-white">{preview.actions_approved}/{preview.actions_total} Approved</span>
                </div>
              </div>
            ) : null}
          </div>

          {/* FSSAI Regulatory Options & Notice */}
          <div className="p-3.5 rounded-xl bg-[#091829] border border-[#23cad2]/20 space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-2.5">
                <input
                  type="checkbox"
                  id="include-fssai"
                  checked={includeFssai}
                  onChange={(e) => setIncludeFssai(e.target.checked)}
                  className="mt-1 w-4 h-4 rounded border-white/30 text-[#23cad2] focus:ring-[#23cad2] cursor-pointer"
                />
                <label htmlFor="include-fssai" className="cursor-pointer">
                  <div className="font-semibold text-white text-xs flex items-center gap-1.5">
                    <span>Include FSSAI Schedule-I Regulatory Profile</span>
                    <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-[#23cad2]/20 text-[#8ef5e6] font-bold">
                      2017 REGULATIONS
                    </span>
                  </div>
                  <p className="text-[11px] text-white/70 mt-0.5 leading-relaxed">
                    Appends structured Food Recall Notice profile compliant with FSSAI Food Recall Procedure Regulations, 2017.
                  </p>
                </label>
              </div>
            </div>

            {includeFssai && (
              <div className="p-2.5 rounded-lg bg-amber-500/[0.08] border border-amber-500/20 text-amber-200/90 text-[10.5px] space-y-1">
                <div className="flex items-center gap-1.5 font-bold text-amber-300">
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                  <span>Regulatory Review Flags:</span>
                </div>
                <p className="leading-relaxed">
                  Per FSSAI guidelines, two required fields (<strong>FSSAI License No.</strong> and <strong>Recall Coordinator Telephone</strong>) are not maintained in standard LOTLINE ERP tables and are marked for human operator input prior to official FoSCoS portal filing.
                </p>
              </div>
            )}

            <div className="pt-2 border-t border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px]">
              <span className="text-white/60 font-mono">Signatory Operator:</span>
              <input
                type="text"
                value={operatorName}
                onChange={(e) => setOperatorName(e.target.value)}
                placeholder="Operator Title / Name"
                className="px-2.5 py-1 rounded bg-black/50 border border-white/20 text-white font-mono text-xs focus:border-[#23cad2] focus:outline-none w-full sm:w-64"
              />
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 sm:p-5 bg-[#08121e] border-t border-white/10 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 shrink-0">
          <div className="flex items-center gap-2 text-[11px] font-mono text-white/50">
            <Lock className="w-3.5 h-3.5 text-[#23cad2]" />
            <span>Cryptographic SHA-256 Dual-Pass Header</span>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={onClose}
              disabled={isGenerating}
              className="min-h-[42px] px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-white/80 hover:text-white text-xs font-semibold cursor-pointer transition-all disabled:opacity-40 flex-1 sm:flex-none flex items-center justify-center"
            >
              Cancel
            </button>
            <button
              onClick={handleDownload}
              disabled={isGenerating}
              className="min-h-[42px] px-5 py-2 rounded-xl bg-[#23cad2] hover:bg-[#34ded6] text-[#030c1a] text-xs font-bold uppercase tracking-wider cursor-pointer transition-all shadow-[0_4px_20px_rgba(35,202,210,0.35)] active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2 flex-1 sm:flex-none"
            >
              <Download className={`w-4 h-4 ${isGenerating ? 'animate-bounce' : ''}`} />
              <span>{isGenerating ? 'GENERATING DOSSIER...' : 'DOWNLOAD DOSSIER (PDF)'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
