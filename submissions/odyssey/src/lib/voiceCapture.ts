/**
 * Voice capture for the Home page: a small controller around the browser's Web Speech API.
 *
 * It has no React in it, so it can be driven by a fake recognition object in tests. The page gets it through
 * `useVoiceCapture` (src/hooks/useVoiceCapture.ts).
 *
 * What it does:
 *  - keeps interim text (what the engine is still working out) apart from final text, so nothing is added twice
 *  - starts a new line when the speaker pauses, so separate thoughts do not run together
 *  - capitalises the start of a line and ends it with a full stop, and changes nothing else that was said
 *  - starts the engine again when the browser stops it early, a limited number of times in a row
 *  - turns the engine's error codes into a message and a hint a person can act on
 *  - optionally reports a microphone level, so the page can show that sound is arriving
 *
 * It never sends anything anywhere and does not touch how the text is interpreted afterwards.
 */

// ─── Minimal Web Speech API types (not all of them ship with TypeScript) ──────

interface SpeechAlternativeLike { transcript: string }
interface SpeechResultLike { isFinal: boolean; 0: SpeechAlternativeLike; length?: number }
export interface SpeechEventLike { resultIndex: number; results: ArrayLike<SpeechResultLike> }
export interface SpeechErrorEventLike { error: string }

export interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives?: number;
  onstart: (() => void) | null;
  onresult: ((event: SpeechEventLike) => void) | null;
  onerror: ((event: SpeechErrorEventLike) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

export type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

// ─── Public types ─────────────────────────────────────────────────────────────

export type VoicePhase = 'idle' | 'starting' | 'recording' | 'stopping';

export type VoiceErrorCode =
  | 'unsupported'
  | 'denied'
  | 'no-microphone'
  | 'network'
  | 'no-speech'
  | 'stalled'
  | 'language'
  | 'start-failed'
  | 'unknown';

export interface VoiceError {
  code: VoiceErrorCode;
  /** One sentence saying what happened. */
  message: string;
  /** What the person can do about it. */
  hint: string;
}

export interface VoiceResult {
  /** Changes every time a recording ends, so a consumer can tell a new result from the last one. */
  id: number;
  kind: 'finished' | 'cancelled';
  /** One entry per line. Empty when cancelled. */
  segments: string[];
}

export interface VoiceSnapshot {
  supported: boolean;
  phase: VoicePhase;
  /** Final text so far in this recording, one entry per thought (not yet punctuated). */
  segments: string[];
  /** What the engine is still working out. */
  interim: string;
  /** 0 to 1 while the microphone level is known, otherwise null (the page shows a pulse instead). */
  level: number | null;
  error: VoiceError | null;
  result: VoiceResult | null;
}

// ─── Text helpers ─────────────────────────────────────────────────────────────

const SENTENCE_END = /[.!?…。।॥]$/;

export function normaliseSpeech(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
}

/**
 * One thought as a line: first letter capitalised, a full stop at the end unless it already ends a sentence.
 * A trailing comma, semicolon or colon becomes the full stop. Nothing inside the text is touched.
 */
export function finishLine(text: string): string {
  const clean = normaliseSpeech(text);
  if (!clean) return '';
  const capital = clean.charAt(0).toLocaleUpperCase() + clean.slice(1);
  if (SENTENCE_END.test(capital)) return capital;
  return `${capital.replace(/[,;:]+$/, '')}.`;
}

/** The text that goes in the box: what was there, then one line per thought. */
export function composeDictation(base: string, segments: string[]): string {
  const lines = segments.map(finishLine).filter(Boolean);
  if (lines.length === 0) return base;
  if (!base.trim()) return lines.join('\n');
  return `${base.replace(/\s+$/, '')}\n${lines.join('\n')}`;
}

// ─── Errors ───────────────────────────────────────────────────────────────────

export const VOICE_ERRORS: Record<VoiceErrorCode, Omit<VoiceError, 'code'>> = {
  unsupported: {
    message: "Voice input isn't available in this browser.",
    hint: 'Try a recent Chrome, Edge or Safari, or type your tasks here.',
  },
  denied: {
    message: 'Microphone access is blocked.',
    hint: "Allow the microphone for this site in your browser's address bar or site settings, then press the mic again. You can keep typing in the meantime.",
  },
  'no-microphone': {
    message: 'No microphone was found.',
    hint: 'Plug in or turn on a microphone, check that it is the one your browser uses, then try again.',
  },
  network: {
    message: 'Voice input could not reach the speech service.',
    hint: 'Check your connection and try again. What you said so far has been kept.',
  },
  'no-speech': {
    message: "We didn't hear anything.",
    hint: 'Check that the right microphone is selected and speak a little closer to it, then try again.',
  },
  stalled: {
    message: 'Voice input kept stopping.',
    hint: 'Press the mic to start again. What you said so far has been kept.',
  },
  language: {
    message: "This browser can't recognise speech in your language.",
    hint: 'Change the browser language or type your tasks here.',
  },
  'start-failed': {
    message: 'Voice input could not start.',
    hint: 'Reload the page and try again, or type your tasks here.',
  },
  unknown: {
    message: 'Voice input stopped unexpectedly.',
    hint: 'Press the mic to try again. What you said so far has been kept.',
  },
};

const makeError = (code: VoiceErrorCode): VoiceError => ({ code, ...VOICE_ERRORS[code] });

/** Maps the `error` of a SpeechRecognition error event. `null` means it is not an error to show. */
export function codeForSpeechError(error: string): VoiceErrorCode | 'ignore' | 'no-speech-retry' | 'capture' {
  switch (error) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'denied';
    case 'audio-capture':
      return 'capture';
    case 'network':
      return 'network';
    case 'language-not-supported':
      return 'language';
    case 'no-speech':
      return 'no-speech-retry';
    case 'aborted':
      return 'ignore';
    default:
      return 'unknown';
  }
}

