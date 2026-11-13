import React from 'react';
import { MiniPlayer } from '../player/MiniPlayer';
import { CurrentSession } from '../session/CurrentSession';

export const FloatingWidgets: React.FC = () => {
  return (
    <div className="flex flex-col gap-3 h-full w-full">
      {/* Mini Player — ~55% height */}
      <div style={{ flex: '0 0 55%' }} className="flex flex-col min-h-0">
        <MiniPlayer />
      </div>

      {/* Current Session — ~45% height */}
      <div style={{ flex: '0 0 calc(45% - 12px)' }} className="flex flex-col min-h-0">
        <CurrentSession />
      </div>
    </div>
  );
};

export default FloatingWidgets;
