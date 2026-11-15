import { describe, it, expect, vi } from 'vitest';
import {
  codeForSpeechError,
  composeDictation,
  createVoiceCapture,
  finishLine,
  normaliseSpeech,
  startLevelMeter,
  VOICE_ERRORS,
  type LevelMeterDeps,
  type SpeechEventLike,
  type SpeechRecognitionLike,
  type VoiceCapture,
} from './voiceCapture';

// ─── Fakes ────────────────────────────────────────────────────────────────────

class FakeRecognition implements SpeechRecognitionLike {
  static instances: FakeRecognition[] = [];
  static startThrows = false;
  continuous = false;
  interimResults = false;
  lang = '';
  maxAlternatives = 0;
  onstart: (() => void) | null = null;
  onresult: ((event: SpeechEventLike) => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  started = 0;
  stopped = 0;
  aborted = 0;
  private all: Array<{ isFinal: boolean; 0: { transcript: string } }> = [];

  constructor() { FakeRecognition.instances.push(this); }
  start() {
    if (FakeRecognition.startThrows) throw new Error('InvalidStateError');
    this.started += 1;
  }
  stop() { this.stopped += 1; }
  abort() { this.aborted += 1; }

  // test helpers
  begin() { this.onstart?.(); }
  say(text: string, isFinal = false) {
    const index = this.all.length;
    this.all.push({ isFinal, 0: { transcript: text } });
    this.onresult?.({ resultIndex: index, results: this.all });
  }
  fail(error: string) { this.onerror?.({ error }); }
  end() { this.onend?.(); }
}

const setup = (extra: Parameters<typeof createVoiceCapture>[0] = {}) => {
  FakeRecognition.instances = [];
  FakeRecognition.startThrows = false;
  const clock = { t: 1000 };
  const timers: Array<{ id: number; at: number; fn: () => void }> = [];
  let nextId = 1;
  const capture = createVoiceCapture({
    ctor: FakeRecognition,
    lang: 'en-IN',
    levelMeter: false,
    now: () => clock.t,
    setTimer: (fn, ms) => { const id = nextId++; timers.push({ id, at: clock.t + ms, fn }); return id; },
    clearTimer: id => { const i = timers.findIndex(x => x.id === id); if (i >= 0) timers.splice(i, 1); },
    ...extra,
  });
  const current = () => FakeRecognition.instances[FakeRecognition.instances.length - 1];
  const advance = (ms: number) => {
    clock.t += ms;
    timers.filter(x => x.at <= clock.t).forEach(x => { timers.splice(timers.indexOf(x), 1); x.fn(); });
  };
  /** Start and let the engine report that it is listening. */
  const startRecording = (c: VoiceCapture = capture) => { c.start(); current().begin(); };
  return { capture, clock, timers, current, advance, startRecording };
};

// ─── Text ─────────────────────────────────────────────────────────────────────

describe('text helpers', () => {
  it('normaliseSpeech trims and collapses whitespace', () => {
    expect(normaliseSpeech('  call   mum \n now ')).toBe('call mum now');
  });

  it('finishLine capitalises the first letter and adds a full stop', () => {
    expect(finishLine('buy milk')).toBe('Buy milk.');
    expect(finishLine('  email   the report  ')).toBe('Email the report.');
  });

  it('finishLine leaves a sentence that already ends alone, and swaps a trailing comma for the stop', () => {
    expect(finishLine('is the form ready?')).toBe('Is the form ready?');
    expect(finishLine('great!')).toBe('Great!');
    expect(finishLine('call mum,')).toBe('Call mum.');
    expect(finishLine('यह काम करना है।')).toBe('यह काम करना है।');
  });

  it('finishLine changes nothing inside the text, and nothing for empty text', () => {
    expect(finishLine('pay RENT on the 5th')).toBe('Pay RENT on the 5th.');
    expect(finishLine('   ')).toBe('');
  });

  it('composeDictation puts one line per thought after what was there', () => {
    expect(composeDictation('', ['buy milk', 'call mum'])).toBe('Buy milk.\nCall mum.');
    expect(composeDictation('Existing note.', ['buy milk'])).toBe('Existing note.\nBuy milk.');
    expect(composeDictation('Existing note.\n', ['buy milk'])).toBe('Existing note.\nBuy milk.');
  });

  it('composeDictation returns the text unchanged when nothing was said', () => {
    expect(composeDictation('keep me', [])).toBe('keep me');
    expect(composeDictation('keep me', ['  '])).toBe('keep me');
  });
});

describe('error codes', () => {
  it('maps the engine codes', () => {
    expect(codeForSpeechError('not-allowed')).toBe('denied');
    expect(codeForSpeechError('service-not-allowed')).toBe('denied');
    expect(codeForSpeechError('audio-capture')).toBe('capture');
    expect(codeForSpeechError('network')).toBe('network');
    expect(codeForSpeechError('language-not-supported')).toBe('language');
    expect(codeForSpeechError('no-speech')).toBe('no-speech-retry');
    expect(codeForSpeechError('aborted')).toBe('ignore');
    expect(codeForSpeechError('something-new')).toBe('unknown');
  });

  it('every message has a hint the person can act on', () => {
    Object.values(VOICE_ERRORS).forEach(e => {
      expect(e.message.length).toBeGreaterThan(10);
      expect(e.hint.length).toBeGreaterThan(10);
    });
  });
});

// ─── Starting, interim and final text ─────────────────────────────────────────

describe('starting and listening', () => {
  it('goes starting, then recording once the engine is listening, and sets the engine up', () => {
    const { capture, current } = setup();
    expect(capture.getSnapshot().supported).toBe(true);
    capture.start();
    expect(capture.getSnapshot().phase).toBe('starting');
    expect(current().started).toBe(1);
    expect(current()).toMatchObject({ continuous: true, interimResults: true, lang: 'en-IN' });
    current().begin();
    expect(capture.getSnapshot().phase).toBe('recording');
  });

  it('ignores a second start while recording', () => {
    const { capture, startRecording } = setup();
    startRecording();
    capture.start();
    expect(FakeRecognition.instances).toHaveLength(1);
  });

  it('keeps interim text apart from final text, and never adds a final result twice', () => {
    const { capture, current, startRecording } = setup();
    startRecording();
    current().say('buy mil');
    expect(capture.getSnapshot()).toMatchObject({ interim: 'buy mil', segments: [] });
    current().say('buy milk', true);
    expect(capture.getSnapshot()).toMatchObject({ interim: '', segments: ['buy milk'] });
    current().say('and', false);
    expect(capture.getSnapshot()).toMatchObject({ interim: 'and', segments: ['buy milk'] });
  });

  it('merges a final result that follows without a pause, and starts a new line after one', () => {
    const { capture, current, clock, advance, startRecording } = setup({ pauseMs: 900 });
    startRecording();
    current().say('buy milk', true);
    advance(300);
    current().say('and eggs', true);
    expect(capture.getSnapshot().segments).toEqual(['buy milk and eggs']);
    advance(1500);
    current().say('call mum', true);
    expect(capture.getSnapshot().segments).toEqual(['buy milk and eggs', 'call mum']);
    expect(clock.t).toBeGreaterThan(1000);
  });

  it('measures the pause from when the next speech starts, not from when its final result arrives', () => {
    const { capture, current, advance, startRecording } = setup({ pauseMs: 900 });
    startRecording();
    current().say('buy milk', true);
    advance(200);
    current().say('and', false);          // speech started again quickly: the same thought
    advance(3000);                        // it takes a while to be finalised
    current().say('and eggs', true);
    expect(capture.getSnapshot().segments).toEqual(['buy milk and eggs']);
  });

  it('ignores empty results', () => {
    const { capture, current, startRecording } = setup();
    startRecording();
    current().say('   ', true);
    expect(capture.getSnapshot().segments).toEqual([]);
  });
});

// ─── Finish and cancel ────────────────────────────────────────────────────────

describe('finish and cancel', () => {
  it('Finish stops the engine, waits for its last results, and hands over the lines', () => {
    const { capture, current, advance, startRecording } = setup();
    startRecording();
    current().say('buy milk', true);
    capture.finish();
    expect(current().stopped).toBe(1);
    expect(capture.getSnapshot().phase).toBe('stopping');
    advance(1200);
    current().say('call mum', true);      // a last result can still arrive after stop()
    current().end();
    const s = capture.getSnapshot();
    expect(s.phase).toBe('idle');
    expect(s.result).toMatchObject({ kind: 'finished', segments: ['buy milk', 'call mum'] });
    expect(s.segments).toEqual([]);
  });

  it('Finish keeps a phrase the engine had not finalised', () => {
    const { capture, current, startRecording } = setup();
    startRecording();
    current().say('call the dentist', false);
    capture.finish();
    current().end();
    expect(capture.getSnapshot().result?.segments).toEqual(['call the dentist']);
  });

  it('Finish does not wait for ever for an engine that never ends', () => {
    const { capture, advance, startRecording } = setup({ stopTimeoutMs: 1500 });
    startRecording();
    capture.finish();
    expect(capture.getSnapshot().phase).toBe('stopping');
    advance(1600);
    expect(capture.getSnapshot().phase).toBe('idle');
    expect(capture.getSnapshot().result?.kind).toBe('finished');
  });

  it('Cancel aborts, throws away what was said, and ignores anything the old engine says later', () => {
    const { capture, current, startRecording } = setup();
    startRecording();
    const rec = current();
    rec.say('buy milk', true);
    capture.cancel();
    expect(rec.aborted).toBe(1);
    expect(capture.getSnapshot()).toMatchObject({ phase: 'idle', segments: [], interim: '' });
    expect(capture.getSnapshot().result).toMatchObject({ kind: 'cancelled', segments: [] });
    rec.say('late words', true);
    rec.end();
    expect(capture.getSnapshot()).toMatchObject({ phase: 'idle', segments: [] });
  });

  it('gives every recording its own result id', () => {
    const { capture, current, startRecording } = setup();
    startRecording(); current().say('one', true); capture.finish(); current().end();
    const first = capture.getSnapshot().result!.id;
    startRecording(); capture.cancel();
    expect(capture.getSnapshot().result!.id).toBe(first + 1);
  });

  it('Finish and Cancel do nothing when nothing is recording', () => {
    const { capture } = setup();
    capture.finish();
    capture.cancel();
    expect(capture.getSnapshot()).toMatchObject({ phase: 'idle', result: null });
  });
});

// ─── The browser stopping early ───────────────────────────────────────────────

describe('restarting', () => {
  it('starts the engine again when the browser ends it, after a short delay, and keeps the text', () => {
    const { capture, current, advance, startRecording } = setup({ restartDelayMs: 250 });
    startRecording();
    current().say('buy milk', true);
    current().end();
    expect(capture.getSnapshot().phase).toBe('recording');
    expect(FakeRecognition.instances).toHaveLength(1);
    advance(300);
    expect(FakeRecognition.instances).toHaveLength(2);
    current().begin();
    advance(1200);
    current().say('call mum', true);
    expect(capture.getSnapshot().segments).toEqual(['buy milk', 'call mum']);
  });

  it('gives up after too many restarts in a row, says so, and keeps what was said', () => {
    const { capture, current, advance, startRecording } = setup({ maxRestarts: 2 });
    startRecording();
    current().say('buy milk', true);
    current().end(); advance(300);
    current().begin(); current().end(); advance(300);
    current().begin(); current().end();
    const s = capture.getSnapshot();
    expect(s.phase).toBe('idle');
    expect(s.error?.code).toBe('stalled');
    expect(s.result?.segments).toEqual(['buy milk']);
  });

  it('counts only restarts in a row: a result in between starts the count again', () => {
    const { capture, current, advance, startRecording } = setup({ maxRestarts: 1 });
    startRecording();
    for (let i = 0; i < 4; i += 1) {
      current().end(); advance(300);
      current().begin();
      current().say(`thought ${i}`, true);
      advance(2000);
    }
    expect(capture.getSnapshot().phase).toBe('recording');
    expect(capture.getSnapshot().error).toBeNull();
  });

  it('does not start another engine if Finish or Cancel came between two starts', () => {
    const a = setup();
    a.startRecording();
    a.current().end();
    a.capture.finish();
    a.advance(1000);
    expect(FakeRecognition.instances).toHaveLength(1);
    expect(a.capture.getSnapshot().phase).toBe('idle');
    const b = setup();
    b.startRecording();
    b.current().end();
    b.capture.cancel();
    b.advance(1000);
    expect(FakeRecognition.instances).toHaveLength(1);
  });
});

// ─── Errors ───────────────────────────────────────────────────────────────────

describe('errors', () => {
  it('a denied microphone ends the recording with a message, and does not restart', () => {
    const { capture, current, advance } = setup();
    capture.start();
    current().fail('not-allowed');
    const s = capture.getSnapshot();
    expect(s.phase).toBe('idle');
    expect(s.error).toMatchObject({ code: 'denied', message: VOICE_ERRORS.denied.message });
    current().end();
    advance(2000);
    expect(FakeRecognition.instances).toHaveLength(1);
  });

  it('keeps what was said when an error ends the recording', () => {
    const { capture, current, startRecording } = setup();
    startRecording();
    current().say('buy milk', true);
    current().fail('network');
    expect(capture.getSnapshot().error?.code).toBe('network');
    expect(capture.getSnapshot().result).toMatchObject({ kind: 'finished', segments: ['buy milk'] });
  });

  it('no microphone, an unsupported language and an unknown code each get their own message', () => {
    for (const [code, expected] of [['audio-capture', 'no-microphone'], ['language-not-supported', 'language'], ['bad-grammar', 'unknown']] as const) {
      const { capture, current, startRecording } = setup();
      startRecording();
      current().fail(code);
      expect(capture.getSnapshot().error?.code).toBe(expected);
    }
  });

  it('silence is not an error at first: the engine is started again quietly', () => {
    const { capture, current, advance, startRecording } = setup({ maxSilentRestarts: 3 });
    startRecording();
    current().fail('no-speech'); current().end(); advance(300);
    expect(capture.getSnapshot()).toMatchObject({ phase: 'recording', error: null });
    expect(FakeRecognition.instances).toHaveLength(2);
  });

  it('after several silent timeouts in a row it stops and says nothing was heard', () => {
    const { capture, current, advance, startRecording } = setup({ maxSilentRestarts: 3, maxRestarts: 10 });
    startRecording();
    for (let i = 0; i < 2; i += 1) { current().fail('no-speech'); current().end(); advance(300); current().begin(); }
    current().fail('no-speech');
    expect(capture.getSnapshot().phase).toBe('idle');
    expect(capture.getSnapshot().error?.code).toBe('no-speech');
  });

  it('an abort from the browser is not an error', () => {
    const { capture, current, startRecording } = setup();
    startRecording();
    current().fail('aborted');
    expect(capture.getSnapshot()).toMatchObject({ phase: 'recording', error: null });
  });

  it('a browser without the API says so and never starts', () => {
    const { capture } = setup({ ctor: null });
    expect(capture.getSnapshot().supported).toBe(false);
    capture.start();
    expect(capture.getSnapshot()).toMatchObject({ phase: 'idle', error: { code: 'unsupported' } });
    expect(FakeRecognition.instances).toHaveLength(0);
  });

  it('an engine that refuses to start is reported', () => {
    const { capture } = setup();
    FakeRecognition.startThrows = true;
    capture.start();
    expect(capture.getSnapshot()).toMatchObject({ phase: 'idle', error: { code: 'start-failed' } });
  });

  it('the error can be dismissed, and a new start clears it', () => {
    const { capture, current } = setup();
    capture.start();
    current().fail('not-allowed');
    capture.dismissError();
    expect(capture.getSnapshot().error).toBeNull();
    capture.start();
    current().fail('not-allowed');
    capture.start();
    expect(capture.getSnapshot().error).toBeNull();
  });
});

// ─── Subscribing and tearing down ─────────────────────────────────────────────

describe('subscribe and destroy', () => {
  it('tells listeners about every change, and stops after unsubscribe', () => {
    const { capture, current, startRecording } = setup();
    const listener = vi.fn();
    const off = capture.subscribe(listener);
    startRecording();
    current().say('buy milk', true);
    const calls = listener.mock.calls.length;
    expect(calls).toBeGreaterThanOrEqual(3);
    off();
    current().say('call mum', true);
    expect(listener.mock.calls.length).toBe(calls);
  });

  it('destroy aborts the engine and ignores anything it says afterwards', () => {
    const { capture, current, startRecording } = setup();
    startRecording();
    const rec = current();
    capture.destroy();
    expect(rec.aborted).toBe(1);
    const before = capture.getSnapshot();
    rec.say('late', true);
    rec.end();
    expect(capture.getSnapshot()).toBe(before);
  });
});

// ─── The microphone level ─────────────────────────────────────────────────────

const flush = async () => { for (let i = 0; i < 6; i += 1) await Promise.resolve(); };

const meterDeps = (amplitude: { v: number }) => {
  const frames: Array<() => void> = [];
  const track = { stop: vi.fn() };
  const closed = vi.fn(() => Promise.resolve());
  const deps: LevelMeterDeps = {
    getUserMedia: vi.fn(() => Promise.resolve({ getTracks: () => [track] })),
    createAudioContext: () => ({
      createMediaStreamSource: () => ({ connect: () => {} }),
      createAnalyser: () => ({
        fftSize: 0,
        frequencyBinCount: 64,
        getByteTimeDomainData: (data: Uint8Array) => { for (let i = 0; i < data.length; i += 1) data[i] = 128 + (i % 2 ? amplitude.v : -amplitude.v); },
      }),
      close: closed,
    }),
    requestFrame: cb => { frames.push(cb); return frames.length; },
    cancelFrame: () => {},
  };
  const run = (n = 1) => { for (let i = 0; i < n; i += 1) frames.splice(0).forEach(f => f()); };
  return { deps, run, track, closed };
};

describe('the microphone level', () => {
  it('reports a level that follows the sound, and releases the microphone when stopped', async () => {
    const amp = { v: 0 };
    const m = meterDeps(amp);
    const levels: number[] = [];
    const stop = await startLevelMeter(m.deps, l => levels.push(l));
    expect(stop).not.toBeNull();
    m.run(6);
    expect(Math.max(...levels)).toBeLessThan(0.05);
    amp.v = 60;
    m.run(10);
    expect(Math.max(...levels)).toBeGreaterThan(0.5);
    expect(Math.max(...levels)).toBeLessThanOrEqual(1);
    stop!();
    expect(m.track.stop).toHaveBeenCalled();
    expect(m.closed).toHaveBeenCalled();
  });

  it('is null, not an error, without getUserMedia or when the stream cannot be opened', async () => {
    expect(await startLevelMeter({ requestFrame: () => 0, cancelFrame: () => {} }, () => {})).toBeNull();
    const m = meterDeps({ v: 0 });
    m.deps.getUserMedia = vi.fn(() => Promise.reject(new Error('NotAllowedError')));
    expect(await startLevelMeter(m.deps, () => {})).toBeNull();
  });

  it('shows up in the snapshot while recording and goes back to null afterwards', async () => {
    const amp = { v: 70 };
    const m = meterDeps(amp);
    const { capture, current, startRecording } = setup({ levelMeter: m.deps });
    startRecording();
    await flush();
    m.run(8);
    expect(capture.getSnapshot().level).toBeGreaterThan(0.4);
    capture.finish();
    current().end();
    expect(capture.getSnapshot().level).toBeNull();
    expect(m.track.stop).toHaveBeenCalled();
  });

  it('the recording works without a level when the microphone cannot be opened for it', async () => {
    const m = meterDeps({ v: 0 });
    m.deps.getUserMedia = vi.fn(() => Promise.reject(new Error('busy')));
    const { capture, current, startRecording } = setup({ levelMeter: m.deps });
    startRecording();
    await flush();
    current().say('buy milk', true);
    expect(capture.getSnapshot()).toMatchObject({ phase: 'recording', level: null, segments: ['buy milk'] });
  });

  it('a recording that ends while the microphone is still being opened releases it', async () => {
    const m = meterDeps({ v: 10 });
    const { capture, startRecording } = setup({ levelMeter: m.deps });
    startRecording();
    capture.cancel();                       // before the stream promise has resolved
    await flush();
    expect(m.track.stop).toHaveBeenCalled();
    expect(capture.getSnapshot().level).toBeNull();
  });

  it('if opening the microphone for the level takes it from the engine, the level is given up and the engine restarts', async () => {
    const m = meterDeps({ v: 20 });
    const { capture, current, advance, startRecording } = setup({ levelMeter: m.deps });
    startRecording();
    await flush();
    current().fail('audio-capture');         // the engine lost the microphone
    expect(capture.getSnapshot().error).toBeNull();
    expect(m.track.stop).toHaveBeenCalled();
    current().end();
    advance(300);
    expect(FakeRecognition.instances).toHaveLength(2);
    current().begin();
    await flush();
    expect(m.deps.getUserMedia).toHaveBeenCalledTimes(1);   // not opened again for this recording
    expect(capture.getSnapshot().phase).toBe('recording');
  });
});

describe('onResult', () => {
  it('is called once per recording, with the lines, and with nothing when cancelled', () => {
    const onResult = vi.fn();
    const { capture, current, startRecording } = setup({ onResult });
    startRecording();
    current().say('buy milk', true);
    capture.finish();
    current().end();
    expect(onResult).toHaveBeenCalledTimes(1);
    expect(onResult).toHaveBeenLastCalledWith({ id: 1, kind: 'finished', segments: ['buy milk'] });
    startRecording();
    current().say('ignored', true);
    capture.cancel();
    expect(onResult).toHaveBeenCalledTimes(2);
    expect(onResult).toHaveBeenLastCalledWith({ id: 2, kind: 'cancelled', segments: [] });
  });

  it('is also called when an error ends the recording', () => {
    const onResult = vi.fn();
    const { capture, current } = setup({ onResult });
    capture.start();
    current().fail('not-allowed');
    expect(onResult).toHaveBeenCalledWith({ id: 1, kind: 'finished', segments: [] });
  });
});

describe('setResultHandler', () => {
  it('replaces the handler, and null stops the calls', () => {
    const first = vi.fn();
    const second = vi.fn();
    const { capture, startRecording } = setup({ onResult: first });
    capture.setResultHandler(second);
    startRecording();
    capture.cancel();
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
    capture.setResultHandler(null);
    startRecording();
    capture.cancel();
    expect(second).toHaveBeenCalledTimes(1);
  });
});