// ─── Microphone level (optional) ──────────────────────────────────────────────

export interface LevelMeterDeps {
  getUserMedia?: (constraints: { audio: boolean }) => Promise<MediaStreamLike>;
  createAudioContext?: () => AudioContextLike;
  requestFrame: (cb: () => void) => number;
  cancelFrame: (id: number) => void;
}

interface MediaStreamLike { getTracks(): Array<{ stop(): void }> }
interface AnalyserLike { fftSize: number; frequencyBinCount: number; getByteTimeDomainData(data: Uint8Array): void }
export interface AudioContextLike {
  createMediaStreamSource(stream: unknown): { connect(node: unknown): void };
  createAnalyser(): AnalyserLike;
  close(): Promise<void>;
}

/**
 * Reads the level of the microphone for a visual indicator. Best effort: if the browser has no
 * getUserMedia or the stream cannot be opened it resolves to null and the page shows a pulse instead.
 */
export async function startLevelMeter(deps: LevelMeterDeps, onLevel: (level: number) => void): Promise<(() => void) | null> {
  if (!deps.getUserMedia || !deps.createAudioContext) return null;
  let stream: MediaStreamLike;
  let ctx: AudioContextLike;
  try {
    stream = await deps.getUserMedia({ audio: true });
    ctx = deps.createAudioContext();
  } catch {
    return null;
  }
  let stopped = false;
  let frame = 0;
  let last = 0;
  try {
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    ctx.createMediaStreamSource(stream).connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      if (stopped) return;
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (let i = 0; i < data.length; i += 1) {
        const v = (data[i] - 128) / 128;
        sum += v * v;
      }
      // Speech is quiet next to a full-scale signal, so the root mean square is scaled up before it is capped.
      const level = Math.min(1, Math.sqrt(sum / data.length) * 4);
      last = last * 0.6 + level * 0.4;
      onLevel(last);
      frame = deps.requestFrame(tick);
    };
    frame = deps.requestFrame(tick);
  } catch {
    stream.getTracks().forEach(t => t.stop());
    void ctx.close().catch(() => {});
    return null;
  }
  return () => {
    stopped = true;
    deps.cancelFrame(frame);
    stream.getTracks().forEach(t => t.stop());
    void ctx.close().catch(() => {});
  };
}

