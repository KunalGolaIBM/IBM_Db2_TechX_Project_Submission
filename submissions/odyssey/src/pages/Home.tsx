import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { taskService } from '../services/taskService';
import { missionService } from '../services/missionService';
import { interpretCapture } from '../services/aiService';
import { useMissionTimer } from '../hooks/useMissionTimer';
import { useVoiceCapture } from '../hooks/useVoiceCapture';
import { composeDictation, type VoiceResult } from '../lib/voiceCapture';
import { formatDuration } from '../components/FocusTimer';
import type {
  CaptureContext,
  AIInterpretation,
  AIItem,
  AIItemCategory,
  EnergyLevel,
  PlanHorizon,
} from '../lib/odysseyTypes';
import type { Mission, Task, TaskPriority } from '../types/database';

// ─── Colour maps ──────────────────────────────────────────────────────────────

const PRIORITY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  urgent: { bg: 'color-mix(in srgb, var(--color-app-danger) 12%, transparent)',  text: 'var(--color-status-urgent)', border: 'color-mix(in srgb, var(--color-app-danger) 35%, transparent)'  },
  high:   { bg: 'color-mix(in srgb, var(--color-app-warning) 10%, transparent)',  text: 'var(--color-app-gold)', border: 'color-mix(in srgb, var(--color-app-warning) 30%, transparent)'  },
  medium: { bg: 'color-mix(in srgb, var(--color-app-mission) 10%, transparent)',  text: 'var(--color-app-mission)', border: 'color-mix(in srgb, var(--color-app-mission) 25%, transparent)' },
  low:    { bg: 'color-mix(in srgb, var(--color-status-low) 10%, transparent)', text: 'var(--color-status-low)', border: 'color-mix(in srgb, var(--color-status-low) 20%, transparent)' },
};

const CATEGORY_META: Record<AIItemCategory, { label: string; color: string; bg: string; border: string }> = {
  deadline: { label: 'Deadline',      color: 'var(--color-status-urgent)', bg: 'color-mix(in srgb, var(--color-app-danger) 8%, transparent)',    border: 'color-mix(in srgb, var(--color-app-danger) 22%, transparent)'   },
  upcoming: { label: 'Upcoming',      color: 'var(--color-app-gold)', bg: 'color-mix(in srgb, var(--color-app-warning) 7%, transparent)',   border: 'color-mix(in srgb, var(--color-app-warning) 20%, transparent)'   },
  task:     { label: 'Task',          color: 'var(--color-app-mission)', bg: 'color-mix(in srgb, var(--color-app-mission) 7%, transparent)',   border: 'color-mix(in srgb, var(--color-app-mission) 20%, transparent)'   },
  goal:     { label: 'Ongoing goal',  color: 'var(--color-status-low)', bg: 'color-mix(in srgb, var(--color-status-low) 7%, transparent)', border: 'color-mix(in srgb, var(--color-status-low) 18%, transparent)' },
};

// ─── Voice level indicator ────────────────────────────────────────────────────

const METER_WEIGHTS = [0.55, 0.85, 1, 0.85, 0.55];

/** Bars that follow the microphone level, or a gentle pulse when the browser gives no level. */
function VoiceMeter({ level, active }: { level: number | null; active: boolean }) {
  return (
    <span
      aria-hidden="true"
      data-testid="voice-meter"
      data-level={level === null ? 'pulse' : level.toFixed(2)}
      className="flex items-end gap-0.5 h-5"
    >
      {METER_WEIGHTS.map((w, i) => (
        <span
          key={i}
          className={level === null && active ? 'animate-pulse motion-reduce:animate-none' : ''}
          style={{
            width:           3,
            borderRadius:    2,
            backgroundColor: 'var(--color-app-mission)',
            height:          level === null ? 8 + Math.round(w * 8) : 4 + Math.round(level * w * 16),
            transition:      'height 80ms linear',
            animationDelay:  `${i * 90}ms`,
          }}
        />
      ))}
    </span>
  );
}

// ─── Capture form ─────────────────────────────────────────────────────────────

interface CaptureFormProps {
  onInterpret: (ctx: CaptureContext) => void;
  interpreting: boolean;
}

