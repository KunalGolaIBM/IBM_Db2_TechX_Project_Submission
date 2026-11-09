import React, { useState, useEffect, useRef } from 'react';
import {
  UploadCloud,
  FileText,
  CheckCircle,
  AlertTriangle,
  XCircle,
  ArrowRight,
  RefreshCw,
  Sliders,
  Database,
  ShieldCheck,
  Check,
  ExternalLink,
  Layers,
  Sparkles
} from 'lucide-react';
import {
  apiClient,
  ImportPreviewResponse,
  ImportCommitResponse,
  ImportJobItem,
  ApiError
} from '../../api/client';
import { useAuth } from '../../context/AuthContext';

const SAMPLE_BANK_CSV = `Date,Description,Amount,Type,Category
2026-11-01,Fresh Supermarket,1450.00,DEBIT,Groceries & Supermarket
2026-11-02,Blue Tokai Coffee,240.00,DEBIT,Dining & Takeout
2026-11-03,Client Consulting Fee,35000.00,CREDIT,Consulting & Freelance
2026-11-04,Uber India Ride,360.00,DEBIT,Commute & Travel
2026-11-05,Apollo Pharmacy,480.00,DEBIT,Healthcare & Pharmacy`;

const SAMPLE_DEBIT_CREDIT_CSV = `Transaction Date,Merchant Narration,Debit,Credit,Transaction Category
01/11/2026,Croma Electronics,4500.00,,Electronics & Shopping
02/11/2026,Monthly Retainer Payout,,25000.00,Consulting & Freelance
03/11/2026,Tata Power Electricity,1850.00,,Utilities & Internet
04/11/2026,Swiggy Gourmet,820.00,,Dining & Takeout`;

interface ImportTransactionsViewProps {
  onNavigateToTransactions?: () => void;
  onNavigateToDashboard?: () => void;
}

type Step = 'SELECT_FILE' | 'MAP_COLUMNS' | 'REVIEW' | 'RESULTS';

