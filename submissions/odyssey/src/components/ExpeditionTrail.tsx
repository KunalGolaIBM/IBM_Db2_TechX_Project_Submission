import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import type { CSSProperties, KeyboardEvent, ReactNode, RefObject } from 'react';
import { Link } from 'react-router-dom';
import type { FocusSession, Mission } from '../types/database';
import {
  TRAIL_WIDTH,
  buildWaypoints,
  formatMinutes,
  layoutTrail,
  pathThrough,
} from '../lib/expeditionTrail';
import type { Waypoint } from '../lib/expeditionTrail';

// ─── Small helpers ───────────────────────────────────────────────────────────

const WIDE_QUERY = '(min-width: 768px)';
const NODE_SIZE = 34;

function subscribeWide(onChange: () => void) {
  const mq = window.matchMedia(WIDE_QUERY);
  mq.addEventListener('change', onChange);
  return () => mq.removeEventListener('change', onChange);
}

function useIsWide() {
  return useSyncExternalStore(
    subscribeWide,
    () => window.matchMedia(WIDE_QUERY).matches,
    () => true,
  );
}

function formatDate(iso: string | null, long = false) {
  if (!iso) return 'Date not recorded';
  return new Date(iso).toLocaleDateString(undefined, long
    ? { year: 'numeric', month: 'long', day: 'numeric' }
    : { month: 'short', day: 'numeric', year: 'numeric' });
}

function focusLabel(wp: Waypoint) {
  return wp.focusMinutes > 0 ? `${formatMinutes(wp.focusMinutes)} focus` : 'No focus logged';
}

function waypointAriaLabel(wp: Waypoint, isLatest: boolean) {
  return `Waypoint ${wp.index}: ${wp.mission.title}. Completed ${formatDate(wp.completedAt)}. ${focusLabel(wp)}.${isLatest ? ' Latest waypoint.' : ''}`;
}

// ─── Node markers ────────────────────────────────────────────────────────────

type NodeKind = 'camp' | 'done' | 'latest' | 'next';

function TrailNode({ kind, label, selected }: { kind: NodeKind; label?: number; selected?: boolean }) {
  const done = kind === 'done' || kind === 'latest';
  return (
    <span
      className="relative flex items-center justify-center rounded-full flex-shrink-0 font-mono text-xs font-bold"
      data-node={kind}
      style={{
        width: NODE_SIZE,
        height: NODE_SIZE,
        backgroundColor: kind === 'latest' ? 'var(--color-app-gold)' : 'var(--color-app-surface-raised)',
        color: kind === 'latest' ? 'var(--color-app-bg)' : done ? 'var(--color-app-gold)' : 'var(--color-app-mission)',
        border: `2px ${kind === 'next' ? 'dashed' : 'solid'} ${done ? 'var(--color-app-gold)' : kind === 'next' ? 'var(--color-app-mission)' : 'var(--color-app-text-muted)'}`,
        boxShadow: selected
          ? '0 0 0 4px var(--color-app-gold-light)'
          : done ? '0 0 14px var(--color-app-gold-glow)' : 'none',
      }}
      aria-hidden="true"
    >
      {kind === 'latest' && (
        <span className="absolute rounded-full animate-pulse pointer-events-none"
          style={{ inset: -7, border: '1.5px solid var(--color-app-gold)', opacity: 0.6 }} />
      )}
      {kind === 'camp' && (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
          strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--color-app-text-muted)' }}>
          <path d="M3 20L12 4l9 16H3z" />
          <path d="M12 20v-6l-3 6" />
        </svg>
      )}
      {kind === 'next' && (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round">
          <path d="M12 5v14M5 12h14" />
        </svg>
      )}
      {done && label}
    </span>
  );
}

function CaptionCard({ children, dashed = false, selected = false }: { children: ReactNode; dashed?: boolean; selected?: boolean }) {
  return (
    <span
      className="flex flex-col gap-0.5 w-full rounded-lg px-2.5 py-2 text-center"
      style={{
        backgroundColor: 'var(--color-app-surface)',
        border: `1px ${dashed ? 'dashed' : 'solid'} ${selected ? 'var(--color-app-gold)' : 'var(--color-app-border)'}`,
      }}
    >
      {children}
    </span>
  );
}

