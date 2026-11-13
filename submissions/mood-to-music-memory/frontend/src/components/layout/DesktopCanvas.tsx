import React, { useState, useEffect, useRef } from 'react';
import MoodSelection   from '../panels/MoodSelection';
import NowPlaying      from '../panels/NowPlaying';
import MyLibrary       from '../panels/MyLibrary';
import MoodMemories    from '../panels/MoodMemories';
import FloatingWidgets from '../panels/FloatingWidgets';

/** PRD §4.2 reference canvas size */
const REF_W = 1672;
const REF_H = 941;

/** Panel layout from PRD §4.2 */
const PANELS = [
  { key: 'MoodSelection',   left: 134,  top: 35,  width: 686, height: 451 },
  { key: 'NowPlaying',      left: 835,  top: 35,  width: 741, height: 451 },
  { key: 'MyLibrary',       left: 96,   top: 506, width: 486, height: 343 },
  { key: 'MoodMemories',    left: 601,  top: 506, width: 555, height: 343 },
  { key: 'FloatingWidgets', left: 1175, top: 506, width: 357, height: 343 },
] as const;

const PANEL_COMPONENTS: Record<string, React.ComponentType> = {
  MoodSelection,
  NowPlaying,
  MyLibrary,
  MoodMemories,
  FloatingWidgets,
};

function computeScale(): number {
  return Math.min(window.innerWidth / REF_W, window.innerHeight / REF_H);
}

const DesktopCanvas: React.FC = () => {
  const [scale, setScale] = useState<number>(computeScale);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleResize = () => setScale(computeScale());

    // ResizeObserver on the viewport root
    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(handleResize);
      ro.observe(document.documentElement);
    } else {
      window.addEventListener('resize', handleResize);
    }

    return () => {
      if (ro) ro.disconnect();
      else window.removeEventListener('resize', handleResize);
    };
  }, []);

  return (
    /**
     * Outer wrapper — full viewport, clips any overflow during scale transitions
     */
    <div
      style={{
        position: 'absolute',
        inset: 0,
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {/**
       * The reference canvas: always REF_W × REF_H px,
       * scaled uniformly to fit the viewport.
       */}
      <div
        ref={containerRef}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: REF_W,
          height: REF_H,
          transform: `scale(${scale})`,
          transformOrigin: 'top left',
        }}
      >
        {PANELS.map(panel => {
          const Component = PANEL_COMPONENTS[panel.key];
          return (
            <div
              key={panel.key}
              style={{
                position: 'absolute',
                left:   panel.left,
                top:    panel.top,
                width:  panel.width,
                height: panel.height,
                overflow: 'hidden',
                borderRadius: 12,
                background: 'rgba(255,255,255,0.03)',
                backdropFilter: 'blur(12px)',
                WebkitBackdropFilter: 'blur(12px)',
                border: '1px solid rgba(255,255,255,0.07)',
                boxShadow: '0 8px 32px rgba(0,0,0,0.45)',
              }}
            >
              <Component />
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default DesktopCanvas;