// ─── Controller ───────────────────────────────────────────────────────────────

export interface VoiceCaptureOptions {
  /** The recognition class. Defaults to the browser's SpeechRecognition or webkitSpeechRecognition. */
  ctor?: SpeechRecognitionCtor | null;
  lang?: string;
  /** Silence in ms after which the next speech starts a new line. */
  pauseMs?: number;
  /** How many times in a row the engine may be started again after the browser stopped it. */
  maxRestarts?: number;
  /** How many silent (no-speech) timeouts in a row end the recording. */
  maxSilentRestarts?: number;
  restartDelayMs?: number;
  /** How long to wait for the engine to finish after Finish before giving up on it. */
  stopTimeoutMs?: number;
  /** Set to false to never open the microphone for a level. */
  levelMeter?: LevelMeterDeps | false;
  /** Called once when a recording ends, with what was said (nothing if it was cancelled). */
  onResult?: (result: VoiceResult) => void;
  now?: () => number;
  setTimer?: (fn: () => void, ms: number) => unknown;
  clearTimer?: (id: unknown) => void;
}

export interface VoiceCapture {
  getSnapshot(): VoiceSnapshot;
  subscribe(listener: () => void): () => void;
  start(): void;
  /** Stops listening and keeps what was said. */
  finish(): void;
  /** Stops listening and throws away what was said in this recording. */
  cancel(): void;
  dismissError(): void;
  /** Replaces the function that is called when a recording ends (null for none). */
  setResultHandler(handler: ((result: VoiceResult) => void) | null): void;
  destroy(): void;
}

export function browserRecognitionCtor(win: unknown = typeof window === 'undefined' ? undefined : window): SpeechRecognitionCtor | null {
  const w = win as { SpeechRecognition?: SpeechRecognitionCtor; webkitSpeechRecognition?: SpeechRecognitionCtor } | undefined;
  return w?.SpeechRecognition ?? w?.webkitSpeechRecognition ?? null;
}

export function browserLevelMeterDeps(): LevelMeterDeps | false {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') return false;
  const md = navigator.mediaDevices;
  const AudioCtor = (window as unknown as { AudioContext?: new () => AudioContextLike; webkitAudioContext?: new () => AudioContextLike }).AudioContext
    ?? (window as unknown as { webkitAudioContext?: new () => AudioContextLike }).webkitAudioContext;
  if (!md?.getUserMedia || !AudioCtor) return false;
  return {
    getUserMedia: c => md.getUserMedia(c) as unknown as Promise<MediaStreamLike>,
    createAudioContext: () => new AudioCtor(),
    requestFrame: cb => window.requestAnimationFrame(cb),
    cancelFrame: id => window.cancelAnimationFrame(id),
  };
}

