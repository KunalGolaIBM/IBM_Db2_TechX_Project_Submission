import { create } from "zustand";

export interface TrackingState {
  trackedMap: Record<string, { status: string; bookmarked: boolean }>;
  setTracking: (opportunityId: string, status: string, bookmarked: boolean) => void;
  toggleBookmark: (opportunityId: string) => void;
  loadTracked: (items: Array<{ opportunity_id: string; status: string; bookmarked: boolean }>) => void;
}

export const useTrackingStore = create<TrackingState>((set) => ({
  trackedMap: {},
  setTracking: (opportunityId, status, bookmarked) =>
    set((state) => ({
      trackedMap: {
        ...state.trackedMap,
        [opportunityId]: { status, bookmarked },
      },
    })),
  toggleBookmark: (opportunityId) =>
    set((state) => {
      const current = state.trackedMap[opportunityId] || { status: "None", bookmarked: false };
      return {
        trackedMap: {
          ...state.trackedMap,
          [opportunityId]: { ...current, bookmarked: !current.bookmarked },
        },
      };
    }),
  loadTracked: (items) => {
    const map: Record<string, { status: string; bookmarked: boolean }> = {};
    for (const item of items) {
      map[item.opportunity_id] = {
        status: item.status,
        bookmarked: Boolean(item.bookmarked),
      };
    }
    set({ trackedMap: map });
  },
}));
