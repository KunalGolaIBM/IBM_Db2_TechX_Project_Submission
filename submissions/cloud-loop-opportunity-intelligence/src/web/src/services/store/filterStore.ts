import { create } from "zustand";

export interface FilterState {
  searchQuery: string;
  selectedKind: string;
  selectedMode: string;
  selectedLocation: string;
  activeOnly: boolean;
  selectedSkills: string[];
  mobileMenuOpen: boolean;
  setSearchQuery: (q: string) => void;
  setSelectedKind: (kind: string) => void;
  setSelectedMode: (mode: string) => void;
  setSelectedLocation: (loc: string) => void;
  setActiveOnly: (active: boolean) => void;
  toggleSkill: (skill: string) => void;
  clearFilters: () => void;
  setMobileMenuOpen: (open: boolean) => void;
}

export const useFilterStore = create<FilterState>((set) => ({
  searchQuery: "",
  selectedKind: "all",
  selectedMode: "all",
  selectedLocation: "all",
  activeOnly: false,
  selectedSkills: [],
  mobileMenuOpen: false,

  setSearchQuery: (searchQuery) => set({ searchQuery }),
  setSelectedKind: (selectedKind) => set({ selectedKind }),
  setSelectedMode: (selectedMode) => set({ selectedMode }),
  setSelectedLocation: (selectedLocation) => set({ selectedLocation }),
  setActiveOnly: (activeOnly) => set({ activeOnly }),
  toggleSkill: (skill) =>
    set((state) => ({
      selectedSkills: state.selectedSkills.includes(skill)
        ? state.selectedSkills.filter((s) => s !== skill)
        : [...state.selectedSkills, skill],
    })),
  clearFilters: () =>
    set({
      searchQuery: "",
      selectedKind: "all",
      selectedMode: "all",
      selectedLocation: "all",
      activeOnly: false,
      selectedSkills: [],
    }),
  setMobileMenuOpen: (mobileMenuOpen) => set({ mobileMenuOpen }),
}));
