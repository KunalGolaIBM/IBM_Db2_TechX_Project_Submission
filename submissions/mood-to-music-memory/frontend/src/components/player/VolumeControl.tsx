import React from 'react';
import { Volume2 } from 'lucide-react';
import { useAppStore } from '../../store/appStore';

export default function VolumeControl() {
  const { volume, setVolume } = useAppStore();

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        width: '100%',
      }}
    >
      <Volume2 size={16} color="rgba(255,255,255,0.5)" />
      <input
        type="range"
        min={0}
        max={1}
        step={0.01}
        value={volume}
        onChange={(e) => setVolume(parseFloat(e.target.value))}
        style={{
          flex: 1,
          height: '4px',
          appearance: 'none',
          background: `linear-gradient(90deg, #a855f7 ${volume * 100}%, rgba(255,255,255,0.12) ${volume * 100}%)`,
          borderRadius: '2px',
          cursor: 'pointer',
          outline: 'none',
        }}
      />
      <span
        style={{
          fontSize: '11px',
          color: 'rgba(255,255,255,0.45)',
          minWidth: '32px',
          textAlign: 'right',
        }}
      >
        {Math.round(volume * 100)}%
      </span>
    </div>
  );
}
