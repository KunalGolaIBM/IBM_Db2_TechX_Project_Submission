import type { Character, WorldId } from './types'

export const characters: Character[] = [
  { id: 'sam', name: 'Sam Altman', role: 'OpenAI-inspired strategist', color: '#55e6ff', accent: '#1260a5', unlocked: true, unlockCost: 0, effect: 'Balanced runner' },
  { id: 'jensen', name: 'Jensen Huang', role: 'GPU power specialist', color: '#8bff75', accent: '#1d7b4d', unlocked: false, unlockCost: 120, effect: 'Chip pickups score +25%' },
  { id: 'elon', name: 'Elon Musk', role: 'High-speed unlockable', color: '#ff6f91', accent: '#8a2045', unlocked: false, unlockCost: 220, effect: 'Starts with a speed boost' },
  { id: 'mark', name: 'Mark Zuckerberg', role: 'Metaverse runner', color: '#8e9bff', accent: '#3d42a1', unlocked: false, unlockCost: 320, effect: 'Magnet duration +2s' },
  { id: 'satya', name: 'Satya Nadella', role: 'Cloud systems leader', color: '#ffd166', accent: '#a74c45', unlocked: false, unlockCost: 450, effect: 'One extra life per run' },
]

export const worlds: { id: WorldId; name: string; subtitle: string; unlockCost: number; colors: [number, number, number] }[] = [
  { id: 'silicon-valley', name: 'Silicon Valley', subtitle: 'Campus roads and digital billboards', unlockCost: 0, colors: [0x071016, 0x164456, 0x2c90a8] },
  { id: 'neon-ai-city', name: 'Neon AI City', subtitle: 'Holograms after dark', unlockCost: 180, colors: [0x10071c, 0x6a247d, 0xf05cff] },
  { id: 'data-center', name: 'AI Data Center', subtitle: 'Cold blue server corridors', unlockCost: 360, colors: [0x06121d, 0x176078, 0x51d5ff] },
  { id: 'gpu-factory', name: 'GPU Factory', subtitle: 'Industrial heat and energy', unlockCost: 600, colors: [0x1a1008, 0x754112, 0xff9f43] },
]

export const achievementNames = ['First Run', 'Coin Collector', 'Speed Demon', 'Survivor', 'Million-Meter Runner', 'Full Character Collection']
export const missionNames = ['Run 500 meters', 'Collect 100 coins', 'Reach speed 20']
