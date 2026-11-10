export type Screen = 'menu' | 'game' | 'results' | 'dashboard'
export type Difficulty = 'Easy' | 'Normal' | 'Hard'
export type Mode = 'Explore' | 'Flow'

export interface Question {
  id: string
  topic: string
  difficulty: Lowercase<Difficulty>
  question: string
  options: [string, string, string]
  correctIndex: 0 | 1 | 2
  explanation: string
}

export interface Character {
  id: string
  name: string
  role: string
  color: string
  accent: string
  unlocked: boolean
}

export interface SessionStats {
  score: number
  coins: number
  correct: number
  answered: number
  bestStreak: number
  distance: number
}
