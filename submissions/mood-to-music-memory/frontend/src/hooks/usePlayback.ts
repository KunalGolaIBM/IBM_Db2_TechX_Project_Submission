import { useEffect, useRef } from 'react';
import { useAppStore } from '../store/appStore';

// Singleton audio element across component re-renders
let globalAudio: HTMLAudioElement | null = null;

export function usePlayback() {
  const isPlaying = useAppStore(s => s.isPlaying);
  const currentSong = useAppStore(s => s.currentSong);
  const volume = useAppStore(s => s.volume);
  const intervalRef = useRef<number | null>(null);

  // Audio element management
  useEffect(() => {
    if (!globalAudio) {
      globalAudio = new Audio();
    }

    const audio = globalAudio;

    const onTimeUpdate = () => {
      useAppStore.getState().setCurrentTime(Math.floor(audio.currentTime));
    };

    const onEnded = () => {
      const state = useAppStore.getState();
      if (state.repeatEnabled) {
        audio.currentTime = 0;
        audio.play().catch(() => {});
      } else {
        state.nextSong();
      }
    };

    audio.addEventListener('timeupdate', onTimeUpdate);
    audio.addEventListener('ended', onEnded);

    return () => {
      audio.removeEventListener('timeupdate', onTimeUpdate);
      audio.removeEventListener('ended', onEnded);
    };
  }, []);

  // Update volume
  useEffect(() => {
    if (globalAudio) {
      globalAudio.volume = Math.max(0, Math.min(1, volume));
    }
  }, [volume]);

  // Handle Play / Pause / Song Change
  useEffect(() => {
    const audio = globalAudio;
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (!currentSong) {
      if (audio) {
        audio.pause();
      }
      return;
    }

    const hasRealAudio = Boolean(currentSong.audioUrl);

    if (hasRealAudio && audio) {
      const currentSrc = audio.src;
      const targetSrc = currentSong.audioUrl!.startsWith('http')
        ? currentSong.audioUrl!
        : `http://localhost:8000${currentSong.audioUrl}`;

      if (currentSrc !== targetSrc) {
        audio.src = targetSrc;
        audio.currentTime = 0;
      }

      if (isPlaying) {
        audio.play().catch(err => {
          console.warn('[usePlayback] Audio play prevented or unavailable:', err);
          // Fallback to simulated timer if browser blocked autoplay
          fallbackTimer();
        });
      } else {
        audio.pause();
      }
    } else {
      // Fallback timer for songs without physical audio file
      if (audio) audio.pause();
      if (isPlaying) {
        fallbackTimer();
      }
    }

    function fallbackTimer() {
      if (intervalRef.current) clearInterval(intervalRef.current);
      intervalRef.current = window.setInterval(() => {
        const state = useAppStore.getState();
        const { currentTime, currentSong: song, repeatEnabled } = state;
        const duration = song?.duration ?? 180;

        if (currentTime >= duration) {
          if (repeatEnabled) {
            state.setCurrentTime(0);
          } else {
            state.nextSong();
          }
        } else {
          state.setCurrentTime(currentTime + 1);
        }
      }, 1000);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isPlaying, currentSong?.id, currentSong?.audioUrl]);
}
