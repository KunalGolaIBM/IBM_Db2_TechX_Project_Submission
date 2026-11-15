import { useState, useRef, type ChangeEvent, type DragEvent } from 'react';
import { portabilityService } from '../services/portabilityService';
import type { ValidationResult, RestoreStrategy, RestoreResult } from '../types/portability';

interface ImportRestoreModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRestoreSuccess: (result: RestoreResult) => void;
}

export default function ImportRestoreModal({
  isOpen,
  onClose,
  onRestoreSuccess,
}: ImportRestoreModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [strategy, setStrategy] = useState<RestoreStrategy>('merge');
  const [confirmReplaceChecked, setConfirmReplaceChecked] = useState(false);
  const [confirmReplaceText, setConfirmReplaceText] = useState('');
  const [isRestoring, setIsRestoring] = useState(false);
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const [restoreSuccess, setRestoreSuccess] = useState<RestoreResult | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [showAllErrors, setShowAllErrors] = useState(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  if (!isOpen) return null;

  const resetState = () => {
    setFile(null);
    setValidation(null);
    setStrategy('merge');
    setConfirmReplaceChecked(false);
    setConfirmReplaceText('');
    setIsRestoring(false);
    setRestoreError(null);
    setRestoreSuccess(null);
    setIsDragging(false);
    setShowAllErrors(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleClose = () => {
    if (isRestoring) return; // Prevent closing while processing
    resetState();
    onClose();
  };

  const processFile = (selectedFile: File) => {
    setFile(selectedFile);
    setRestoreError(null);
    setRestoreSuccess(null);

    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result;
      if (typeof content === 'string') {
        const result = portabilityService.validateImport(content);
        setValidation(result);
      }
    };
    reader.onerror = () => {
      setValidation({
        valid: false,
        errors: [{ path: 'root', message: 'Unable to read the chosen file.' }],
      });
    };
    reader.readAsText(selectedFile);
  };

  const handleFileInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      processFile(selected);
    }
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      processFile(droppedFile);
    }
  };

  const handleExecuteRestore = async () => {
    if (!validation?.valid || !validation.data) return;

    if (strategy === 'replace') {
      if (!confirmReplaceChecked || confirmReplaceText.trim().toUpperCase() !== 'REPLACE') {
        setRestoreError('Please confirm the replacement safeguard by typing REPLACE and checking the acknowledgement box.');
        return;
      }
    }

    setIsRestoring(true);
    setRestoreError(null);

    try {
      const result = await portabilityService.restoreUserData(validation.data, strategy);
      if (result.success) {
        setRestoreSuccess(result);
        onRestoreSuccess(result);
      } else {
        setRestoreError(result.error ?? 'Restoration failed. Please check your data.');
      }
    } catch (err: unknown) {
      setRestoreError(err instanceof Error ? err.message : 'An unexpected error occurred during restoration.');
    } finally {
      setIsRestoring(false);
    }
  };

  const isReplaceConfirmed =
    strategy !== 'replace' ||
    (confirmReplaceChecked && confirmReplaceText.trim().toUpperCase() === 'REPLACE');

  const visibleErrors = validation?.errors ? (showAllErrors ? validation.errors : validation.errors.slice(0, 5)) : [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{
        backgroundColor: 'rgba(3, 6, 13, 0.8)',
        backdropFilter: 'blur(6px)',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      <div
        className="w-full max-w-xl rounded-2xl flex flex-col max-h-[90vh] overflow-hidden shadow-2xl transition-all"
        style={{
          backgroundColor: 'var(--color-app-surface)',
          border: '1px solid var(--color-app-border)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-6 py-4 border-b"
          style={{ borderColor: 'var(--color-app-border)' }}
        >
          <div>
            <h2 className="text-lg font-display font-semibold" style={{ color: 'var(--color-app-text)' }}>
              Restore & Migrate Data
            </h2>
            <p className="text-xs mt-0.5" style={{ color: 'var(--color-app-text-muted)' }}>
              Import tasks, missions, and session logs from a JSON backup.
            </p>
          </div>
          <button
            onClick={handleClose}
            disabled={isRestoring}
            aria-label="Close dialog"
            className="p-1.5 rounded-lg text-lg leading-none cursor-pointer border-none transition-colors"
            style={{
              backgroundColor: 'transparent',
              color: 'var(--color-app-text-dim)',
            }}
            onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.color = 'var(--color-app-text)')}
            onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.color = 'var(--color-app-text-dim)')}
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5">
          {/* Success Screen */}
          {restoreSuccess ? (
            <div className="text-center py-6 space-y-4">
              <div
                className="w-16 h-16 mx-auto rounded-full flex items-center justify-center text-3xl"
                style={{
                  backgroundColor: 'rgba(74, 140, 106, 0.15)',
                  border: '2px solid rgba(74, 140, 106, 0.4)',
                  color: 'var(--color-app-success)',
                }}
              >
                ✓
              </div>
              <div>
                <h3 className="text-xl font-display font-semibold" style={{ color: 'var(--color-app-text)' }}>
                  Restore Complete
                </h3>
                <p className="text-xs mt-1" style={{ color: 'var(--color-app-text-muted)' }}>
                  Your progress has been safely {restoreSuccess.strategy === 'replace' ? 'restored and replaced' : 'merged'}.
                </p>
              </div>

              {/* Statistics Grid */}
              <div className="grid grid-cols-3 gap-3 my-4">
                <div
                  className="rounded-xl p-3 text-center"
                  style={{
                    backgroundColor: 'var(--color-app-surface-raised)',
                    border: '1px solid var(--color-app-border)',
                  }}
                >
                  <p className="text-xl font-display font-semibold" style={{ color: 'var(--color-app-gold)' }}>
                    {restoreSuccess.tasksImported}
                  </p>
                  <p className="text-[0.65rem] uppercase tracking-wider mt-0.5" style={{ color: 'var(--color-app-text-dim)' }}>
                    Tasks
                  </p>
                </div>
                <div
                  className="rounded-xl p-3 text-center"
                  style={{
                    backgroundColor: 'var(--color-app-surface-raised)',
                    border: '1px solid var(--color-app-border)',
                  }}
                >
                  <p className="text-xl font-display font-semibold" style={{ color: 'var(--color-app-mission)' }}>
                    {restoreSuccess.missionsImported}
                  </p>
                  <p className="text-[0.65rem] uppercase tracking-wider mt-0.5" style={{ color: 'var(--color-app-text-dim)' }}>
                    Missions
                  </p>
                </div>
                <div
                  className="rounded-xl p-3 text-center"
                  style={{
                    backgroundColor: 'var(--color-app-surface-raised)',
                    border: '1px solid var(--color-app-border)',
                  }}
                >
                  <p className="text-xl font-display font-semibold" style={{ color: 'var(--color-app-text)' }}>
                    {restoreSuccess.sessionsImported}
                  </p>
                  <p className="text-[0.65rem] uppercase tracking-wider mt-0.5" style={{ color: 'var(--color-app-text-dim)' }}>
                    Sessions
                  </p>
                </div>
              </div>

              <div className="pt-2">
                <button
                  onClick={handleClose}
                  className="w-full py-2.5 px-4 rounded-xl text-sm font-semibold cursor-pointer border-none transition-all shadow-md"
                  style={{
                    backgroundColor: 'var(--color-app-gold)',
                    color: '#03060D',
                  }}
                >
                  Done
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* File Dropzone */}
              <div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".json,application/json"
                  className="hidden"
                  onChange={handleFileInputChange}
                />
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all"
                  style={{
                    borderColor: isDragging
                      ? 'var(--color-app-gold)'
                      : file
                      ? 'var(--color-app-mission)'
                      : 'var(--color-app-border)',
                    backgroundColor: isDragging
                      ? 'rgba(214, 168, 79, 0.08)'
                      : 'var(--color-app-surface-raised)',
                  }}
                >
                  <div className="w-10 h-10 mx-auto mb-2 rounded-full flex items-center justify-center text-xl"
                    style={{
                      backgroundColor: 'rgba(184, 122, 85, 0.15)',
                      color: 'var(--color-app-mission)',
                    }}>
                    📁
                  </div>
                  {file ? (
                    <div>
                      <p className="text-sm font-semibold truncate" style={{ color: 'var(--color-app-text)' }}>
                        {file.name}
                      </p>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--color-app-text-dim)' }}>
                        {(file.size / 1024).toFixed(1)} KB · Click or drag to choose another file
                      </p>
                    </div>
                  ) : (
                    <div>
                      <p className="text-sm font-medium" style={{ color: 'var(--color-app-text)' }}>
                        Drag & drop your Odyssey backup JSON here
                      </p>
                      <p className="text-xs mt-1" style={{ color: 'var(--color-app-text-muted)' }}>
                        or click to browse from your device
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Validation Feedback */}
              {validation && !validation.valid && (
                <div
                  className="rounded-xl p-4 space-y-2"
                  style={{
                    backgroundColor: 'rgba(168, 59, 59, 0.08)',
                    border: '1px solid rgba(168, 59, 59, 0.3)',
                  }}
                >
                  <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: '#E07070' }}>
                    <span>⚠️</span>
                    <span>Validation Failed ({validation.errors.length} issue{validation.errors.length === 1 ? '' : 's'})</span>
                  </div>
                  <p className="text-xs" style={{ color: 'var(--color-app-text-muted)' }}>
                    The uploaded file does not conform to the Odyssey schema. No existing data was modified.
                  </p>
                  <div className="space-y-1 mt-2 text-xs max-h-36 overflow-y-auto pr-1">
                    {visibleErrors.map((err, idx) => (
                      <div key={idx} className="flex items-start gap-1.5" style={{ color: '#E8A5A5' }}>
                        <span className="text-[0.65rem] opacity-75 mt-0.5">•</span>
                        <span>{err.message}</span>
                      </div>
                    ))}
                    {validation.errors.length > 5 && !showAllErrors && (
                      <button
                        onClick={() => setShowAllErrors(true)}
                        className="text-[0.7rem] font-semibold underline cursor-pointer bg-transparent border-none p-0 mt-1"
                        style={{ color: 'var(--color-app-gold)' }}
                      >
                        Show {validation.errors.length - 5} more issues...
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* Valid Backup Summary */}
              {validation && validation.valid && validation.summary && (
                <div
                  className="rounded-xl p-4 space-y-3"
                  style={{
                    backgroundColor: 'rgba(74, 140, 106, 0.08)',
                    border: '1px solid rgba(74, 140, 106, 0.3)',
                  }}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--color-app-success)' }}>
                      ✓ Valid Backup Package
                    </span>
                    {validation.exported_at && (
                      <span className="text-[0.65rem]" style={{ color: 'var(--color-app-text-dim)' }}>
                        Exported: {new Date(validation.exported_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="rounded-lg p-2" style={{ backgroundColor: 'var(--color-app-surface)' }}>
                      <p className="text-lg font-bold" style={{ color: 'var(--color-app-text)' }}>
                        {validation.summary.task_count}
                      </p>
                      <p className="text-[0.6rem] uppercase tracking-wider" style={{ color: 'var(--color-app-text-dim)' }}>
                        Tasks
                      </p>
                    </div>
                    <div className="rounded-lg p-2" style={{ backgroundColor: 'var(--color-app-surface)' }}>
                      <p className="text-lg font-bold" style={{ color: 'var(--color-app-text)' }}>
                        {validation.summary.mission_count}
                      </p>
                      <p className="text-[0.6rem] uppercase tracking-wider" style={{ color: 'var(--color-app-text-dim)' }}>
                        Missions
                      </p>
                    </div>
                    <div className="rounded-lg p-2" style={{ backgroundColor: 'var(--color-app-surface)' }}>
                      <p className="text-lg font-bold" style={{ color: 'var(--color-app-text)' }}>
                        {validation.summary.session_count}
                      </p>
                      <p className="text-[0.6rem] uppercase tracking-wider" style={{ color: 'var(--color-app-text-dim)' }}>
                        Sessions
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Restoration Strategy Selection */}
              {validation?.valid && (
                <div className="space-y-3 pt-2">
                  <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--color-app-text-muted)' }}>
                    Restoration Mode
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {/* Merge Option */}
                    <div
                      onClick={() => setStrategy('merge')}
                      className="rounded-xl p-3.5 cursor-pointer transition-all border"
                      style={{
                        backgroundColor:
                          strategy === 'merge' ? 'rgba(214, 168, 79, 0.08)' : 'var(--color-app-surface-raised)',
                        borderColor:
                          strategy === 'merge' ? 'var(--color-app-gold)' : 'var(--color-app-border)',
                      }}
                    >
                      <div className="flex items-center gap-2">
                        <input
                          type="radio"
                          name="strategy"
                          checked={strategy === 'merge'}
                          onChange={() => setStrategy('merge')}
                          className="accent-[#D6A84F]"
                        />
                        <span className="text-sm font-semibold" style={{ color: 'var(--color-app-text)' }}>
                          Merge Data
                        </span>
                      </div>
                      <p className="text-xs mt-1.5 ml-5" style={{ color: 'var(--color-app-text-muted)' }}>
                        Preserves your current progress and safely integrates items from the backup.
                      </p>
                    </div>

                    {/* Replace Option */}
                    <div
                      onClick={() => setStrategy('replace')}
                      className="rounded-xl p-3.5 cursor-pointer transition-all border"
                      style={{
                        backgroundColor:
                          strategy === 'replace' ? 'rgba(168, 59, 59, 0.08)' : 'var(--color-app-surface-raised)',
                        borderColor:
                          strategy === 'replace' ? '#E07070' : 'var(--color-app-border)',
                      }}
                    >
                      <div className="flex items-center gap-2">
                        <input
                          type="radio"
                          name="strategy"
                          checked={strategy === 'replace'}
                          onChange={() => setStrategy('replace')}
                          className="accent-[#E07070]"
                        />
                        <span className="text-sm font-semibold" style={{ color: strategy === 'replace' ? '#E07070' : 'var(--color-app-text)' }}>
                          Replace Data
                        </span>
                      </div>
                      <p className="text-xs mt-1.5 ml-5" style={{ color: 'var(--color-app-text-muted)' }}>
                        Overwrites current tasks, missions, and session logs with this backup.
                      </p>
                    </div>
                  </div>

                  {/* Explicit Confirmation Safeguard for Replace Strategy */}
                  {strategy === 'replace' && (
                    <div
                      className="rounded-xl p-4 mt-3 space-y-3"
                      style={{
                        backgroundColor: 'rgba(168, 59, 59, 0.1)',
                        border: '1px solid rgba(168, 59, 59, 0.35)',
                      }}
                    >
                      <div className="flex items-start gap-2">
                        <span className="text-sm">⚠️</span>
                        <div>
                          <p className="text-xs font-bold uppercase tracking-wider text-red-400">
                            Irreversible Action Warning
                          </p>
                          <p className="text-xs mt-0.5" style={{ color: 'var(--color-app-text-muted)' }}>
                            Replacing your records will permanently erase all existing tasks, missions, and session history before loading the backup.
                          </p>
                        </div>
                      </div>

                      <label className="flex items-start gap-2 cursor-pointer select-none text-xs" style={{ color: 'var(--color-app-text)' }}>
                        <input
                          type="checkbox"
                          checked={confirmReplaceChecked}
                          onChange={(e) => setConfirmReplaceChecked(e.target.checked)}
                          className="mt-0.5 accent-red-500"
                        />
                        <span>I understand that all my current Odyssey data will be permanently overwritten.</span>
                      </label>

                      <div>
                        <label className="block text-[0.7rem] uppercase tracking-wider mb-1 font-semibold" style={{ color: 'var(--color-app-text-dim)' }}>
                          Type <span className="text-red-400 font-mono">REPLACE</span> to confirm:
                        </label>
                        <input
                          type="text"
                          value={confirmReplaceText}
                          onChange={(e) => setConfirmReplaceText(e.target.value)}
                          placeholder="REPLACE"
                          className="w-full px-3 py-1.5 rounded-lg text-sm font-mono border"
                          style={{
                            backgroundColor: 'var(--color-app-surface)',
                            borderColor: confirmReplaceText.trim().toUpperCase() === 'REPLACE' ? '#4A8C6A' : 'rgba(168,59,59,0.4)',
                            color: 'var(--color-app-text)',
                          }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* General Error Message */}
              {restoreError && (
                <div
                  className="rounded-xl p-3 text-xs flex items-center gap-2"
                  style={{
                    backgroundColor: 'rgba(168, 59, 59, 0.12)',
                    border: '1px solid rgba(168, 59, 59, 0.3)',
                    color: '#E07070',
                  }}
                >
                  <span>⚠️</span>
                  <span>{restoreError}</span>
                </div>
              )}
            </>
          )}
        </div>

        {/* Modal Footer */}
        {!restoreSuccess && (
          <div
            className="flex items-center justify-end gap-3 px-6 py-4 border-t"
            style={{ borderColor: 'var(--color-app-border)' }}
          >
            <button
              onClick={handleClose}
              disabled={isRestoring}
              className="px-4 py-2 rounded-xl text-xs font-semibold cursor-pointer border transition-colors"
              style={{
                backgroundColor: 'transparent',
                borderColor: 'var(--color-app-border)',
                color: 'var(--color-app-text-muted)',
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleExecuteRestore}
              disabled={!validation?.valid || !isReplaceConfirmed || isRestoring}
              className="px-5 py-2 rounded-xl text-xs font-semibold cursor-pointer border-none transition-all flex items-center gap-2 shadow"
              style={{
                backgroundColor:
                  strategy === 'replace'
                    ? isReplaceConfirmed
                      ? '#E07070'
                      : 'rgba(168, 59, 59, 0.3)'
                    : validation?.valid
                    ? 'var(--color-app-gold)'
                    : 'var(--color-app-surface-raised)',
                color: strategy === 'replace' ? '#FFFFFF' : '#03060D',
                opacity: (!validation?.valid || !isReplaceConfirmed || isRestoring) ? 0.5 : 1,
                cursor: (!validation?.valid || !isReplaceConfirmed || isRestoring) ? 'not-allowed' : 'pointer',
              }}
            >
              {isRestoring ? (
                <>
                  <div
                    className="w-3.5 h-3.5 border-2 rounded-full animate-spin"
                    style={{ borderColor: '#03060D', borderTopColor: 'transparent' }}
                  />
                  <span>Restoring...</span>
                </>
              ) : strategy === 'replace' ? (
                'Confirm & Replace All Data'
              ) : (
                'Restore & Merge Data'
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
