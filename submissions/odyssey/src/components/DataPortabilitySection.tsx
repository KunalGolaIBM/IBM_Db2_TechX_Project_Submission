import { useState } from 'react';
import { portabilityService } from '../services/portabilityService';
import ImportRestoreModal from './ImportRestoreModal';

interface DataPortabilitySectionProps {
  taskCount: number;
  missionCount: number;
  sessionCount: number;
  onDataRestored: () => void;
}

export default function DataPortabilitySection({
  taskCount,
  missionCount,
  sessionCount,
  onDataRestored,
}: DataPortabilitySectionProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const handleExport = async () => {
    setIsExporting(true);
    setExportMessage(null);
    try {
      const { filename } = await portabilityService.downloadBackupFile();
      setExportMessage(`Saved backup as ${filename}`);
      setTimeout(() => setExportMessage(null), 6000);
    } catch (err: unknown) {
      setExportMessage(err instanceof Error ? err.message : 'Export failed. Please try again.');
      setTimeout(() => setExportMessage(null), 6000);
    } finally {
      setIsExporting(false);
    }
  };

  const handleRestoreSuccess = () => {
    onDataRestored();
  };

  return (
    <section className="mb-8">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--color-app-text-muted)' }}>
            Data Backup & Portability
          </h2>
          <p className="text-xs mt-0.5" style={{ color: 'var(--color-app-text-dim)' }}>
            Safely export your history as structured JSON, or restore progress across devices.
          </p>
        </div>
        <div
          className="text-[0.65rem] font-semibold px-2.5 py-1 rounded-full self-start sm:self-auto flex items-center gap-1.5"
          style={{
            backgroundColor: 'var(--color-app-surface-raised)',
            border: '1px solid var(--color-app-border)',
            color: 'var(--color-app-gold)',
          }}
        >
          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: 'var(--color-app-gold)' }} />
          <span>{taskCount} tasks · {missionCount} missions · {sessionCount} sessions</span>
        </div>
      </div>

      {/* Export / Import Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Export Card */}
        <div
          className="rounded-xl p-5 flex flex-col justify-between transition-all"
          style={{
            backgroundColor: 'var(--color-app-surface)',
            border: '1px solid var(--color-app-border)',
          }}
        >
          <div className="flex items-start gap-3.5 mb-4">
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 text-lg"
              style={{
                backgroundColor: 'rgba(214, 168, 79, 0.12)',
                color: 'var(--color-app-gold)',
                border: '1px solid rgba(214, 168, 79, 0.25)',
              }}
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.5V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold" style={{ color: 'var(--color-app-text)' }}>
                Export Structured JSON
              </h3>
              <p className="text-xs mt-1 leading-relaxed" style={{ color: 'var(--color-app-text-dim)' }}>
                Download your full mission, task, and focus session history as a clean, portable JSON package.
              </p>
            </div>
          </div>

          <div className="space-y-2 pt-2">
            <button
              onClick={handleExport}
              disabled={isExporting}
              className="w-full py-2 px-4 rounded-lg text-xs font-semibold cursor-pointer border transition-all flex items-center justify-center gap-2"
              style={{
                backgroundColor: 'rgba(214, 168, 79, 0.1)',
                borderColor: 'rgba(214, 168, 79, 0.3)',
                color: 'var(--color-app-gold)',
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'rgba(214, 168, 79, 0.18)';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'rgba(214, 168, 79, 0.1)';
              }}
            >
              {isExporting ? (
                <>
                  <div
                    className="w-3.5 h-3.5 border-2 rounded-full animate-spin"
                    style={{ borderColor: 'var(--color-app-gold)', borderTopColor: 'transparent' }}
                  />
                  <span>Generating JSON...</span>
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  <span>Export Data (.json)</span>
                </>
              )}
            </button>

            {exportMessage && (
              <p className="text-[0.7rem] text-center font-medium animate-fade-in" style={{ color: 'var(--color-app-gold)' }}>
                {exportMessage}
              </p>
            )}
          </div>
        </div>

        {/* Import Card */}
        <div
          className="rounded-xl p-5 flex flex-col justify-between transition-all"
          style={{
            backgroundColor: 'var(--color-app-surface)',
            border: '1px solid var(--color-app-border)',
          }}
        >
          <div className="flex items-start gap-3.5 mb-4">
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 text-lg"
              style={{
                backgroundColor: 'rgba(184, 122, 85, 0.12)',
                color: 'var(--color-app-mission)',
                border: '1px solid rgba(184, 122, 85, 0.25)',
              }}
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.5V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold" style={{ color: 'var(--color-app-text)' }}>
                Import & Restore Backup
              </h3>
              <p className="text-xs mt-1 leading-relaxed" style={{ color: 'var(--color-app-text-dim)' }}>
                Upload an existing JSON backup with schema validation. Safely choose between merging or replacing data.
              </p>
            </div>
          </div>

          <div className="pt-2">
            <button
              onClick={() => setIsModalOpen(true)}
              className="w-full py-2 px-4 rounded-lg text-xs font-semibold cursor-pointer border transition-all flex items-center justify-center gap-2"
              style={{
                backgroundColor: 'rgba(184, 122, 85, 0.1)',
                borderColor: 'rgba(184, 122, 85, 0.3)',
                color: 'var(--color-app-mission)',
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'rgba(184, 122, 85, 0.18)';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'rgba(184, 122, 85, 0.1)';
              }}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              <span>Import & Restore Data...</span>
            </button>
          </div>
        </div>
      </div>

      {/* Modal Dialog */}
      <ImportRestoreModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onRestoreSuccess={handleRestoreSuccess}
      />
    </section>
  );
}