function CaptureForm({ onInterpret, interpreting }: CaptureFormProps) {
  const [rawInput,          setRawInput]          = useState('');
  const [availableHours,    setAvailableHours]     = useState(4);
  const [energy,            setEnergy]             = useState<EnergyLevel>('medium');
  const [consistencyInput,  setConsistencyInput]   = useState('');
  const [consistencyGoals,  setConsistencyGoals]   = useState<string[]>([]);
  const [horizon,           setHorizon]            = useState<PlanHorizon>('today');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // ── Voice dictation ────────────────────────────────────────────────────────
  // The logic lives in src/lib/voiceCapture.ts. While recording, the box shows what was there plus what has
  // been said so far, and it is read-only; Finish puts the lines into the box for editing, Cancel drops them.
  const [voiceNotice, setVoiceNotice] = useState<string | null>(null);

  const handleVoiceResult = useCallback((result: VoiceResult) => {
    if (result.kind !== 'finished' || result.segments.length === 0) return;
    setRawInput(prev => composeDictation(prev, result.segments));
    setVoiceNotice('Dictation added. Review and edit it before you send.');
    setTimeout(() => {
      const el = textareaRef.current;
      if (!el) return;
      el.focus();
      el.setSelectionRange(el.value.length, el.value.length);
    }, 0);
  }, []);

  const voice = useVoiceCapture(handleVoiceResult);
  const recording = voice.phase !== 'idle';
  const shownText = recording ? composeDictation(rawInput, voice.segments) : rawInput;
  const voiceHint = !voice.supported
    ? "Voice input isn't available in this browser. Type your tasks above."
    : voiceNotice && !recording && !voice.error ? voiceNotice : null;

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [shownText]);

  const autoResize = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setRawInput(e.target.value);
    setVoiceNotice(null);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  };

  const addConsistencyGoal = () => {
    const trimmed = consistencyInput.trim();
    if (trimmed && !consistencyGoals.includes(trimmed)) {
      setConsistencyGoals(prev => [...prev, trimmed]);
      setConsistencyInput('');
    }
  };

  const removeGoal = (g: string) =>
    setConsistencyGoals(prev => prev.filter(x => x !== g));

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      submit();
    }
  };

  const submit = () => {
    if (recording || !rawInput.trim()) return;
    onInterpret({
      rawInput:         rawInput.trim(),
      availableHours,
      energy,
      consistencyGoals,
      horizon,
      capturedAt:       new Date().toISOString(),
    });
  };

  const ENERGY_OPTIONS: { value: EnergyLevel; label: string; color: string }[] = [
    { value: 'low',    label: 'Low',    color: 'var(--color-status-low)' },
    { value: 'medium', label: 'Medium', color: 'var(--color-app-mission)' },
    { value: 'high',   label: 'High',   color: 'var(--color-app-success)' },
  ];

  const HORIZON_OPTIONS: { value: PlanHorizon; label: string }[] = [
    { value: 'today',     label: 'Today' },
    { value: 'this_week', label: 'This week' },
  ];

  return (
    <div
      className="rounded-xl overflow-hidden"
      onKeyDown={e => { if (recording && e.key === 'Escape') { e.preventDefault(); voice.cancel(); } }}
      style={{
        background:  'rgba(8, 19, 33, 0.85)',
        border:      recording ? '1px solid color-mix(in srgb, var(--color-app-mission) 70%, transparent)' : '1px solid rgba(30, 60, 100, 0.45)',
        boxShadow:   recording ? '0 0 16px -2px color-mix(in srgb, var(--color-app-mission) 30%, transparent)' : '0 2px 24px -4px rgba(3, 6, 13, 0.5)',
        transition:  'border-color 0.3s ease, box-shadow 0.3s ease',
      }}
    >
      {/* Brain dump */}
      <div className="relative">
        <textarea
          ref={textareaRef}
          value={shownText}
          onChange={autoResize}
          onKeyDown={handleKeyDown}
          readOnly={recording}
          aria-describedby={voiceHint ? 'capture-voice-hint' : undefined}
          placeholder="What's on your mind? Dump it all here — assignments, deadlines, goals, anything…"
          rows={4}
          className="w-full bg-transparent resize-none pl-5 pr-14 pt-5 pb-3 text-base leading-relaxed focus:outline-none"
          style={{
            color:       'var(--color-app-text)',
            caretColor:  'var(--color-app-mission)',
            fontFamily:  'var(--font-sans)',
            minHeight:   '5.5rem',
          }}
          autoFocus
          disabled={interpreting}
        />

        {/* Microphone button inside textarea container: starts voice input, and finishes it while recording */}
        <div className="absolute top-4 right-4">
          <button
            type="button"
            onClick={recording ? voice.finish : voice.start}
            disabled={interpreting || !voice.supported || voice.phase === 'stopping'}
            aria-pressed={recording}
            aria-label={!voice.supported ? 'Voice input is not available in this browser' : recording ? 'Finish voice input' : 'Start voice input'}
            title={!voice.supported ? 'Voice input is not available in this browser' : recording ? 'Finish and keep what you said' : 'Dictate with voice'}
            className="p-2 rounded-lg cursor-pointer border transition-all flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              backgroundColor: recording ? 'var(--color-app-mission)' : 'rgba(30, 60, 100, 0.3)',
              borderColor:     recording ? 'var(--color-app-mission)' : 'rgba(30, 60, 100, 0.5)',
              color:           recording ? '#fff' : 'var(--color-app-text-muted)',
              boxShadow:       recording ? '0 0 10px color-mix(in srgb, var(--color-app-mission) 50%, transparent)' : 'none',
            }}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 10v1a7 7 0 01-14 0v-1M12 18.5V23M8 23h8" />
            </svg>
          </button>
        </div>
      </div>

      {/* Recording bar: level, what is being heard, Cancel and Finish */}
      {recording && (
        <div
          role="group"
          aria-label="Voice recording"
          data-testid="voice-bar"
          className="mx-5 mb-3 px-3 py-2 rounded-lg flex flex-wrap items-center gap-x-3 gap-y-2"
          style={{
            background: 'color-mix(in srgb, var(--color-app-mission) 10%, transparent)',
            border:     '1px solid color-mix(in srgb, var(--color-app-mission) 35%, transparent)',
          }}
        >
          <VoiceMeter level={voice.level} active={voice.phase === 'recording'} />
          <span role="status" aria-live="polite" className="text-xs font-medium" style={{ color: 'var(--color-app-mission)' }}>
            {voice.phase === 'starting'
              ? 'Waiting for the microphone…'
              : voice.phase === 'stopping'
                ? 'Finishing…'
                : 'Listening. Pause between tasks to start a new line.'}
          </span>
          {voice.interim && (
            <span aria-hidden="true" data-testid="voice-interim" className="text-xs italic min-w-0 basis-full sm:basis-0 sm:flex-1 line-clamp-2 sm:line-clamp-1" style={{ color: 'var(--color-app-text-dim)' }}>
              {voice.interim}
            </span>
          )}
          <div className="flex gap-2 ml-auto">
            <button
              type="button"
              onClick={voice.cancel}
              className="px-3 py-1 rounded-lg text-xs font-semibold cursor-pointer border"
              style={{ backgroundColor: 'transparent', color: 'var(--color-app-text-muted)', borderColor: 'rgba(30,60,100,0.5)' }}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={voice.finish}
              disabled={voice.phase === 'stopping'}
              className="px-3 py-1 rounded-lg text-xs font-semibold cursor-pointer border-none disabled:opacity-50"
              style={{ backgroundColor: 'var(--color-app-mission)', color: '#fff' }}
            >
              Finish
            </button>
          </div>
        </div>
      )}

      {/* Voice input error: what happened and what to do */}
      {voice.error && (
        <div
          role="alert"
          data-testid="voice-error"
          className="mx-5 mb-2 px-3 py-2 rounded-lg text-xs flex items-start justify-between gap-3"
          style={{ background: 'color-mix(in srgb, var(--color-app-danger) 12%, transparent)', border: '1px solid color-mix(in srgb, var(--color-app-danger) 25%, transparent)', color: 'var(--color-status-urgent)' }}
        >
          <span>
            <span className="font-semibold block">{voice.error.message}</span>
            <span className="block mt-0.5" style={{ color: 'var(--color-app-text-muted)' }}>{voice.error.hint}</span>
          </span>
          <button
            type="button"
            onClick={voice.dismissError}
            aria-label="Dismiss voice input message"
            className="text-sm bg-transparent border-none cursor-pointer leading-none"
            style={{ color: 'var(--color-status-urgent)' }}
          >×</button>
        </div>
      )}

      {/* Helper text: no support, or a reminder to review what was dictated */}
      {voiceHint && (
        <p id="capture-voice-hint" role="status" className="mx-5 mb-2 text-xs" style={{ color: 'var(--color-app-text-dim)' }}>
          {voiceHint}
        </p>
      )}

      {/* Structured context */}
      <div
        className="px-5 py-4 space-y-4"
        style={{ borderTop: '1px solid rgba(30, 60, 100, 0.28)' }}
      >
        {/* Row 1: hours + energy + horizon */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">

          {/* Available hours */}
          <div>
            <label className="block text-[0.7rem] font-semibold uppercase tracking-widest mb-2"
              style={{ color: 'var(--color-app-text-dim)' }}>
              Available today
            </label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={0.5} max={12} step={0.5}
                value={availableHours}
                onChange={e => setAvailableHours(parseFloat(e.target.value))}
                disabled={interpreting}
                className="flex-1 accent-(--color-app-mission) cursor-pointer"
                style={{ height: '4px' }}
              />
              <span
                className="text-sm font-medium tabular-nums flex-shrink-0 w-16 text-right"
                style={{ color: 'var(--color-app-text)' }}
              >
                {availableHours === 1 ? '1 hr' : `${availableHours} hrs`}
              </span>
            </div>
          </div>

          {/* Energy */}
          <div>
            <label className="block text-[0.7rem] font-semibold uppercase tracking-widest mb-2"
              style={{ color: 'var(--color-app-text-dim)' }}>
              Energy
            </label>
            <div className="flex gap-2">
              {ENERGY_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setEnergy(opt.value)}
                  disabled={interpreting}
                  className="flex-1 py-1.5 rounded-lg text-xs font-semibold cursor-pointer border transition-all"
                  style={{
                    backgroundColor: energy === opt.value ? `color-mix(in srgb, ${opt.color} 20%, transparent)` : 'transparent',
                    color:           energy === opt.value ? opt.color : 'var(--color-app-text-dim)',
                    borderColor:     energy === opt.value ? `color-mix(in srgb, ${opt.color} 60%, transparent)` : 'rgba(30,60,100,0.3)',
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Horizon */}
          <div>
            <label className="block text-[0.7rem] font-semibold uppercase tracking-widest mb-2"
              style={{ color: 'var(--color-app-text-dim)' }}>
              Planning horizon
            </label>
            <div className="flex gap-2">
              {HORIZON_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setHorizon(opt.value)}
                  disabled={interpreting}
                  className="flex-1 py-1.5 rounded-lg text-xs font-semibold cursor-pointer border transition-all"
                  style={{
                    backgroundColor: horizon === opt.value ? 'color-mix(in srgb, var(--color-app-mission) 12%, transparent)' : 'transparent',
                    color:           horizon === opt.value ? 'var(--color-app-mission)' : 'var(--color-app-text-dim)',
                    borderColor:     horizon === opt.value ? 'color-mix(in srgb, var(--color-app-mission) 40%, transparent)' : 'rgba(30,60,100,0.3)',
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Row 2: consistency goals */}
        <div>
          <label className="block text-[0.7rem] font-semibold uppercase tracking-widest mb-2"
            style={{ color: 'var(--color-app-text-dim)' }}>
            Consistency goals <span style={{ color: 'var(--color-app-text-dim)', fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>— what do you want to keep doing regularly?</span>
          </label>

          <div className="flex gap-2 mb-2">
            <input
              type="text"
              value={consistencyInput}
              onChange={e => setConsistencyInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addConsistencyGoal(); } }}
              placeholder="e.g. Practice Java problems every day"
              disabled={interpreting}
              className="app-input flex-1 text-sm"
            />
            <button
              type="button"
              onClick={addConsistencyGoal}
              disabled={interpreting || !consistencyInput.trim()}
              className="px-3 py-1.5 rounded-lg text-sm cursor-pointer border-none disabled:opacity-30"
              style={{ backgroundColor: 'color-mix(in srgb, var(--color-app-mission) 15%, transparent)', color: 'var(--color-app-mission)' }}
            >
              Add
            </button>
          </div>

          {consistencyGoals.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {consistencyGoals.map((g, i) => (
                <span
                  key={i}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs"
                  style={{ background: 'color-mix(in srgb, var(--color-status-low) 12%, transparent)', border: '1px solid color-mix(in srgb, var(--color-status-low) 25%, transparent)', color: 'var(--color-status-low)' }}
                >
                  {g}
                  <button
                    type="button"
                    onClick={() => removeGoal(g)}
                    className="cursor-pointer bg-transparent border-none p-0 leading-none"
                    style={{ color: 'var(--color-status-low)' }}
                  >×</button>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Footer: hint + submit */}
      <div
        className="flex items-center justify-between px-5 py-3"
        style={{ borderTop: '1px solid rgba(30, 60, 100, 0.28)' }}
      >
        <span className="text-xs" style={{ color: 'var(--color-app-text-dim)' }}>
          <kbd
            className="px-1.5 py-0.5 rounded text-[0.6rem] font-mono mr-1"
            style={{ background: 'rgba(30,60,100,0.3)', color: 'var(--color-app-text-dim)', border: '1px solid rgba(30,60,100,0.4)' }}
          >⌘↵</kbd>
          to interpret
        </span>
        <button
          type="button"
          onClick={submit}
          disabled={!rawInput.trim() || interpreting || recording}
          title={recording ? 'Finish voice input first' : undefined}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold cursor-pointer border-none disabled:opacity-30 transition-all"
          style={{ backgroundColor: 'var(--color-app-mission)', color: '#fff' }}
        >
          {interpreting ? (
            <>
              <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Analysing…
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
              Find My Next Move
            </>
          )}
        </button>
      </div>
    </div>
  );
}

// ─── Interpretation review panel ──────────────────────────────────────────────

interface ReviewPanelProps {
  ctx:           CaptureContext;
  interpretation: AIInterpretation;
  onReset:       () => void;
  onConfirm:     (items: AIItem[]) => Promise<void>;
}

function ReviewPanel({ ctx, interpretation, onReset, onConfirm }: ReviewPanelProps) {
  const [items,     setItems]     = useState<AIItem[]>(interpretation.items);
  const [saving,    setSaving]    = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const updateText = (i: number, text: string) =>
    setItems(prev => prev.map((it, idx) => idx === i ? { ...it, text } : it));
  const removeItem = (i: number) =>
    setItems(prev => prev.filter((_, idx) => idx !== i));

  const handleConfirm = async () => {
    if (items.length === 0) return;
    setSaving(true);
    setSaveError(null);
    try {
      await onConfirm(items);
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : 'Something went wrong');
      setSaving(false);
    }
  };

  // Group for display
  const deadlines   = items.filter(i => i.category === 'deadline');
  const upcoming    = items.filter(i => i.category === 'upcoming');
  const tasks       = items.filter(i => i.category === 'task');
  const goals       = items.filter(i => i.category === 'goal' || i.isConsistency);

  const sections: Array<{ label: string; items: AIItem[] }> = [
    { label: 'Deadlines',    items: deadlines },
    { label: 'Upcoming',     items: upcoming  },
    { label: 'Tasks',        items: tasks     },
    { label: 'Consistency',  items: goals     },
  ].filter(s => s.items.length > 0);

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        background:  'rgba(8, 19, 33, 0.9)',
        border:      '1px solid rgba(30, 60, 100, 0.5)',
        boxShadow:   '0 4px 32px -8px rgba(3, 6, 13, 0.6)',
      }}
    >
      {/* Header */}
      <div
        className="px-5 py-4 flex items-center justify-between gap-3"
        style={{ borderBottom: '1px solid rgba(30, 60, 100, 0.3)' }}
      >
        <div className="flex items-center gap-2.5">
          <div
            className="w-2 h-2 rounded-full flex-shrink-0"
            style={{ backgroundColor: 'var(--color-app-mission)', boxShadow: '0 0 6px color-mix(in srgb, var(--color-app-mission) 60%, transparent)' }}
          />
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em]"
              style={{ color: 'var(--color-app-mission)' }}>
              Here's what I understand
            </p>
            <p className="text-xs mt-0.5" style={{ color: 'var(--color-app-text-dim)' }}>
              {items.length} item{items.length !== 1 ? 's' : ''} · {ctx.availableHours}h available · {ctx.energy} energy
              {!interpretation.aiGenerated && (
                <span className="ml-1.5 opacity-60">(offline mode)</span>
              )}
            </p>
          </div>
        </div>
        <button
          onClick={onReset}
          className="text-xs cursor-pointer border-none bg-transparent"
          style={{ color: 'var(--color-app-text-dim)' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-app-text-muted)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-app-text-dim)')}
        >
          Start over
        </button>
      </div>

      {/* Original input */}
      <div className="px-5 pt-3 pb-1">
        <p className="text-xs italic leading-relaxed" style={{ color: 'var(--color-app-text-dim)' }}>
          "{ctx.rawInput.length > 140 ? ctx.rawInput.slice(0, 140) + '…' : ctx.rawInput}"
        </p>
      </div>

      {/* Grouped items */}
      <div className="px-5 py-3 space-y-4">
        {sections.length === 0 ? (
          <p className="text-sm" style={{ color: 'var(--color-app-text-muted)' }}>
            Couldn't extract anything — try adding more detail.
          </p>
        ) : sections.map(section => (
          <div key={section.label}>
            <p className="text-[0.65rem] font-bold uppercase tracking-[0.2em] mb-2"
              style={{ color: 'var(--color-app-text-dim)' }}>
              {section.label}
            </p>
            <div className="space-y-1.5">
              {section.items.map(item => {
                const globalIdx = items.indexOf(item);
                const cm = CATEGORY_META[item.category];
                const pc = PRIORITY_COLORS[item.priority];
                return (
                  <ReviewItemRow
                    key={globalIdx}
                    item={item}
                    cm={cm}
                    pc={pc}
                    onEdit={text => updateText(globalIdx, text)}
                    onRemove={() => removeItem(globalIdx)}
                  />
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Error */}
      {saveError && (
        <div className="mx-5 mb-3 px-3 py-2 rounded-lg text-xs"
          style={{ background: 'color-mix(in srgb, var(--color-app-danger) 12%, transparent)', border: '1px solid color-mix(in srgb, var(--color-app-danger) 25%, transparent)', color: 'var(--color-status-urgent)' }}>
          {saveError}
        </div>
      )}

      {/* CTA */}
      {items.length > 0 && (
        <div
          className="px-5 py-4 flex items-center justify-between gap-3"
          style={{ borderTop: '1px solid rgba(30, 60, 100, 0.3)' }}
        >
          <p className="text-xs" style={{ color: 'var(--color-app-text-dim)' }}>
            Looks right? Save these and Odyssey will pick your first mission.
          </p>
          <button
            onClick={handleConfirm}
            disabled={saving}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold cursor-pointer border-none disabled:opacity-50 transition-all"
            style={{ backgroundColor: 'var(--color-app-mission)', color: '#fff' }}
          >
            {saving ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Saving…
              </>
            ) : (
              <>
                Save &amp; Plan My Mission
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}

function ReviewItemRow({
  item, cm, pc, onEdit, onRemove,
}: {
  item:     AIItem;
  cm:       { color: string; bg: string; border: string };
  pc:       { bg: string; text: string; border: string };
  onEdit:   (text: string) => void;
  onRemove: () => void;
}) {
  const [editing,   setEditing]   = useState(false);
  const [editValue, setEditValue] = useState(item.text);

  const commit = () => {
    setEditing(false);
    if (editValue.trim() && editValue.trim() !== item.text) onEdit(editValue.trim());
    else setEditValue(item.text);
  };

  return (
    <div
      className="flex items-start gap-3 px-3 py-2.5 rounded-lg group/row"
      style={{ background: cm.bg, border: `1px solid ${cm.border}` }}
    >
      <div className="flex-1 min-w-0">
        {editing ? (
          <input
            autoFocus
            value={editValue}
            onChange={e => setEditValue(e.target.value)}
            onBlur={commit}
            onKeyDown={e => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') { setEditing(false); setEditValue(item.text); } }}
            className="w-full bg-transparent text-sm focus:outline-none border-b"
            style={{ color: 'var(--color-app-text)', borderColor: 'var(--color-app-mission)' }}
          />
        ) : (
          <button
            onClick={() => setEditing(true)}
            className="text-sm text-left w-full bg-transparent border-none cursor-text p-0 font-medium"
            style={{ color: 'var(--color-app-text)' }}
          >
            {item.text}
          </button>
        )}

        <div className="flex flex-wrap items-center gap-2 mt-1">
          {item.deadlineLabel && (
            <span className="text-xs flex items-center gap-1" style={{ color: cm.color }}>
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              {item.deadlineLabel}
            </span>
          )}
          <span
            className="text-[0.6rem] font-bold tracking-wider uppercase px-1.5 py-0.5 rounded"
            style={{ background: pc.bg, color: pc.text, border: `1px solid ${pc.border}` }}
          >
            {item.priority}
          </span>
          {item.isConsistency && (
            <span className="text-[0.6rem] font-bold tracking-wider uppercase px-1.5 py-0.5 rounded"
              style={{ background: 'color-mix(in srgb, var(--color-status-low) 10%, transparent)', color: 'var(--color-status-low)', border: '1px solid color-mix(in srgb, var(--color-status-low) 25%, transparent)' }}>
              daily
            </span>
          )}
          {item.ambiguity && (
            <span className="text-[0.6rem] italic" style={{ color: 'var(--color-app-text-dim)' }}>
              ⚠ {item.ambiguity}
            </span>
          )}
        </div>
      </div>

      <button
        onClick={onRemove}
        className="p-1 rounded opacity-0 group-hover/row:opacity-100 transition-opacity cursor-pointer border-none flex-shrink-0"
        style={{ backgroundColor: 'rgba(0,0,0,0.3)', color: 'var(--color-app-text-dim)' }}
        onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-status-urgent)')}
        onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-app-text-dim)')}
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

// ─── Task row (existing task list — unchanged) ────────────────────────────────

function TaskRow({
  task, onToggle, onDelete, onLaunchMission,
}: {
  task:            Task;
  onToggle:        (t: Task) => void;
  onDelete:        (id: string) => void;
  onLaunchMission: (t: Task) => void;
}) {
  const isCompleted = task.status === 'completed';
  const pc = PRIORITY_COLORS[task.priority] ?? PRIORITY_COLORS.medium;

  return (
    <div
      className={`rounded-xl p-4 flex items-start justify-between gap-4 group transition-all${isCompleted ? ' app-dimmed' : ''}`}
      style={{ backgroundColor: 'var(--color-app-surface)', border: '1px solid var(--color-app-border)' }}
    >
      <div className="flex items-start gap-3 flex-1 min-w-0">
        <button
          onClick={() => onToggle(task)}
          className="mt-0.5 w-5 h-5 rounded flex items-center justify-center border transition-all cursor-pointer flex-shrink-0"
          style={isCompleted
            ? { backgroundColor: 'var(--color-app-mission)', borderColor: 'var(--color-app-mission)' }
            : { backgroundColor: 'transparent', borderColor: 'var(--color-app-border)' }}
        >
          {isCompleted && (
            <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          )}
        </button>

        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-0.5">
            <span
              className="text-sm font-medium truncate"
              style={{ color: isCompleted ? 'var(--color-app-text-dim)' : 'var(--color-app-text)', textDecoration: isCompleted ? 'line-through' : 'none' }}
            >
              {task.title}
            </span>
            <span
              className="text-[0.6rem] font-bold tracking-wider uppercase px-1.5 py-0.5 rounded"
              style={{ backgroundColor: pc.bg, color: pc.text, border: `1px solid ${pc.border}` }}
            >
              {task.priority}
            </span>
          </div>
          {task.description && (
            <p className="text-xs line-clamp-1 mt-0.5" style={{ color: 'var(--color-app-text-muted)' }}>{task.description}</p>
          )}
          <div className="flex flex-wrap items-center gap-3 mt-1.5">
            {task.deadline && (
              <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--color-app-text-dim)' }}>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                {new Date(task.deadline).toLocaleDateString()}
              </span>
            )}
            {task.estimated_minutes && (
              <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--color-app-text-dim)' }}>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <circle cx="12" cy="12" r="10" /><path strokeLinecap="round" d="M12 6v6l4 2" />
                </svg>
                {task.estimated_minutes}m
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-1 flex-shrink-0">
        {!isCompleted && (
          <button
            onClick={() => onLaunchMission(task)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer border-none"
            style={{ backgroundColor: 'var(--color-app-mission-light)', color: 'var(--color-app-mission)', border: '1px solid color-mix(in srgb, var(--color-app-mission) 20%, transparent)' }}
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
            </svg>
            Start Mission
          </button>
        )}
        <button
          onClick={() => onDelete(task.id)}
          className="p-1.5 rounded-lg transition-all cursor-pointer border-none opacity-0 group-hover:opacity-100"
          style={{ color: 'var(--color-app-text-dim)' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-status-urgent)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-app-text-dim)')}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
          </svg>
        </button>
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

type ScreenState = 'capture' | 'interpreting' | 'review';

export default function Home() {
  const { user }  = useAuth();
  const navigate  = useNavigate();

  const [tasks,    setTasks]    = useState<Task[]>([]);
  const [missions, setMissions] = useState<Mission[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState<string | null>(null);

  const [screen,          setScreen]          = useState<ScreenState>('capture');
  const [captureCtx,      setCaptureCtx]      = useState<CaptureContext | null>(null);
  const [interpretation,  setInterpretation]  = useState<AIInterpretation | null>(null);
  const [captureExpanded, setCaptureExpanded] = useState(true);

  // Structured task form (for manual add)
  const [isFormOpen,       setIsFormOpen]       = useState(false);
  const [title,            setTitle]            = useState('');
  const [description,      setDescription]      = useState('');
  const [deadline,         setDeadline]         = useState('');
  const [priority,         setPriority]         = useState<TaskPriority>('medium');
  const [estimatedMinutes, setEstimatedMinutes] = useState('');
  const [isCreating,       setIsCreating]       = useState(false);
  const [formError,        setFormError]        = useState<string | null>(null);

  useEffect(() => { loadTasks(); }, []);

  useEffect(() => { loadMissions(); }, [user?.id]);

  useEffect(() => {
    if (!loading && tasks.length > 0 && screen === 'capture') {
      setCaptureExpanded(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  const loadTasks = async () => {
    setLoading(true);
    setError(null);
    try {
      setTasks(await taskService.getTasks());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load tasks');
    } finally {
      setLoading(false);
    }
  };

  const loadMissions = async () => {
    try {
      setMissions(await missionService.getMissions());
    } catch (err) {
      console.warn('Failed to load missions for resume prompt:', err);
    }
  };

  // ── Capture flow ──────────────────────────────────────────────────────────

  const handleInterpret = async (ctx: CaptureContext) => {
    setCaptureCtx(ctx);
    setScreen('interpreting');
    setCaptureExpanded(true);
    const result = await interpretCapture(ctx);
    setInterpretation(result);
    setScreen('review');
  };

  const handleReset = () => {
    setScreen('capture');
    setCaptureCtx(null);
    setInterpretation(null);
  };

  const handleConfirmAndPlan = async (items: AIItem[]) => {
    if (!captureCtx) return;
    // Save tasks
    const created = await Promise.all(
      items.map(item =>
        taskService.createTask({
          title:    item.text,
          priority: item.priority as TaskPriority,
          deadline: item.isoDeadline ?? null,
          status:   'todo',
        })
      )
    );
    setTasks(prev => [...created, ...prev]);
    setScreen('capture');
    setCaptureExpanded(false);
    // Navigate to Plan with full context
    navigate('/mission', {
      state: {
        captureContext:  { ...captureCtx },
        interpretation:  { items, aiGenerated: interpretation?.aiGenerated ?? false },
      },
    });
  };

  // ── Manual task form ──────────────────────────────────────────────────────

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    setIsCreating(true);
    setFormError(null);
    try {
      const newTask = await taskService.createTask({
        title:             title.trim(),
        description:       description.trim() || undefined,
        deadline:          deadline ? new Date(deadline).toISOString() : undefined,
        priority,
        estimated_minutes: estimatedMinutes ? parseInt(estimatedMinutes, 10) : undefined,
      });
      setTasks(prev => [newTask, ...prev]);
      setTitle(''); setDescription(''); setDeadline('');
      setPriority('medium'); setEstimatedMinutes('');
      setIsFormOpen(false);
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Failed to create task');
    } finally {
      setIsCreating(false);
    }
  };

  const handleToggleComplete = async (task: Task) => {
    try {
      const updated = task.status === 'completed'
        ? await taskService.updateTask(task.id, { status: 'todo', completed_at: null })
        : await taskService.completeTask(task.id);
      setTasks(prev => prev.map(t => t.id === task.id ? updated : t));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to update task');
    }
  };

  const handleDeleteTask = async (id: string) => {
    if (!confirm('Delete this task?')) return;
    try {
      await taskService.deleteTask(id);
      setTasks(prev => prev.filter(t => t.id !== id));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to delete task');
    }
  };

  const handleLaunchMission = (task: Task) => {
    navigate('/mission', { state: { prefillTask: task } });
  };

  const activeTasks    = tasks.filter(t => t.status !== 'completed' && t.status !== 'archived');
  const completedTasks = tasks.filter(t => t.status === 'completed');
  const resumableMission = missions.find(m => m.status === 'active' || m.status === 'paused') ?? null;
  const missionTimer = useMissionTimer(resumableMission, updatedMission => {
    setMissions(previous => previous.map(m => m.id === updatedMission.id ? updatedMission : m));
  });
  const missionDuration = (resumableMission?.planned_minutes ?? 25) * 60;
  const missionProgress = Math.min(missionTimer.elapsed / missionDuration, 1);
  const displayName    = user?.email?.split('@')[0] ?? null;

  return (
    <div className="max-w-3xl mx-auto">

      {/* Header */}
      <div className="mb-7">
        <p className="text-xs font-semibold tracking-[0.18em] uppercase mb-2"
          style={{ color: 'var(--color-app-mission)' }}>
          Step 1 — Capture
        </p>
        <h1 className="font-display text-3xl leading-tight" style={{ color: 'var(--color-app-text)' }}>
          {displayName ? `What's on your mind, ${displayName}?` : "What's on your mind?"}
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--color-app-text-muted)' }}>
          Dump everything here — tasks, deadlines, goals, anything weighing on you. Odyssey will sort it out and tell you what to do next.
        </p>
      </div>

      {resumableMission && (
        <section
          className="rounded-xl p-5 mb-8"
          style={{
            background: 'linear-gradient(135deg, rgba(18,32,58,0.92) 0%, rgba(8,19,33,0.96) 100%)',
            border: '1px solid color-mix(in srgb, var(--color-app-mission) 38%, transparent)',
            boxShadow: '0 8px 28px -8px color-mix(in srgb, var(--color-app-mission) 16%, transparent)',
          }}
        >
          <div className="flex items-center gap-2 mb-3">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: missionTimer.running ? 'var(--color-app-success)' : 'var(--color-app-mission)' }} />
            <p className="text-xs font-bold uppercase tracking-[0.16em]" style={{ color: 'var(--color-app-mission)' }}>
              Pick up where you left off
            </p>
          </div>
          <h2 className="font-display text-xl mb-1" style={{ color: 'var(--color-app-text)' }}>{resumableMission.title}</h2>
          <div className="flex items-center justify-between gap-3 mt-4 mb-2">
            <span className="text-xs font-mono" style={{ color: 'var(--color-app-text-muted)' }}>
              {formatDuration(Math.max(0, missionDuration - missionTimer.elapsed))} remaining
            </span>
            <span className="text-xs font-mono" style={{ color: 'var(--color-app-text-dim)' }}>{Math.round(missionProgress * 100)}% complete</span>
          </div>
          <div className="h-1.5 rounded-full overflow-hidden mb-4" style={{ backgroundColor: 'rgba(30,60,100,0.42)' }}>
            <div className="h-full rounded-full" style={{ width: `${Math.round(missionProgress * 100)}%`, background: 'linear-gradient(90deg, var(--color-app-mission), var(--color-ody-gold))' }} />
          </div>
          <button
            onClick={() => navigate('/execute', { state: { mission: resumableMission } })}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold cursor-pointer border-none"
            style={{ backgroundColor: 'var(--color-app-mission)', color: '#fff' }}
          >
            CONTINUE MISSION
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
          </button>
        </section>
      )}

      {/* Capture section */}
      <div className="mb-8">
        {/* Collapsed toggle when tasks exist and we're idle */}
        {tasks.length > 0 && !captureExpanded && screen === 'capture' && (
          <button
            onClick={() => setCaptureExpanded(true)}
            className="flex items-center gap-2 text-sm font-medium cursor-pointer border-none bg-transparent transition-colors mb-4"
            style={{ color: 'var(--color-app-text-dim)' }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-app-text-muted)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-app-text-dim)')}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            Capture more
          </button>
        )}

        {/* Interpreting spinner */}
        {screen === 'interpreting' && (
          <div
            className="rounded-xl px-5 py-6 flex items-center gap-3"
            style={{ background: 'rgba(8,19,33,0.85)', border: '1px solid rgba(30,60,100,0.45)' }}
          >
            <div className="w-4 h-4 border-2 rounded-full animate-spin flex-shrink-0"
              style={{ borderColor: 'var(--color-app-mission)', borderTopColor: 'transparent' }} />
            <div>
              <p className="text-sm font-medium" style={{ color: 'var(--color-app-text)' }}>
                Understanding your context…
              </p>
              <p className="text-xs mt-0.5" style={{ color: 'var(--color-app-text-dim)' }}>
                Parsing tasks, deadlines, and goals from your input.
              </p>
            </div>
          </div>
        )}

        {captureExpanded && screen === 'capture' && (
          <CaptureForm onInterpret={handleInterpret} interpreting={false} />
        )}

        {screen === 'review' && captureCtx && interpretation && (
          <ReviewPanel
            ctx={captureCtx}
            interpretation={interpretation}
            onReset={handleReset}
            onConfirm={handleConfirmAndPlan}
          />
        )}
      </div>

      {/* Task list header + add button */}
      {tasks.length > 0 && (
        <div className="flex items-center justify-between gap-4 mb-5">
          <p className="text-xs font-semibold uppercase tracking-wider"
            style={{ color: 'var(--color-app-text-dim)' }}>
            Task list
          </p>
          <button
            onClick={() => setIsFormOpen(!isFormOpen)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer border-none"
            style={{
              backgroundColor: isFormOpen ? 'color-mix(in srgb, var(--color-app-mission) 12%, transparent)' : 'transparent',
              color:           isFormOpen ? 'var(--color-app-mission)' : 'var(--color-app-text-dim)',
              border:          '1px solid ' + (isFormOpen ? 'color-mix(in srgb, var(--color-app-mission) 30%, transparent)' : 'rgba(30,60,100,0.35)'),
            }}
          >
            {isFormOpen ? 'Cancel' : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                </svg>
                Add task
              </>
            )}
          </button>
        </div>
      )}

      {/* Manual task form */}
      {isFormOpen && (
        <div className="rounded-xl p-5 mb-5"
          style={{ backgroundColor: 'var(--color-app-surface)', border: '1px solid var(--color-app-border)' }}>
          <h2 className="font-display text-base mb-4" style={{ color: 'var(--color-app-text)' }}>New Task</h2>
          {formError && (
            <div className="rounded-lg p-3 text-xs mb-4"
              style={{ backgroundColor: 'color-mix(in srgb, var(--color-app-danger) 10%, transparent)', border: '1px solid color-mix(in srgb, var(--color-app-danger) 25%, transparent)', color: 'var(--color-status-urgent)' }}>
              {formError}
            </div>
          )}
          <form onSubmit={handleCreateTask} className="space-y-3">
            <div>
              <label htmlFor="t-title" className="block text-xs font-semibold uppercase tracking-wider mb-1.5"
                style={{ color: 'var(--color-app-text-muted)' }}>
                Title <span style={{ color: 'var(--color-status-urgent)' }}>*</span>
              </label>
              <input id="t-title" type="text" required value={title} onChange={e => setTitle(e.target.value)}
                placeholder="What needs doing?" className="app-input w-full" />
            </div>
            <div>
              <label htmlFor="t-desc" className="block text-xs font-semibold uppercase tracking-wider mb-1.5"
                style={{ color: 'var(--color-app-text-muted)' }}>
                Description
              </label>
              <textarea id="t-desc" rows={2} value={description} onChange={e => setDescription(e.target.value)}
                placeholder="Optional details…" className="app-input w-full resize-none" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label htmlFor="t-priority" className="block text-xs font-semibold uppercase tracking-wider mb-1.5"
                  style={{ color: 'var(--color-app-text-muted)' }}>Priority</label>
                <select id="t-priority" value={priority} onChange={e => setPriority(e.target.value as TaskPriority)}
                  className="app-input w-full" style={{ cursor: 'pointer' }}>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="urgent">Urgent</option>
                </select>
              </div>
              <div>
                <label htmlFor="t-est" className="block text-xs font-semibold uppercase tracking-wider mb-1.5"
                  style={{ color: 'var(--color-app-text-muted)' }}>Est. Minutes</label>
                <input id="t-est" type="number" min="1" value={estimatedMinutes}
                  onChange={e => setEstimatedMinutes(e.target.value)} placeholder="e.g. 45" className="app-input w-full" />
              </div>
              <div>
                <label htmlFor="t-deadline" className="block text-xs font-semibold uppercase tracking-wider mb-1.5"
                  style={{ color: 'var(--color-app-text-muted)' }}>Deadline</label>
                <input id="t-deadline" type="date" value={deadline} onChange={e => setDeadline(e.target.value)}
                  className="app-input w-full" />
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-1">
              <button type="button" onClick={() => setIsFormOpen(false)}
                className="px-4 py-2 rounded-lg text-sm cursor-pointer border-none"
                style={{ backgroundColor: 'transparent', color: 'var(--color-app-text-muted)', border: '1px solid var(--color-app-border)' }}>
                Cancel
              </button>
              <button type="submit" disabled={isCreating || !title.trim()}
                className="px-5 py-2 rounded-lg text-sm font-medium cursor-pointer border-none disabled:opacity-50"
                style={{ backgroundColor: 'var(--color-app-mission)', color: '#fff' }}>
                {isCreating ? 'Saving…' : 'Save Task'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Task list */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20">
          <div className="w-8 h-8 border-2 rounded-full animate-spin mb-3"
            style={{ borderColor: 'var(--color-app-mission)', borderTopColor: 'transparent' }} />
          <span className="text-sm" style={{ color: 'var(--color-app-text-muted)' }}>Loading tasks…</span>
        </div>
      ) : error ? (
        <div className="rounded-xl p-5 text-center"
          style={{ backgroundColor: 'color-mix(in srgb, var(--color-app-danger) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-app-danger) 20%, transparent)' }}>
          <p className="text-sm mb-3" style={{ color: 'var(--color-status-urgent)' }}>{error}</p>
          <button onClick={loadTasks} className="px-4 py-1.5 rounded-lg text-xs font-medium cursor-pointer border-none"
            style={{ backgroundColor: 'color-mix(in srgb, var(--color-app-danger) 20%, transparent)', color: 'var(--color-status-urgent)' }}>Retry</button>
        </div>
      ) : tasks.length === 0 && screen === 'capture' ? (
        <div className="rounded-xl px-5 py-6 text-center"
          style={{ background: 'rgba(8,19,33,0.5)', border: '1px dashed rgba(30,60,100,0.4)' }}>
          <p className="text-sm mb-1" style={{ color: 'var(--color-app-text-muted)' }}>
            Start by typing what's on your mind above.
          </p>
          <p className="text-xs" style={{ color: 'var(--color-app-text-dim)' }}>
            No special format needed — just write like you'd tell a friend.
          </p>
        </div>
      ) : tasks.length === 0 ? null : (
        <>
          {activeTasks.length > 0 && (
            <div className="space-y-2 mb-8">
              {activeTasks.map(task => (
                <TaskRow key={task.id} task={task}
                  onToggle={handleToggleComplete}
                  onDelete={handleDeleteTask}
                  onLaunchMission={handleLaunchMission} />
              ))}
            </div>
          )}
          {completedTasks.length > 0 && (
            <details className="group">
              <summary className="text-xs font-semibold uppercase tracking-wider cursor-pointer mb-3 flex items-center gap-2 select-none list-none"
                style={{ color: 'var(--color-app-text-dim)' }}>
                <svg className="w-3.5 h-3.5 transition-transform group-open:rotate-90" fill="none"
                  viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                </svg>
                Completed ({completedTasks.length})
              </summary>
              <div className="space-y-2">
                {completedTasks.map(task => (
                  <TaskRow key={task.id} task={task}
                    onToggle={handleToggleComplete}
                    onDelete={handleDeleteTask}
                    onLaunchMission={handleLaunchMission} />
                ))}
              </div>
            </details>
          )}
        </>
      )}
    </div>
  );
}