export function createVoiceCapture(options: VoiceCaptureOptions = {}): VoiceCapture {
  const ctor = options.ctor === undefined ? browserRecognitionCtor() : options.ctor;
  const lang = options.lang ?? (typeof navigator !== 'undefined' && navigator.language ? navigator.language : 'en-US');
  const pauseMs = options.pauseMs ?? 900;
  const maxRestarts = options.maxRestarts ?? 4;
  const maxSilentRestarts = options.maxSilentRestarts ?? 3;
  const restartDelayMs = options.restartDelayMs ?? 250;
  const stopTimeoutMs = options.stopTimeoutMs ?? 1500;
  const meterDeps = options.levelMeter === undefined ? browserLevelMeterDeps() : options.levelMeter;
  const clock = options.now ?? (() => (typeof performance !== 'undefined' ? performance.now() : Date.now()));
  const setTimer = options.setTimer ?? ((fn: () => void, ms: number) => setTimeout(fn, ms));
  const clearTimer = options.clearTimer ?? ((id: unknown) => clearTimeout(id as ReturnType<typeof setTimeout>));

  let snapshot: VoiceSnapshot = {
    supported: Boolean(ctor),
    phase: 'idle',
    segments: [],
    interim: '',
    level: null,
    error: null,
    result: null,
  };
  const listeners = new Set<() => void>();
  const emit = (patch: Partial<VoiceSnapshot>) => {
    snapshot = { ...snapshot, ...patch };
    listeners.forEach(l => l());
  };

  let recognition: SpeechRecognitionLike | null = null;
  let generation = 0;               // a recognition object from an earlier start must not act on this one
  let requested: 'finish' | 'cancel' | null = null;
  let restartsInRow = 0;
  let silentInRow = 0;
  let lastFinalAt: number | null = null;
  let phraseStartedAt: number | null = null;
  let resultCount = 0;
  let meterDisabled = false;
  let stopMeter: (() => void) | null = null;
  let meterPending = false;
  let meterGeneration = 0;
  let timer: unknown = null;
  let stopTimer: unknown = null;
  let resultHandler: ((result: VoiceResult) => void) | null = options.onResult ?? null;

  const clearTimers = () => {
    if (timer !== null) clearTimer(timer);
    if (stopTimer !== null) clearTimer(stopTimer);
    timer = null;
    stopTimer = null;
  };

  const endMeter = () => {
    meterGeneration += 1;
    meterPending = false;
    stopMeter?.();
    stopMeter = null;
    if (snapshot.level !== null) emit({ level: null });
  };

  const beginMeter = () => {
    if (!meterDeps || meterDisabled || stopMeter || meterPending) return;
    const mine = ++meterGeneration;
    meterPending = true;
    void startLevelMeter(meterDeps, level => { if (mine === meterGeneration) emit({ level }); }).then(stop => {
      if (mine === meterGeneration) meterPending = false;
      if (!stop) return;
      if (mine !== meterGeneration) stop();     // the recording ended while the microphone was being opened
      else stopMeter = stop;
    });
  };

  const detach = (r: SpeechRecognitionLike | null) => {
    if (!r) return;
    r.onstart = null;
    r.onresult = null;
    r.onerror = null;
    r.onend = null;
  };

  const addFinal = (text: string, startedAt: number, at: number) => {
    const segments = snapshot.segments.slice();
    const continues = segments.length > 0 && lastFinalAt !== null && startedAt - lastFinalAt < pauseMs;
    if (continues) segments[segments.length - 1] = `${segments[segments.length - 1]} ${text}`;
    else segments.push(text);
    lastFinalAt = at;
    snapshot = { ...snapshot, segments };
  };

  const complete = (kind: 'finished' | 'cancelled', error: VoiceError | null = null) => {
    clearTimers();
    generation += 1;
    detach(recognition);
    recognition = null;
    endMeter();
    let segments = snapshot.segments;
    if (kind === 'finished' && snapshot.interim.trim()) {
      // The engine was stopped in the middle of a phrase: keep what it had heard.
      const now = clock();
      addFinal(normaliseSpeech(snapshot.interim), phraseStartedAt ?? now, now);
      segments = snapshot.segments;
    }
    if (kind === 'cancelled') segments = [];
    resultCount += 1;
    requested = null;
    const result: VoiceResult = { id: resultCount, kind, segments };
    emit({ phase: 'idle', segments: [], interim: '', level: null, error, result });
    resultHandler?.(result);
  };

  const launch = () => {
    if (!ctor) return;
    const mine = generation;
    let rec: SpeechRecognitionLike;
    try {
      rec = new ctor();
    } catch {
      complete('finished', makeError('start-failed'));
      return;
    }
    recognition = rec;
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = lang;
    rec.maxAlternatives = 1;
    const live = () => mine === generation && recognition === rec;

    rec.onstart = () => {
      if (!live()) return;
      if (snapshot.phase === 'starting') emit({ phase: 'recording' });
      beginMeter();
    };

    rec.onresult = event => {
      if (!live()) return;
      const now = clock();
      restartsInRow = 0;
      silentInRow = 0;
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const text = normaliseSpeech(result[0]?.transcript ?? '');
        if (!text) continue;
        if (phraseStartedAt === null) phraseStartedAt = now;
        if (result.isFinal) {
          addFinal(text, phraseStartedAt, now);
          phraseStartedAt = null;
        } else {
          interim = interim ? `${interim} ${text}` : text;
        }
      }
      emit({ interim });
    };

    rec.onerror = event => {
      if (!live()) return;
      const code = codeForSpeechError(event.error);
      if (code === 'ignore') return;
      if (code === 'no-speech-retry') {
        silentInRow += 1;
        if (silentInRow >= maxSilentRestarts) complete('finished', makeError('no-speech'));
        return;                                   // the engine ends next, and onend starts it again
      }
      if (code === 'capture' && stopMeter && !meterDisabled) {
        // Opening the microphone for the level can take it away from the engine on some devices: give it up.
        meterDisabled = true;
        endMeter();
        return;                                   // onend starts the engine again, now without the level
      }
      complete('finished', makeError(code === 'capture' ? 'no-microphone' : code));
    };

    rec.onend = () => {
      if (!live()) return;
      if (requested === 'finish') {
        complete('finished');
        return;
      }
      if (snapshot.phase === 'idle') return;
      // The browser stopped listening by itself (silence, a time limit, a hiccup): start again, a few times at most.
      if (restartsInRow >= maxRestarts) {
        complete('finished', makeError('stalled'));
        return;
      }
      restartsInRow += 1;
      recognition = null;
      generation += 1;
      timer = setTimer(() => {
        timer = null;
        if (snapshot.phase === 'recording' || snapshot.phase === 'starting') launch();
      }, restartDelayMs);
    };

    try {
      rec.start();
    } catch {
      complete('finished', makeError('start-failed'));
    }
  };

  return {
    getSnapshot: () => snapshot,

    subscribe(listener) {
      listeners.add(listener);
      return () => { listeners.delete(listener); };
    },

    start() {
      if (snapshot.phase !== 'idle') return;
      if (!ctor) {
        emit({ error: makeError('unsupported') });
        return;
      }
      requested = null;
      restartsInRow = 0;
      silentInRow = 0;
      lastFinalAt = null;
      phraseStartedAt = null;
      meterDisabled = false;
      generation += 1;
      emit({ phase: 'starting', segments: [], interim: '', level: null, error: null });
      launch();
    },

    finish() {
      if (snapshot.phase === 'idle' || snapshot.phase === 'stopping') return;
      requested = 'finish';
      emit({ phase: 'stopping' });
      if (timer !== null) {                       // between two starts: nothing is listening, so there is nothing to wait for
        complete('finished');
        return;
      }
      const rec = recognition;
      try { rec?.stop(); } catch { /* already stopped */ }
      stopTimer = setTimer(() => complete('finished'), stopTimeoutMs);
    },

    cancel() {
      if (snapshot.phase === 'idle') return;
      requested = 'cancel';
      try { recognition?.abort(); } catch { /* already stopped */ }
      complete('cancelled');
    },

    dismissError() {
      if (snapshot.error) emit({ error: null });
    },

    setResultHandler(handler) {
      resultHandler = handler;
    },

    destroy() {
      clearTimers();
      generation += 1;
      try { recognition?.abort(); } catch { /* already stopped */ }
      detach(recognition);
      recognition = null;
      endMeter();
      listeners.clear();
      resultHandler = null;
    },
  };
}