function WaypointCaption({ wp, selected }: { wp: Waypoint; selected: boolean }) {
  return (
    <CaptionCard selected={selected}>
      <span className="text-[0.6rem] font-mono uppercase tracking-wider" style={{ color: 'var(--color-app-text-muted)' }}>
        {formatDate(wp.completedAt)}
      </span>
      <span className="text-[0.8rem] font-semibold leading-snug line-clamp-2 break-words" style={{ color: 'var(--color-app-text)' }}>
        {wp.mission.title}
      </span>
      <span className="text-[0.65rem] font-mono" style={{ color: 'var(--color-app-text-muted)' }}>
        {focusLabel(wp)}
      </span>
    </CaptionCard>
  );
}

function CampCaption() {
  return (
    <CaptionCard>
      <span className="text-[0.8rem] font-semibold" style={{ color: 'var(--color-app-text)' }}>Base Camp</span>
      <span className="text-[0.65rem]" style={{ color: 'var(--color-app-text-muted)' }}>Where the expedition starts</span>
    </CaptionCard>
  );
}

function NextCaption({ first }: { first: boolean }) {
  return (
    <CaptionCard dashed>
      <span className="text-[0.8rem] font-semibold" style={{ color: 'var(--color-app-mission)' }}>
        {first ? 'First waypoint' : 'Next waypoint'}
      </span>
      <span className="text-[0.65rem]" style={{ color: 'var(--color-app-text-muted)' }}>Plan a mission</span>
    </CaptionCard>
  );
}

// ─── Waypoint detail panel ───────────────────────────────────────────────────

