import type { Character } from '../types/game'

const image = '/assets/char_junior_debugger_1794382058153.jpg'
const imageAlt = '/assets/char_script_ninja_1794382057226.jpg'
const makeStats = (speed: number, jump: number) => ({
  speed, jump, shieldDuration: Math.min(99, speed + 4),
  magnetRadius: Math.min(99, jump - 2), syntaxBonus: Math.min(99, speed + 1),
})

export const CHARACTERS_DATA: Character[] = [
  { id: 'sam', name: 'Sam Altman', title: 'OpenAI-inspired strategist', description: 'A balanced operator built for reliable lane changes and consistent runs.', rarity: 'Common', unlocked: true, image, accentColor: '#00E5FF', glowColor: 'rgba(0,229,255,.4)', stats: makeStats(72, 78), passive: { name: 'Balanced Runner', description: 'A dependable all-rounder.', codeSnippet: 'run({ strategy: "balanced" });' } },
  { id: 'jensen', name: 'Jensen Huang', title: 'GPU power specialist', description: 'Industrial momentum turns every chip pickup into a bigger score.', rarity: 'Rare', unlocked: true, image: imageAlt, accentColor: '#A3FF12', glowColor: 'rgba(163,255,18,.4)', stats: makeStats(80, 72), passive: { name: 'Tensor Boost', description: 'Chip pickups score 25% more.', codeSnippet: 'tensor.cores.accelerate();' } },
  { id: 'elon', name: 'Elon Musk', title: 'High-speed unlockable', description: 'A fast, tall runner who starts every run with extra momentum.', rarity: 'Epic', unlocked: false, unlockCost: 220, image, accentColor: '#EC4899', glowColor: 'rgba(236,72,153,.4)', stats: makeStats(91, 74), passive: { name: 'Launch Window', description: 'Starts with a speed boost.', codeSnippet: 'launch({ thrust: "maximum" });' } },
  { id: 'mark', name: 'Mark Zuckerberg', title: 'Metaverse runner', description: 'Compact and precise, with a larger window for collecting power-ups.', rarity: 'Rare', unlocked: false, unlockCost: 320, image: imageAlt, accentColor: '#8B5CF6', glowColor: 'rgba(139,92,246,.4)', stats: makeStats(78, 86), passive: { name: 'Social Magnet', description: 'Magnet duration is extended.', codeSnippet: 'network.magnet({ duration: 2 });' } },
  { id: 'satya', name: 'Satya Nadella', title: 'Cloud systems leader', description: 'Resilient cloud instincts keep one extra life in reserve.', rarity: 'Legendary', unlocked: false, unlockCost: 450, image, accentColor: '#F59E0B', glowColor: 'rgba(245,158,11,.4)', stats: makeStats(76, 80), passive: { name: 'Cloud Recovery', description: 'One extra life per run.', codeSnippet: 'cloud.failover({ retries: 1 });' } },
  { id: 'mira', name: 'Mira Chen', title: 'Robotics sprint captain', description: 'A nimble robotics specialist with a higher jump arc.', rarity: 'Epic', unlocked: false, unlockCost: 560, image: imageAlt, accentColor: '#00E5FF', glowColor: 'rgba(0,229,255,.4)', stats: makeStats(84, 94), passive: { name: 'Servo Leap', description: 'Jump height is increased.', codeSnippet: 'servo.jump({ height: 1.15 });' } },
  { id: 'dev', name: 'Dev Patel', title: 'Data pipeline dasher', description: 'A quick collector who makes every coin count.', rarity: 'Rare', unlocked: false, unlockCost: 680, image, accentColor: '#14B8A6', glowColor: 'rgba(20,184,166,.4)', stats: makeStats(86, 82), passive: { name: 'Pipeline Yield', description: 'Coins are worth more.', codeSnippet: 'pipeline.flush({ yield: "+1" });' } },
  { id: 'ada', name: 'Ada Okafor', title: 'Neural net navigator', description: 'A powerful heavy runner with an extended slide window.', rarity: 'Mythic', unlocked: false, unlockCost: 820, image: imageAlt, accentColor: '#C792FF', glowColor: 'rgba(199,146,255,.4)', stats: makeStats(88, 88), passive: { name: 'Neural Glide', description: 'Slides last longer.', codeSnippet: 'neural.slide({ duration: 1.3 });' } },
]