export const ImportTransactionsView: React.FC<ImportTransactionsViewProps> = ({
  onNavigateToTransactions,
  onNavigateToDashboard,
}) => {
  const { csrfToken } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Workflow State
  const [currentStep, setCurrentStep] = useState<Step>('SELECT_FILE');
  const [filename, setFilename] = useState<string>('');
  const [csvContent, setCsvContent] = useState<string>('');
  const [fileSize, setFileSize] = useState<number>(0);
  const [skipDuplicates, setSkipDuplicates] = useState<boolean>(true);

  // Custom Mappings
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});

  // API State
  const [loading, setLoading] = useState<boolean>(false);
  const [committing, setCommitting] = useState<boolean>(false);
  const [retryingIndex, setRetryingIndex] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Response Payloads
  const [previewData, setPreviewData] = useState<ImportPreviewResponse | null>(null);
  const [commitResult, setCommitResult] = useState<ImportCommitResponse | null>(null);
  const [history, setHistory] = useState<ImportJobItem[]>([]);
  const [showHistory, setShowHistory] = useState<boolean>(false);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      const res = await apiClient.imports.getHistory();
      setHistory(res);
    } catch {
      // Non-blocking history load
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    processSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    processSelectedFile(file);
  };

  const processSelectedFile = (file: File) => {
    setErrorMessage(null);
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setErrorMessage('Only standard CSV files (.csv) are supported.');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setErrorMessage('File size exceeds the 5 MB maximum limit.');
      return;
    }

    setFilename(file.name);
    setFileSize(file.size);

    const reader = new FileReader();
    reader.onload = async (event) => {
      const text = event.target?.result as string;
      setCsvContent(text);
      await runPreview(file.name, text);
    };
    reader.onerror = () => {
      setErrorMessage('Failed to read file contents.');
    };
    reader.readAsText(file);
  };

  const loadSample = async (type: 'bank' | 'debit_credit') => {
    const text = type === 'bank' ? SAMPLE_BANK_CSV : SAMPLE_DEBIT_CREDIT_CSV;
    const name = type === 'bank' ? 'synthetic_bank_statement.csv' : 'synthetic_debit_credit.csv';
    setFilename(name);
    setFileSize(text.length);
    setCsvContent(text);
    await runPreview(name, text);
  };

  const runPreview = async (fname: string, content: string, customMap?: Record<string, string>) => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const res = await apiClient.imports.preview(fname, content, customMap, csrfToken);
      setPreviewData(res);
      // Pre-populate mapping fields from detected mapping
      const initialMap: Record<string, string> = {};
      Object.entries(res.detected_mapping).forEach(([k, v]) => {
        if (v) initialMap[k] = v;
      });
      if (customMap) {
        Object.assign(initialMap, customMap);
      }
      setColumnMapping(initialMap);
      setCurrentStep('MAP_COLUMNS');
    } catch (err: any) {
      if (err instanceof ApiError) {
        setErrorMessage(err.message || 'Validation error while parsing CSV.');
      } else {
        setErrorMessage(err.message || 'Failed to preview CSV import.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleMappingChange = (field: string, csvCol: string) => {
    const updated = { ...columnMapping, [field]: csvCol };
    if (!csvCol) {
      delete updated[field];
    }
    setColumnMapping(updated);
  };

  const reapplyMapping = async () => {
    if (!filename || !csvContent) return;
    await runPreview(filename, csvContent, columnMapping);
  };

  const handleCommit = async () => {
    if (!previewData || !csvContent) return;
    setCommitting(true);
    setErrorMessage(null);
    try {
      const res = await apiClient.imports.commit(
        previewData.import_id,
        filename,
        csvContent,
        columnMapping,
        skipDuplicates,
        undefined,
        csrfToken
      );
      setCommitResult(res);
      setCurrentStep('RESULTS');
      loadHistory();
    } catch (err: any) {
      if (err instanceof ApiError) {
        setErrorMessage(err.message || 'Failed to commit transaction import to IBM Db2.');
      } else {
        setErrorMessage(err.message || 'Error occurred during transaction import.');
      }
    } finally {
      setCommitting(false);
    }
  };

  const handleRetryIndexing = async () => {
    if (!commitResult) return;
    setRetryingIndex(true);
    try {
      const idxRes = await apiClient.imports.retryIndexing(commitResult.import_id, csrfToken);
      setCommitResult({
        ...commitResult,
        indexing_status: idxRes,
      });
    } catch (err: any) {
      setErrorMessage(err.message || 'Retry vector indexing failed.');
    } finally {
      setRetryingIndex(false);
    }
  };

  const resetImport = () => {
    setCurrentStep('SELECT_FILE');
    setFilename('');
    setCsvContent('');
    setFileSize(0);
    setPreviewData(null);
    setCommitResult(null);
    setErrorMessage(null);
    setColumnMapping({});
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-forest-200 dark:border-forest-800 bg-forest-50 dark:bg-forest-900/70 px-3 py-1 text-xs font-semibold text-forest-800 dark:text-sage-300">
              <ShieldCheck className="h-3.5 w-3.5 text-sage-600 dark:text-gold-400" />
              <span>IBM Db2 Secure Transaction Ingestion · Stage 5</span>
            </div>
            <h1 className="mt-2 text-2xl font-bold tracking-tight text-forest-950 dark:text-cream-100">
              Import Transactions
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-stone-500 dark:text-sage-400">
              Upload bank statements, map columns, preview parsed records, eliminate duplicates, and securely ingest transactions directly into IBM Db2 with automated vector indexing.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="inline-flex items-center gap-2 rounded-xl border border-stone-200 dark:border-forest-800 bg-stone-50/70 dark:bg-[#163013]/60 px-4 py-2 text-xs font-semibold text-stone-700 dark:text-sage-300 hover:bg-stone-100 dark:hover:bg-forest-900 transition"
            >
              <Database className="h-3.5 w-3.5 text-sage-500" />
              <span>{showHistory ? 'Hide History' : `History (${history.length})`}</span>
            </button>
            {currentStep !== 'SELECT_FILE' && (
              <button
                onClick={resetImport}
                className="inline-flex items-center gap-2 rounded-xl border border-stone-200 dark:border-forest-800 bg-white dark:bg-[#10240d] px-4 py-2 text-xs font-semibold text-stone-700 dark:text-sage-300 hover:bg-stone-50 dark:hover:bg-forest-900 transition"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span>New Import</span>
              </button>
            )}
          </div>
        </div>

        {/* Step Indicator */}
        <div className="mt-6 grid grid-cols-4 gap-2 pt-6 border-t border-stone-100 dark:border-forest-900/60">
          {[
            { id: 'SELECT_FILE', label: '1. Select File' },
            { id: 'MAP_COLUMNS', label: '2. Map Columns' },
            { id: 'REVIEW', label: '3. Review & Duplicates' },
            { id: 'RESULTS', label: '4. Committed to Db2' },
          ].map((s, idx) => {
            const stepOrder: Step[] = ['SELECT_FILE', 'MAP_COLUMNS', 'REVIEW', 'RESULTS'];
            const currentIdx = stepOrder.indexOf(currentStep);
            const isCompleted = idx < currentIdx;
            const isCurrent = s.id === currentStep;

            return (
              <div key={s.id} className="flex items-center gap-2">
                <div
                  className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition border ${
                    isCompleted
                      ? 'bg-forest-700 text-white border-forest-600'
                      : isCurrent
                      ? 'bg-[#15370D] text-[#FFF2B4] border-forest-800 ring-4 ring-[#E5CD82]/40'
                      : 'bg-stone-100 dark:bg-[#163013] text-stone-500 dark:text-sage-400 border-stone-200 dark:border-forest-800'
                  }`}
                >
                  {isCompleted ? <Check className="h-4 w-4" /> : idx + 1}
                </div>
                <span
                  className={`text-xs font-medium truncate ${
                    isCurrent
                      ? 'text-forest-950 dark:text-cream-100 font-semibold'
                      : isCompleted
                      ? 'text-forest-800 dark:text-sage-300'
                      : 'text-stone-400 dark:text-sage-500'
                  }`}
                >
                  {s.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Error Alert */}
      {errorMessage && (
        <div className="rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/80 dark:bg-rose-950/30 p-4 text-rose-800 dark:text-rose-300 flex items-start gap-3 text-xs">
          <XCircle className="h-5 w-5 shrink-0 text-rose-600 mt-0.5" />
          <div>
            <span className="font-semibold">Import Issue: </span>
            {errorMessage}
          </div>
        </div>
      )}

      {/* Import History Modal/Drawer */}
      {showHistory && (
        <div className="rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-semibold text-forest-950 dark:text-cream-100 flex items-center gap-2">
              <Database className="h-4 w-4 text-sage-600 dark:text-gold-400" />
              <span>Db2 Import History (<code className="font-mono text-xs">FINSIGHT.IMPORT_JOBS</code>)</span>
            </h3>
            <span className="text-xs text-stone-500 dark:text-sage-400">Tenant-isolated import records</span>
          </div>
          {history.length === 0 ? (
            <p className="text-xs text-stone-500 py-4 text-center">No previous CSV imports found for your account.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-stone-100 dark:border-forest-900/60 text-stone-500 dark:text-sage-400">
                    <th className="pb-2 font-medium">Job ID</th>
                    <th className="pb-2 font-medium">Filename</th>
                    <th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium">Total Rows</th>
                    <th className="pb-2 font-medium">Imported</th>
                    <th className="pb-2 font-medium">Duplicates</th>
                    <th className="pb-2 font-medium">Created At</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 dark:divide-forest-900/50">
                  {history.map((h) => (
                    <tr key={h.import_id} className="hover:bg-stone-50/50 dark:hover:bg-forest-900/30">
                      <td className="py-2.5 font-mono text-stone-600 dark:text-sage-300">{h.import_id}</td>
                      <td className="py-2.5 font-medium text-forest-950 dark:text-cream-100">{h.filename}</td>
                      <td className="py-2.5">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                            h.status === 'COMPLETED'
                              ? 'bg-sage-100 text-sage-800 border-sage-300 dark:bg-forest-900/80 dark:text-sage-300 dark:border-forest-700'
                              : h.status === 'FAILED'
                              ? 'bg-rose-50 text-rose-700 border-rose-300 dark:bg-rose-950/60 dark:text-rose-400 dark:border-rose-800'
                              : 'bg-cream-100 text-[#15370D] border-gold-300 dark:bg-[#163013] dark:text-gold-300 dark:border-gold-600'
                          }`}
                        >
                          {h.status}
                        </span>
                      </td>
                      <td className="py-2.5 text-stone-600 dark:text-sage-300">{h.total_rows}</td>
                      <td className="py-2.5 text-forest-700 dark:text-gold-400 font-semibold font-mono">{h.successful_rows}</td>
                      <td className="py-2.5 text-stone-500 font-mono">{h.duplicate_rows}</td>
                      <td className="py-2.5 text-stone-400 font-mono text-[11px]">{h.created_at.slice(0, 19)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* STEP 1: SELECT FILE */}
      {currentStep === 'SELECT_FILE' && (
        <div className="space-y-6">
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-sage-300 dark:border-forest-800 bg-stone-50/60 dark:bg-[#10240d]/60 p-12 text-center transition hover:border-[#15370D] dark:hover:border-gold-400"
          >
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-cream-100 dark:bg-forest-900/80 text-[#15370D] dark:text-[#E5CD82] mb-4 shadow-xs border border-gold-200 dark:border-forest-700">
              <UploadCloud className="h-8 w-8" />
            </div>
            <h3 className="text-base sm:text-lg font-semibold text-forest-950 dark:text-cream-100">
              Drag & Drop your statement CSV file here
            </h3>
            <p className="mt-1 text-xs sm:text-sm text-stone-500 dark:text-sage-400 max-w-md">
              Supports standard comma-separated transaction files with quoted fields up to 5 MB (max 2,000 rows).
            </p>

            <input
              type="file"
              ref={fileInputRef}
              accept=".csv"
              onChange={handleFileSelect}
              className="hidden"
            />

            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={loading}
              className="mt-6 inline-flex items-center gap-2 rounded-xl bg-[#15370D] hover:bg-[#1e4a14] text-[#FFF2B4] px-5 py-2.5 text-xs sm:text-sm font-semibold shadow-xs transition disabled:opacity-50 border border-forest-800"
            >
              {loading ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin text-[#E5CD82]" />
                  <span>Parsing CSV...</span>
                </>
              ) : (
                <>
                  <FileText className="h-4 w-4 text-[#E5CD82]" />
                  <span>Browse CSV File</span>
                </>
              )}
            </button>
          </div>

          {/* Quick-test Synthetic Datasets */}
          <div className="rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] p-6 shadow-sm">
            <h4 className="text-sm font-semibold text-forest-950 dark:text-cream-100 flex items-center gap-2 mb-3">
              <Sparkles className="h-4 w-4 text-sage-600 dark:text-gold-400" />
              <span>Or test with verified synthetic CSV templates</span>
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <button
                onClick={() => loadSample('bank')}
                disabled={loading}
                className="flex flex-col text-left p-4 rounded-xl border border-stone-200 dark:border-forest-800 hover:border-gold-400 dark:hover:border-gold-500 bg-stone-50/50 dark:bg-[#163013]/60 transition group"
              >
                <div className="flex items-center justify-between w-full mb-1">
                  <span className="font-semibold text-xs sm:text-sm text-forest-950 dark:text-cream-100 group-hover:text-forest-800 dark:group-hover:text-gold-300 transition">
                    Standard Statement CSV
                  </span>
                  <span className="text-[10px] font-mono text-sage-700 dark:text-sage-300 border border-sage-300/60 dark:border-forest-700 bg-sage-50 dark:bg-forest-900/70 px-2 py-0.5 rounded">
                    5 Rows · Inflow & Outflow
                  </span>
                </div>
                <p className="text-xs text-stone-500 dark:text-sage-400">
                  Headers: `Date`, `Description`, `Amount`, `Type`, `Category`. Includes groceries, coffee, freelance income.
                </p>
              </button>

              <button
                onClick={() => loadSample('debit_credit')}
                disabled={loading}
                className="flex flex-col text-left p-4 rounded-xl border border-stone-200 dark:border-forest-800 hover:border-gold-400 dark:hover:border-gold-500 bg-stone-50/50 dark:bg-[#163013]/60 transition group"
              >
                <div className="flex items-center justify-between w-full mb-1">
                  <span className="font-semibold text-xs sm:text-sm text-forest-950 dark:text-cream-100 group-hover:text-forest-800 dark:group-hover:text-gold-300 transition">
                    Separate Debit & Credit Columns
                  </span>
                  <span className="text-[10px] font-mono text-sage-700 dark:text-sage-300 border border-sage-300/60 dark:border-forest-700 bg-sage-50 dark:bg-forest-900/70 px-2 py-0.5 rounded">
                    4 Rows · Split Columns
                  </span>
                </div>
                <p className="text-xs text-stone-500 dark:text-sage-400">
                  Headers: `Transaction Date`, `Merchant Narration`, `Debit`, `Credit`. Verifies dual-column financial parsing.
                </p>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* STEP 2: MAP COLUMNS */}
      {currentStep === 'MAP_COLUMNS' && previewData && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] p-6 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-stone-100 dark:border-forest-900/60">
              <div>
                <h3 className="text-base font-semibold text-forest-950 dark:text-cream-100 flex items-center gap-2">
                  <Sliders className="h-4 w-4 text-sage-600 dark:text-gold-400" />
                  <span>Column Mapping & Header Alignment</span>
                </h3>
                <p className="text-xs text-stone-500 dark:text-sage-400 mt-0.5">
                  File: <span className="font-mono font-medium text-forest-950 dark:text-cream-100">{filename}</span> ({fileSize} bytes) · Detected {previewData.headers.length} headers
                </p>
              </div>
              <button
                onClick={reapplyMapping}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-xl border border-stone-200 dark:border-forest-800 bg-stone-50 dark:bg-[#163013] px-3 py-1.5 text-xs font-semibold text-stone-700 dark:text-sage-300 hover:bg-stone-100 dark:hover:bg-forest-900 transition"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
                <span>Re-Analyze Mapping</span>
              </button>
            </div>

            {/* Mappings Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 mt-4">
              <div>
                <label className="block text-xs font-medium text-stone-700 dark:text-sage-300 mb-1">
                  Transaction Date <span className="text-rose-500">*</span>
                </label>
                <select
                  value={columnMapping.date || ''}
                  onChange={(e) => handleMappingChange('date', e.target.value)}
                  className="w-full text-xs rounded-xl border border-stone-200 dark:border-forest-800 bg-white dark:bg-[#10240d] px-3 py-2 text-forest-950 dark:text-cream-100 focus:outline-hidden focus:ring-2 focus:ring-[#15370D] dark:focus:ring-[#E5CD82]"
                >
                  <option value="">-- Select Date Column --</option>
                  {previewData.headers.map((h) => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-stone-700 dark:text-sage-300 mb-1">
                  Merchant / Narration <span className="text-rose-500">*</span>
                </label>
                <select
                  value={columnMapping.merchant || ''}
                  onChange={(e) => handleMappingChange('merchant', e.target.value)}
                  className="w-full text-xs rounded-xl border border-stone-200 dark:border-forest-800 bg-white dark:bg-[#10240d] px-3 py-2 text-forest-950 dark:text-cream-100 focus:outline-hidden focus:ring-2 focus:ring-[#15370D] dark:focus:ring-[#E5CD82]"
                >
                  <option value="">-- Select Merchant Column --</option>
                  {previewData.headers.map((h) => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-stone-700 dark:text-sage-300 mb-1">
                  Net Amount (Single column)
                </label>
                <select
                  value={columnMapping.amount || ''}
                  onChange={(e) => handleMappingChange('amount', e.target.value)}
                  className="w-full text-xs rounded-xl border border-stone-200 dark:border-forest-800 bg-white dark:bg-[#10240d] px-3 py-2 text-forest-950 dark:text-cream-100 focus:outline-hidden focus:ring-2 focus:ring-[#15370D] dark:focus:ring-[#E5CD82]"
                >
                  <option value="">-- None / Use Debit-Credit --</option>
                  {previewData.headers.map((h) => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-stone-700 dark:text-sage-300 mb-1">
                  Debit Column (Outflow)
                </label>
                <select
                  value={columnMapping.debit_amount || ''}
                  onChange={(e) => handleMappingChange('debit_amount', e.target.value)}
                  className="w-full text-xs rounded-xl border border-stone-200 dark:border-forest-800 bg-white dark:bg-[#10240d] px-3 py-2 text-forest-950 dark:text-cream-100 focus:outline-hidden focus:ring-2 focus:ring-[#15370D] dark:focus:ring-[#E5CD82]"
                >
                  <option value="">-- None --</option>
                  {previewData.headers.map((h) => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-stone-700 dark:text-sage-300 mb-1">
                  Credit Column (Inflow)
                </label>
                <select
                  value={columnMapping.credit_amount || ''}
                  onChange={(e) => handleMappingChange('credit_amount', e.target.value)}
                  className="w-full text-xs rounded-xl border border-stone-200 dark:border-forest-800 bg-white dark:bg-[#10240d] px-3 py-2 text-forest-950 dark:text-cream-100 focus:outline-hidden focus:ring-2 focus:ring-[#15370D] dark:focus:ring-[#E5CD82]"
                >
                  <option value="">-- None --</option>
                  {previewData.headers.map((h) => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-stone-700 dark:text-sage-300 mb-1">
                  Category (Optional)
                </label>
                <select
                  value={columnMapping.category || ''}
                  onChange={(e) => handleMappingChange('category', e.target.value)}
                  className="w-full text-xs rounded-xl border border-stone-200 dark:border-forest-800 bg-white dark:bg-[#10240d] px-3 py-2 text-forest-950 dark:text-cream-100 focus:outline-hidden focus:ring-2 focus:ring-[#15370D] dark:focus:ring-[#E5CD82]"
                >
                  <option value="">-- Uncategorized (Default) --</option>
                  {previewData.headers.map((h) => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setCurrentStep('SELECT_FILE')}
                className="px-4 py-2 rounded-xl border border-stone-200 dark:border-forest-800 text-xs font-semibold text-stone-700 dark:text-sage-300 hover:bg-stone-50 dark:hover:bg-forest-900"
              >
                Back
              </button>
              <button
                onClick={() => setCurrentStep('REVIEW')}
                className="inline-flex items-center gap-2 px-5 py-2 rounded-xl bg-[#15370D] hover:bg-[#1e4a14] text-[#FFF2B4] text-xs font-semibold shadow-xs transition border border-forest-800"
              >
                <span>Continue to Review</span>
                <ArrowRight className="h-3.5 w-3.5 text-[#E5CD82]" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* STEP 3: REVIEW & DUPLICATE IDENTIFICATION */}
      {currentStep === 'REVIEW' && previewData && (
        <div className="space-y-6">
          {/* Summary KPIs */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] p-4 shadow-sm">
              <span className="text-xs text-stone-500 dark:text-sage-400">Total Rows Detected</span>
              <div className="mt-1 text-2xl font-bold font-mono text-forest-950 dark:text-cream-100">
                {previewData.summary.total_rows}
              </div>
              <span className="text-[10px] text-stone-400 dark:text-sage-500">{previewData.headers.length} columns aligned</span>
            </div>

            <div className="rounded-2xl border border-forest-200 dark:border-forest-800 bg-forest-50/50 dark:bg-forest-950/40 p-4 shadow-sm">
              <span className="text-xs text-forest-800 dark:text-sage-300">Valid Transactions</span>
              <div className="mt-1 text-2xl font-bold font-mono text-forest-800 dark:text-sage-300">
                {previewData.summary.valid_rows}
              </div>
              <span className="text-[10px] text-forest-700/60 dark:text-sage-400">Passed strict date & amount checks</span>
            </div>

            <div className="rounded-2xl border border-gold-300 dark:border-forest-700 bg-cream-50/70 dark:bg-[#183013]/60 p-4 shadow-sm">
              <span className="text-xs text-[#15370D] dark:text-[#E5CD82]">Duplicate Candidates</span>
              <div className="mt-1 text-2xl font-bold font-mono text-[#15370D] dark:text-[#FFF2B4]">
                {previewData.summary.duplicate_rows}
              </div>
              <span className="text-[10px] text-forest-800/60 dark:text-gold-400/60">Exact / Intra-batch matches</span>
            </div>

            <div className="rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] p-4 shadow-sm">
              <span className="text-xs text-stone-500 dark:text-sage-400">Net Import Value</span>
              <div className="mt-1 text-2xl font-bold font-mono text-forest-950 dark:text-cream-100">
                ₹{previewData.summary.net_value.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <span className="text-[10px] text-stone-400 dark:text-sage-500">
                +{previewData.summary.total_credits.toLocaleString()} / -{previewData.summary.total_debits.toLocaleString()}
              </span>
            </div>
          </div>

          {/* Duplicate Protection Option */}
          <div className="rounded-2xl border border-gold-300/80 dark:border-forest-800 bg-cream-50/60 dark:bg-[#163013]/60 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-gold-400 shrink-0 mt-0.5" />
              <div>
                <h4 className="text-sm font-semibold text-forest-950 dark:text-cream-100">
                  Duplicate Identification & Deduplication Protection
                </h4>
                <p className="text-xs text-stone-600 dark:text-sage-400 mt-0.5">
                  {previewData.duplicate_candidates.length > 0
                    ? `Found ${previewData.duplicate_candidates.length} potential duplicate records matching existing Db2 transactions or repeating within this batch.`
                    : 'Zero duplicate transactions identified against your existing IBM Db2 ledger.'}
                </p>
              </div>
            </div>
            {previewData.duplicate_candidates.length > 0 && (
              <label className="flex items-center gap-2 cursor-pointer bg-white dark:bg-[#10240d] px-4 py-2 rounded-xl border border-stone-200 dark:border-forest-800">
                <input
                  type="checkbox"
                  checked={skipDuplicates}
                  onChange={(e) => setSkipDuplicates(e.target.checked)}
                  className="rounded text-[#15370D] focus:ring-[#15370D]"
                />
                <span className="text-xs font-semibold text-forest-950 dark:text-cream-100">
                  Skip Duplicates ({previewData.duplicate_candidates.length})
                </span>
              </label>
            )}
          </div>

          {/* Validation Errors List if any */}
          {previewData.validation_errors.length > 0 && (
            <div className="rounded-2xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/80 dark:bg-rose-950/30 p-4">
              <h4 className="text-sm font-semibold text-rose-700 dark:text-rose-400 flex items-center gap-2 mb-2">
                <XCircle className="h-4 w-4" />
                <span>Validation Errors ({previewData.validation_errors.length} rows rejected)</span>
              </h4>
              <ul className="divide-y divide-rose-200 dark:divide-rose-900/40 text-xs">
                {previewData.validation_errors.map((err, i) => (
                  <li key={i} className="py-2 flex items-start justify-between gap-2">
                    <span className="font-mono text-stone-600 dark:text-sage-400">Row {err.row_number}:</span>
                    <span className="text-rose-800 dark:text-rose-300 flex-1">{err.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Parsed Transactions Preview Table */}
          <div className="rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] p-6 shadow-sm">
            <h4 className="text-sm font-semibold text-forest-950 dark:text-cream-100 mb-3 flex items-center justify-between">
              <span>Parsed Transactions Preview ({previewData.preview_rows.length} rows)</span>
              <span className="text-xs text-stone-400 dark:text-sage-500">Default Status: POSTED · Currency: INR</span>
            </h4>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-stone-100 dark:border-forest-900/60 text-stone-500 dark:text-sage-400">
                    <th className="pb-2 font-medium">#</th>
                    <th className="pb-2 font-medium">Date</th>
                    <th className="pb-2 font-medium">Merchant / Narration</th>
                    <th className="pb-2 font-medium">Category</th>
                    <th className="pb-2 font-medium">Type</th>
                    <th className="pb-2 font-medium text-right">Amount</th>
                    <th className="pb-2 font-medium text-right">Validation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 dark:divide-forest-900/50">
                  {previewData.preview_rows.map((row) => (
                    <tr
                      key={row.row_number}
                      className={`hover:bg-stone-50/50 dark:hover:bg-forest-900/30 ${
                        !row.is_valid
                          ? 'bg-rose-50/40 dark:bg-rose-950/20'
                          : row.is_duplicate && skipDuplicates
                          ? 'bg-cream-50/60 dark:bg-forest-950/40'
                          : ''
                      }`}
                    >
                      <td className="py-2 font-mono text-stone-400">{row.row_number}</td>
                      <td className="py-2 font-mono text-stone-700 dark:text-sage-300">{row.date || '—'}</td>
                      <td className="py-2 font-medium text-forest-950 dark:text-cream-100 max-w-[200px] truncate">
                        {row.merchant}
                      </td>
                      <td className="py-2 text-stone-600 dark:text-sage-400">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] bg-stone-100 dark:bg-forest-900/60 text-stone-700 dark:text-sage-300 border border-stone-200 dark:border-forest-800">
                          {row.category}
                        </span>
                      </td>
                      <td className="py-2">
                        <span
                          className={`font-semibold text-[10px] ${
                            row.transaction_type === 'CREDIT'
                              ? 'text-forest-700 dark:text-forest-400 font-bold'
                              : 'text-stone-700 dark:text-cream-100'
                          }`}
                        >
                          {row.transaction_type}
                        </span>
                      </td>
                      <td className="py-2 text-right font-mono font-medium text-forest-950 dark:text-cream-100">
                        {row.amount !== null
                          ? `₹${row.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                          : '—'}
                      </td>
                      <td className="py-2 text-right">
                        {!row.is_valid ? (
                          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-rose-600 dark:text-rose-400">
                            <XCircle className="h-3 w-3" />
                            <span>Invalid</span>
                          </span>
                        ) : row.is_duplicate ? (
                          <span className="inline-flex items-center gap-1 text-[10px] font-bold bg-[#FFF2B4] text-[#15370D] border border-[#E5CD82] px-1.5 py-0.5 rounded">
                            <AlertTriangle className="h-3 w-3 text-[#15370D]" />
                            <span>{skipDuplicates ? 'Skipped Duplicate' : 'Duplicate'}</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[10px] font-medium bg-sage-100 text-sage-800 dark:bg-forest-900/70 dark:text-sage-300 px-1.5 py-0.5 rounded border border-sage-200 dark:border-forest-800">
                            <CheckCircle className="h-3 w-3 text-sage-600" />
                            <span>Valid</span>
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Action Bar */}
          <div className="flex items-center justify-between pt-2">
            <button
              onClick={() => setCurrentStep('MAP_COLUMNS')}
              className="px-4 py-2 rounded-xl border border-stone-200 dark:border-forest-800 text-xs font-semibold text-stone-700 dark:text-sage-300 hover:bg-stone-50 dark:hover:bg-forest-900"
            >
              Back to Column Mapping
            </button>
            <button
              onClick={handleCommit}
              disabled={committing || previewData.summary.valid_rows === 0}
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-[#15370D] hover:bg-[#1e4a14] text-[#FFF2B4] text-xs sm:text-sm font-semibold shadow-md transition disabled:opacity-50 border border-forest-800"
            >
              {committing ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin text-[#E5CD82]" />
                  <span>Ingesting into Db2 & Indexing Vectors...</span>
                </>
              ) : (
                <>
                  <Database className="h-4 w-4 text-[#E5CD82]" />
                  <span>
                    Commit{' '}
                    {skipDuplicates
                      ? previewData.summary.valid_rows - previewData.summary.duplicate_rows
                      : previewData.summary.valid_rows}{' '}
                    Transactions to Db2
                  </span>
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* STEP 4: RESULTS */}
      {currentStep === 'RESULTS' && commitResult && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-forest-200 dark:border-forest-800 bg-white dark:bg-[#10240d] p-8 text-center shadow-sm">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-[#15370D] text-[#FFF2B4] mb-4 shadow-sm border border-forest-800">
              <CheckCircle className="h-8 w-8" />
            </div>
            <h3 className="text-xl font-bold text-forest-950 dark:text-cream-100">
              Transactions Successfully Ingested into IBM Db2
            </h3>
            <p className="mt-1 text-xs sm:text-sm text-stone-600 dark:text-sage-400 max-w-lg mx-auto">
              Your financial records have been committed with strict ACID transaction guarantees. They are now live in your Command Center, AI Assistant, and Vector Search.
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 max-w-2xl mx-auto">
              <div className="p-3 rounded-xl bg-stone-50 dark:bg-[#163013] border border-stone-200 dark:border-forest-800">
                <span className="text-[10px] text-stone-500 dark:text-sage-400 uppercase tracking-wider font-semibold">Import Job ID</span>
                <div className="font-mono text-xs font-bold text-forest-950 dark:text-cream-100 mt-1 truncate">
                  {commitResult.import_id}
                </div>
              </div>

              <div className="p-3 rounded-xl bg-forest-50/60 dark:bg-forest-950/50 border border-forest-200 dark:border-forest-800">
                <span className="text-[10px] text-forest-800 dark:text-sage-300 uppercase tracking-wider font-semibold">Committed</span>
                <div className="text-xl font-bold font-mono text-forest-800 dark:text-sage-300 mt-1">
                  {commitResult.successful_rows}
                </div>
              </div>

              <div className="p-3 rounded-xl bg-cream-100/70 dark:bg-[#1f2e14] border border-gold-300 dark:border-forest-700">
                <span className="text-[10px] text-[#15370D] dark:text-[#E5CD82] uppercase tracking-wider font-semibold">Skipped Duplicates</span>
                <div className="text-xl font-bold font-mono text-[#15370D] dark:text-[#FFF2B4] mt-1">
                  {commitResult.skipped_duplicates}
                </div>
              </div>

              <div className="p-3 rounded-xl bg-rose-50/60 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/60">
                <span className="text-[10px] text-rose-700 dark:text-rose-400 uppercase tracking-wider font-semibold">Rejected Rows</span>
                <div className="text-xl font-bold font-mono text-rose-800 dark:text-rose-300 mt-1">
                  {commitResult.rejected_rows}
                </div>
              </div>
            </div>

            {/* Vector Indexing Status Telemetry */}
            <div className="mt-6 max-w-md mx-auto p-4 rounded-xl border border-stone-200 dark:border-forest-800 bg-stone-50/60 dark:bg-[#14290f]/60 text-left">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-forest-950 dark:text-cream-100 flex items-center gap-1.5">
                  <Layers className="h-3.5 w-3.5 text-sage-600 dark:text-gold-400" />
                  <span>FastEmbed Vector Indexing</span>
                </span>
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                    commitResult.indexing_status.status === 'COMPLETED'
                      ? 'bg-sage-100 text-sage-800 border-sage-300 dark:bg-forest-900/80 dark:text-sage-300 dark:border-forest-700'
                      : 'bg-rose-50 text-rose-700 border-rose-300 dark:bg-rose-950/60 dark:text-rose-400 dark:border-rose-800'
                  }`}
                >
                  {commitResult.indexing_status.status}
                </span>
              </div>
              <p className="text-xs text-stone-600 dark:text-sage-400">
                {commitResult.indexing_status.message}
              </p>
              {commitResult.indexing_status.status === 'FAILED' && (
                <button
                  onClick={handleRetryIndexing}
                  disabled={retryingIndex}
                  className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-forest-800 hover:text-forest-950 dark:text-gold-400 dark:hover:text-gold-300"
                >
                  <RefreshCw className={`h-3 w-3 ${retryingIndex ? 'animate-spin' : ''}`} />
                  <span>Retry Vector Indexing</span>
                </button>
              )}
            </div>

            {/* Navigation Actions */}
            <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
              <button
                onClick={resetImport}
                className="px-5 py-2.5 rounded-xl border border-stone-200 dark:border-forest-800 bg-white dark:bg-[#10240d] text-xs font-semibold text-stone-700 dark:text-sage-300 hover:bg-stone-50 dark:hover:bg-forest-900 transition"
              >
                Import Another File
              </button>
              {onNavigateToTransactions && (
                <button
                  onClick={onNavigateToTransactions}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#15370D] hover:bg-[#1e4a14] text-[#FFF2B4] text-xs font-semibold shadow-xs transition border border-forest-800"
                >
                  <span>View in Transaction Explorer</span>
                  <ExternalLink className="h-3.5 w-3.5 text-[#E5CD82]" />
                </button>
              )}
              {onNavigateToDashboard && (
                <button
                  onClick={onNavigateToDashboard}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border border-forest-300 dark:border-forest-700 text-forest-900 dark:text-gold-300 text-xs font-semibold hover:bg-forest-50 dark:hover:bg-forest-900/40 transition"
                >
                  <span>Command Center Overview</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
