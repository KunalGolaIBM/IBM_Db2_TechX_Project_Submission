import { useEffect, useRef } from 'react';
import { useAppStore } from '../store/appStore';

export function usePlayback() {
  const isPlaying = useAppStore(s => s.isPlaying);
  const currentSongId = useAppStore(s => s.currentSong?.id);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);

    if (isPlaying && currentSongId) {
      intervalRef.current = window.setInterval(() => {
        const state = useAppStore.getState();
        const { currentTime, currentSong, repeatEnabled } = state;
        const duration = currentSong?.duration ?? 1;

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
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isPlaying, currentSongId]);
}
