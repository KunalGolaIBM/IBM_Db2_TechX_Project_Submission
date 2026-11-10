import type { Character, Difficulty, Mode, Question } from './types'

export const characters: Character[] = [
  { id: 'nova', name: 'Nova', role: 'Signal Scout', color: '#55e6ff', accent: '#1260a5', unlocked: true },
  { id: 'orbit', name: 'Orbit', role: 'Pattern Pilot', color: '#a98cff', accent: '#5438a8', unlocked: true },
  { id: 'pixel', name: 'Pixel', role: 'Logic Runner', color: '#ffca6b', accent: '#a74c45', unlocked: true },
]

export const samplePacks: { id: string; title: string; description: string; questions: Question[] }[] = [
  {
    id: 'web-foundations',
    title: 'Web Foundations',
    description: 'Fast reps on the building blocks of the web.',
    questions: [
      { id: 'web-1', topic: 'HTML', difficulty: 'easy', question: 'Which element is used for the largest page heading?', options: ['<h1>', '<head>', '<title>'], correctIndex: 0, explanation: 'The h1 element represents the highest-level heading in a document.' },
      { id: 'web-2', topic: 'CSS', difficulty: 'easy', question: 'Which CSS property changes the text colour?', options: ['paint', 'color', 'ink'], correctIndex: 1, explanation: 'The color property sets the foreground colour of an element’s text.' },
      { id: 'web-3', topic: 'JavaScript', difficulty: 'normal', question: 'What does Array.map return?', options: ['A new transformed array', 'A single boolean', 'The original array only'], correctIndex: 0, explanation: 'map creates a new array by applying a function to each item.' },
      { id: 'web-4', topic: 'Accessibility', difficulty: 'normal', question: 'What should an icon-only button provide?', options: ['A hidden image', 'An accessible name', 'More animation'], correctIndex: 1, explanation: 'An accessible name lets assistive technology communicate the button’s purpose.' },
    ],
  },
  {
    id: 'ai-foundations',
    title: 'AI Foundations',
    description: 'Core concepts for curious builders.',
    questions: [
      { id: 'ai-1', topic: 'Embeddings', difficulty: 'easy', question: 'Which representation helps match related meanings in search?', options: ['Dense embeddings', 'Pixel coordinates', 'File sizes'], correctIndex: 0, explanation: 'Embeddings represent semantic relationships between pieces of information.' },
      { id: 'ai-2', topic: 'Models', difficulty: 'normal', question: 'What is a model’s training data?', options: ['Only its UI', 'Examples used to learn patterns', 'A browser cache'], correctIndex: 1, explanation: 'Training data provides examples from which a model learns patterns.' },
      { id: 'ai-3', topic: 'Safety', difficulty: 'hard', question: 'What is a useful first step before shipping AI output?', options: ['Skip review', 'Add evaluation and guardrails', 'Hide failures'], correctIndex: 1, explanation: 'Evaluation and guardrails help detect and reduce unsafe or unreliable behaviour.' },
    ],
  },
]

export const difficultySettings: Record<Difficulty, { speed: number; lives: number; multiplier: number; label: string }> = {
  Easy: { speed: 10, lives: 5, multiplier: 1, label: 'More time to think' },
  Normal: { speed: 13, lives: 3, multiplier: 1.25, label: 'The intended pace' },
  Hard: { speed: 16, lives: 2, multiplier: 1.6, label: 'For high-velocity learners' },
}

export const modeSettings: Record<Mode, { obstacleRate: number; label: string }> = {
  Explore: { obstacleRate: 0.32, label: 'Relaxed practice laps' },
  Flow: { obstacleRate: 0.5, label: 'Fast focus sessions' },
}
