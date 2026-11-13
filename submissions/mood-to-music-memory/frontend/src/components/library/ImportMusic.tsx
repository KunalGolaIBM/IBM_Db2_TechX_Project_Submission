import React, { useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Upload, X, Check } from 'lucide-react';

interface ImportMusicProps {
  onImport: (fileNames: string[]) => void;
}

const ImportMusic: React.FC<ImportMusicProps> = ({ onImport }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [toast, setToast] = useState<{ visible: boolean; count: number }>({
    visible: false,
    count: 0,
  });
  const timerRef = useRef<number | null>(null);

  const handleButtonClick = () => {
    inputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const fileNames = Array.from(files).map((f) => f.name);
    onImport(fileNames);

    setToast({ visible: true, count: fileNames.length });

    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      setToast((prev) => ({ ...prev, visible: false }));
    }, 4000);

    // Reset input so the same file can be re-imported
    e.target.value = '';
  };

  const dismissToast = () => {
    setToast((prev) => ({ ...prev, visible: false }));
    if (timerRef.current) clearTimeout(timerRef.current);
  };

  return (
    <div style={{ position: 'relative' }}>
      {/* Hidden file input */}
      <input
        ref={inputRef}
        type="file"
        accept="audio/*"
        multiple
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />

      {/* Import button */}
      <button
        onClick={handleButtonClick}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '6px 12px',
          borderRadius: 8,
          border: '1px solid rgba(168,85,247,0.4)',
          background: 'rgba(168,85,247,0.12)',
          color: 'rgba(216,180,254,0.9)',
          fontSize: 12,
          fontWeight: 500,
          cursor: 'pointer',
          transition: 'background 0.15s, border-color 0.15s',
          whiteSpace: 'nowrap',
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background =
            'rgba(168,85,247,0.22)';
          (e.currentTarget as HTMLButtonElement).style.borderColor =
            'rgba(168,85,247,0.7)';
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background =
            'rgba(168,85,247,0.12)';
          (e.currentTarget as HTMLButtonElement).style.borderColor =
            'rgba(168,85,247,0.4)';
        }}
      >
        <Upload size={13} />
        Import Music
      </button>

      {/* Success toast — fixed position, slides from right */}
      <AnimatePresence>
        {toast.visible && (
          <motion.div
            key="import-toast"
            initial={{ x: 80, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 80, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 320, damping: 28 }}
            style={{
              position: 'fixed',
              bottom: 28,
              right: 28,
              zIndex: 9999,
              minWidth: 260,
              background: 'rgba(22,163,74,0.95)',
              backdropFilter: 'blur(12px)',
              borderRadius: 12,
              padding: '12px 16px',
              boxShadow: '0 8px 32px rgba(0,0,0,0.45)',
              display: 'flex',
              alignItems: 'flex-start',
              gap: 10,
            }}
          >
            {/* Green check icon */}
            <span
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 28,
                height: 28,
                borderRadius: '50%',
                background: 'rgba(255,255,255,0.2)',
                flexShrink: 0,
                marginTop: 1,
              }}
            >
              <Check size={15} color="#fff" />
            </span>

            <div style={{ flex: 1 }}>
              <div
                style={{
                  color: '#fff',
                  fontWeight: 600,
                  fontSize: 13,
                  marginBottom: 2,
                }}
              >
                Import complete
              </div>
              <div style={{ color: 'rgba(255,255,255,0.80)', fontSize: 12 }}>
                {toast.count} song{toast.count !== 1 ? 's' : ''} added to your
                library.
              </div>

              {/* Action buttons */}
              <div
                style={{
                  display: 'flex',
                  gap: 8,
                  marginTop: 8,
                }}
              >
                <button
                  onClick={dismissToast}
                  style={{
                    padding: '4px 10px',
                    borderRadius: 6,
                    border: 'none',
                    background: 'rgba(255,255,255,0.22)',
                    color: '#fff',
                    fontSize: 11,
                    fontWeight: 500,
                    cursor: 'pointer',
                  }}
                >
                  View
                </button>
              </div>
            </div>

            {/* Dismiss X */}
            <button
              onClick={dismissToast}
              aria-label="Dismiss"
              style={{
                background: 'transparent',
                border: 'none',
                color: 'rgba(255,255,255,0.7)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                padding: 2,
                flexShrink: 0,
              }}
            >
              <X size={14} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default ImportMusic;