function DetailPanel({
  wp, total, isLatest, panelRef, onClose, onKeyDown, className = '', style,
}: {
  wp: Waypoint;
  total: number;
  isLatest: boolean;
  panelRef: RefObject<HTMLDivElement | null>;
  onClose: () => void;
  onKeyDown: (e: KeyboardEvent<HTMLDivElement>) => void;
  className?: string;
  style?: CSSProperties;
}) {
  const { objective, next_action, planned_minutes } = wp.mission;
  const hasReflection = Boolean(objective?.trim() || next_action?.trim());
  return (
    <div
      id="expedition-detail"
      ref={panelRef}
      role="region"
      aria-labelledby="expedition-detail-title"
      tabIndex={0}
      onKeyDown={onKeyDown}
      className={`rounded-xl px-4 py-3.5 ${className}`}
      style={{
        backgroundColor: 'var(--color-app-surface-raised)',
        border: '1px solid var(--color-app-mission)',
        backdropFilter: 'blur(12px)',
        ...style,
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[0.6rem] font-mono uppercase tracking-wider" style={{ color: 'var(--color-app-mission)' }}>
              Waypoint {wp.index} of {total}
            </span>
            {isLatest && (
              <span className="text-[0.55rem] font-bold px-1.5 py-0.5 rounded uppercase"
                style={{ backgroundColor: 'var(--color-app-gold-light)', color: 'var(--color-app-gold)' }}>
                You are here
              </span>
            )}
          </div>
          <h3 id="expedition-detail-title" className="text-base font-semibold break-words" style={{ color: 'var(--color-app-text)' }}>
            {wp.mission.title}
          </h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close waypoint details"
          className="text-sm leading-none p-1 rounded cursor-pointer bg-transparent border-none flex-shrink-0"
          style={{ color: 'var(--color-app-text-dim)' }}
        >
          ✕
        </button>
      </div>

      <dl className="grid grid-cols-1 sm:grid-cols-3 gap-x-4 gap-y-2 mt-3 mb-0">
        {[
          { label: 'Completed', value: formatDate(wp.completedAt, true) },
          {
            label: 'Focus time',
            value: wp.focusMinutes > 0
              ? wp.sessionCount > 0
                ? `${formatMinutes(wp.focusMinutes)} in ${wp.sessionCount} ${wp.sessionCount === 1 ? 'session' : 'sessions'}`
                : formatMinutes(wp.focusMinutes)
              : 'No focus sessions logged',
          },
          { label: 'Planned', value: planned_minutes ? formatMinutes(planned_minutes) : 'Not set' },
        ].map(({ label, value }) => (
          <div key={label}>
            <dt className="text-[0.6rem] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-app-text-muted)' }}>{label}</dt>
            <dd className="text-xs font-mono m-0" style={{ color: 'var(--color-app-text)' }}>{value}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--color-app-border)' }}>
        <p className="text-[0.6rem] font-semibold uppercase tracking-wider mb-1.5" style={{ color: 'var(--color-app-text-muted)' }}>
          Reflection
        </p>
        {hasReflection ? (
          <div className="flex flex-col gap-1.5 text-xs leading-relaxed" style={{ color: 'var(--color-app-text)' }}>
            {objective?.trim() && (
              <p className="m-0"><span style={{ color: 'var(--color-app-text-dim)' }}>Objective: </span>{objective}</p>
            )}
            {next_action?.trim() && (
              <p className="m-0"><span style={{ color: 'var(--color-app-text-dim)' }}>Next action: </span>{next_action}</p>
            )}
          </div>
        ) : (
          <p className="text-xs m-0" style={{ color: 'var(--color-app-text-dim)' }}>
            No objective or next action was recorded for this mission.
          </p>
        )}
      </div>
    </div>
  );
}

// ─── Empty state ─────────────────────────────────────────────────────────────

function BaseCampNotice({ className = '', style }: { className?: string; style?: CSSProperties }) {
  return (
    <div className={`rounded-xl px-5 py-4 ${className}`}
      style={{ backgroundColor: 'var(--color-app-surface-raised)', border: '1px solid var(--color-app-border)', ...style }}>
      <p className="text-sm font-semibold mb-1" style={{ color: 'var(--color-app-text)' }}>
        You are at Base Camp
      </p>
      <p className="text-xs leading-relaxed mb-3" style={{ color: 'var(--color-app-text-muted)' }}>
        No missions completed yet. Finish your first one and it becomes waypoint 1 on this trail,
        with the date and the focus time you put into it.
      </p>
      <Link
        to="/mission"
        className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg no-underline"
        style={{ color: 'var(--color-app-mission)', border: '1px solid var(--color-app-mission)', backgroundColor: 'var(--color-app-mission-glow)' }}
      >
        Plan your first mission
        <span aria-hidden="true">→</span>
      </Link>
    </div>
  );
}

// ─── Main component ──────────────────────────────────────────────────────────

export default function ExpeditionTrail({ missions, sessions }: { missions: Mission[]; sessions: FocusSession[] }) {
  const waypoints = useMemo(() => buildWaypoints(missions, sessions), [missions, sessions]);
  const total = waypoints.length;
  const totalMinutes = useMemo(() => waypoints.reduce((sum, w) => sum + w.focusMinutes, 0), [waypoints]);
  const isWide = useIsWide();

  // undefined = nothing picked yet (wide layout opens the latest waypoint by default)
  const [picked, setPicked] = useState<number | null | undefined>(undefined);
  const selectedIndex = picked === undefined ? (isWide && total > 0 ? total : null) : picked;
  const selected = waypoints.find(w => w.index === selectedIndex) ?? null;

  const panelRef = useRef<HTMLDivElement>(null);
  const buttonRefs = useRef(new Map<number, HTMLButtonElement>());
  const focusPanelNext = useRef(false);

  // Move focus to the panel after a waypoint is opened, so keyboard users land on its content.
  useEffect(() => {
    if (!focusPanelNext.current || !selected) return;
    focusPanelNext.current = false;
    panelRef.current?.focus({ preventScroll: true });
    panelRef.current?.scrollIntoView({ block: 'nearest' });
  }, [selected]);

  const select = (index: number) => {
    if (selectedIndex === index) {
      setPicked(null);
      return;
    }
    focusPanelNext.current = true;
    setPicked(index);
  };

  const closeFromPanel = () => {
    const index = selectedIndex;
    setPicked(null);
    if (index !== null) buttonRefs.current.get(index)?.focus();
  };

  const onPanelKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape') {
      e.stopPropagation();
      closeFromPanel();
    }
  };

  const registerButton = (index: number) => (el: HTMLButtonElement | null) => {
    if (el) buttonRefs.current.set(index, el);
    else buttonRefs.current.delete(index);
  };

  // Base Camp + one point per waypoint + the "next waypoint" marker
  const layout = useMemo(() => layoutTrail(total + 2), [total]);
  const fullPath = pathThrough(layout, 0, layout.segments.length);
  const walkedPath = pathThrough(layout, 0, total);

  // Draw the walked part of the trail in after mount
  const [drawn, setDrawn] = useState(false);
  useEffect(() => {
    let inner = 0;
    const outer = requestAnimationFrame(() => { inner = requestAnimationFrame(() => setDrawn(true)); });
    return () => { cancelAnimationFrame(outer); cancelAnimationFrame(inner); };
  }, []);

  const telemetry = total === 0
    ? 'Expedition route · at Base Camp'
    : `Expedition route · ${total} ${total === 1 ? 'waypoint' : 'waypoints'} · ${formatMinutes(totalMinutes)} focus`;

  return (
    <section
      aria-label="Expedition milestone trail"
      className="rounded-2xl px-4 sm:px-6 pt-4 pb-5"
      style={{
        backgroundColor: 'var(--color-app-surface)',
        border: '1px solid var(--color-app-border)',
        backgroundImage: 'radial-gradient(var(--color-app-border) 1px, transparent 1px)',
        backgroundSize: '22px 22px',
      }}
    >
      <div className="flex items-center gap-2 mb-3">
        <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: 'var(--color-app-mission)' }} />
        <span className="text-[0.6rem] font-mono tracking-widest uppercase" style={{ color: 'var(--color-app-gold)' }}>
          {telemetry}
        </span>
      </div>

      {isWide ? (
        <>
          <div className="relative w-full" style={{ aspectRatio: `${TRAIL_WIDTH} / ${layout.height}` }}>
            <svg
              viewBox={`0 0 ${TRAIL_WIDTH} ${layout.height}`}
              className="absolute inset-0 w-full h-full"
              aria-hidden="true"
              focusable="false"
            >
              {fullPath && (
                <path d={fullPath} fill="none" strokeWidth="3" strokeLinecap="round" strokeDasharray="2 9"
                  style={{ stroke: 'var(--color-app-text-dim)' }} />
              )}
              {walkedPath && (
                <path
                  d={walkedPath}
                  pathLength={1}
                  fill="none"
                  strokeWidth="4"
                  strokeLinecap="round"
                  strokeDasharray="1"
                  style={{
                    stroke: 'var(--color-app-gold)',
                    strokeDashoffset: drawn ? 0 : 1,
                    transition: 'stroke-dashoffset 1.6s cubic-bezier(0.22, 1, 0.36, 1)',
                    filter: 'drop-shadow(0 0 5px var(--color-app-gold-glow))',
                  }}
                />
              )}
            </svg>

            <ol className="absolute inset-0 m-0 p-0 list-none">
              {layout.points.map((pt, i) => {
                const isCamp = i === 0;
                const isNext = i === layout.points.length - 1;
                const wp = !isCamp && !isNext ? waypoints[i - 1] : null;
                const isLatest = wp !== null && wp.index === total;
                const isSelected = wp !== null && wp.index === selectedIndex;
                return (
                  <li
                    key={isCamp ? 'camp' : isNext ? 'next' : wp!.mission.id}
                    className="absolute flex flex-col items-center"
                    style={{
                      left: `${(pt.x / TRAIL_WIDTH) * 100}%`,
                      top: `${(pt.y / layout.height) * 100}%`,
                      width: '22%',
                      transform: `translate(-50%, -${NODE_SIZE / 2}px)`,
                    }}
                  >
                    {wp ? (
                      <button
                        type="button"
                        ref={registerButton(wp.index)}
                        onClick={() => select(wp.index)}
                        aria-expanded={isSelected}
                        aria-controls={isSelected ? 'expedition-detail' : undefined}
                        aria-label={waypointAriaLabel(wp, isLatest)}
                        className="flex flex-col items-center gap-2 w-full p-1 rounded-xl bg-transparent border-none cursor-pointer"
                      >
                        <TrailNode kind={isLatest ? 'latest' : 'done'} label={wp.index} selected={isSelected} />
                        <WaypointCaption wp={wp} selected={isSelected} />
                      </button>
                    ) : isNext ? (
                      <Link to="/mission" className="flex flex-col items-center gap-2 w-full p-1 rounded-xl no-underline"
                        aria-label={`${total === 0 ? 'First' : 'Next'} waypoint: plan a mission`}>
                        <TrailNode kind="next" />
                        <NextCaption first={total === 0} />
                      </Link>
                    ) : (
                      <div className="flex flex-col items-center gap-2 w-full p-1">
                        <TrailNode kind="camp" />
                        <CampCaption />
                      </div>
                    )}
                  </li>
                );
              })}
            </ol>

            {total === 0 && (
              <BaseCampNotice className="absolute" style={{ left: '56%', right: '4%', top: '50%', transform: 'translateY(-50%)' }} />
            )}
          </div>

          {selected ? (
            <DetailPanel
              wp={selected}
              total={total}
              isLatest={selected.index === total}
              panelRef={panelRef}
              onClose={closeFromPanel}
              onKeyDown={onPanelKeyDown}
              className="mt-3"
            />
          ) : total > 0 ? (
            <p className="text-xs text-center mt-3 mb-0" style={{ color: 'var(--color-app-text-dim)' }}>
              Select a waypoint to see its focus time and reflection.
            </p>
          ) : null}
        </>
      ) : (
        <>
          <ol className="m-0 p-0 list-none">
            {/* Base Camp */}
            <li className="relative pl-12 pb-5">
              <span className="absolute left-0 top-0"><TrailNode kind="camp" /></span>
              <span aria-hidden="true" className="absolute top-[34px] bottom-0"
                style={{ left: NODE_SIZE / 2 - 1, borderLeft: `2px ${total > 0 ? 'solid' : 'dashed'} ${total > 0 ? 'var(--color-app-gold)' : 'var(--color-app-text-dim)'}` }} />
              <CampCaption />
            </li>

            {waypoints.map(wp => {
              const isLatest = wp.index === total;
              const isSelected = wp.index === selectedIndex;
              return (
                <li key={wp.mission.id} className="relative pl-12 pb-5">
                  <span className="absolute left-0 top-0"><TrailNode kind={isLatest ? 'latest' : 'done'} label={wp.index} selected={isSelected} /></span>
                  <span aria-hidden="true" className="absolute top-[34px] bottom-0"
                    style={{ left: NODE_SIZE / 2 - 1, borderLeft: `2px ${isLatest ? 'dashed' : 'solid'} ${isLatest ? 'var(--color-app-text-dim)' : 'var(--color-app-gold)'}` }} />
                  <button
                    type="button"
                    ref={registerButton(wp.index)}
                    onClick={() => select(wp.index)}
                    aria-expanded={isSelected}
                    aria-controls={isSelected ? 'expedition-detail' : undefined}
                    aria-label={waypointAriaLabel(wp, isLatest)}
                    className="block w-full p-0 rounded-lg bg-transparent border-none cursor-pointer text-left"
                  >
                    <WaypointCaption wp={wp} selected={isSelected} />
                  </button>
                  {isSelected && selected && (
                    <DetailPanel
                      wp={selected}
                      total={total}
                      isLatest={isLatest}
                      panelRef={panelRef}
                      onClose={closeFromPanel}
                      onKeyDown={onPanelKeyDown}
                      className="mt-2"
                    />
                  )}
                </li>
              );
            })}

            {/* Next waypoint */}
            <li className="relative pl-12">
              <span className="absolute left-0 top-0"><TrailNode kind="next" /></span>
              <Link to="/mission" className="block no-underline rounded-lg"
                aria-label={`${total === 0 ? 'First' : 'Next'} waypoint: plan a mission`}>
                <NextCaption first={total === 0} />
              </Link>
            </li>
          </ol>

          {total === 0 && <BaseCampNotice className="mt-5" />}
        </>
      )}
    </section>
  );
}
