import { useEffect, useState, useSyncExternalStore } from 'react';
import {
  createVoiceCapture,
  type VoiceCapture,
  type VoiceCaptureOptions,
  type VoiceResult,
  type VoiceSnapshot,
} from '../lib/voiceCapture';

export interface UseVoiceCapture extends VoiceSnapshot {
  start: () => void;
  /** Stops listening and keeps what was said. */
  finish: () => void;
  /** Stops listening and throws away what was said in this recording. */
  cancel: () => void;
  dismissError: () => void;
}

/**
 * Voice dictation for a page. `onResult` runs once when a recording ends, with the lines that were said
 * (see src/lib/voiceCapture.ts for what the controller does and how it is tested).
 */
export function useVoiceCapture(onResult?: (result: VoiceResult) => void, options?: Omit<VoiceCaptureOptions, 'onResult'>): UseVoiceCapture {
  const [capture] = useState<VoiceCapture>(() => createVoiceCapture(options));

  useEffect(() => {
    capture.setResultHandler(onResult ?? null);
    return () => capture.setResultHandler(null);
  }, [capture, onResult]);
  useEffect(() => () => capture.destroy(), [capture]);

  const snapshot = useSyncExternalStore(capture.subscribe, capture.getSnapshot, capture.getSnapshot);
  return {
    ...snapshot,
    start: () => capture.start(),
    finish: () => capture.finish(),
    cancel: () => capture.cancel(),
    dismissError: () => capture.dismissError(),
  };
}
