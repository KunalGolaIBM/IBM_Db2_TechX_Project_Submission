export interface TopicPerformance {
  topic: string
  total_attempts: number
  correct_attempts: number
  accuracy: number
  current_difficulty: string
}

export interface LearningRecommendation {
  recommendation_id?: number
  weak_topics: string[]
  recommended_difficulty: string
  recommendation_text: string
  created_at?: string
}

export interface LearningDashboard {
  learner_id: string
  total_questions: number
  accuracy: number
  strongest_topics: string[]
  weakest_topics: string[]
  progress: TopicPerformance[]
  latest_recommendation?: LearningRecommendation | null
  online: boolean
}

export interface AttemptPayload {
  learner_id: string
  topic: string
  score: number
  difficulty: 'easy' | 'medium' | 'hard'
  questions_count: number
}

const apiBase = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!response.ok) throw new Error(`Learning service returned ${response.status}`)
  return response.json() as Promise<T>
}

export async function fetchDashboard(learnerId: string): Promise<LearningDashboard> {
  const raw = await request<{
    profile?: { strengths?: string; weaknesses?: string; preferred_difficulty?: string } | null
    history: Array<{ topic: string; score: number; difficulty: string; questions_count: number }>
    recommendations: Array<{ id?: number; topic: string; recommendation: string; difficulty: string; created_at?: string }>
  }>(`/dashboard/${encodeURIComponent(learnerId)}`)
  const progress = raw.history.map((item) => ({
    topic: item.topic,
    total_attempts: item.questions_count,
    correct_attempts: Math.round(item.questions_count * item.score / 100),
    accuracy: item.score / 100,
    current_difficulty: item.difficulty,
  }))
  const latest = raw.recommendations[0]
  const weakest = raw.profile?.weaknesses?.split(',').map((item) => item.trim()).filter(Boolean) ?? []
  const strongest = raw.profile?.strengths?.split(',').map((item) => item.trim()).filter(Boolean) ?? []
  return {
    learner_id: learnerId,
    total_questions: progress.reduce((total, item) => total + item.total_attempts, 0),
    accuracy: progress.length ? progress.reduce((total, item) => total + item.accuracy, 0) / progress.length : 0,
    strongest_topics: strongest,
    weakest_topics: weakest,
    progress,
    latest_recommendation: latest ? {
      recommendation_id: latest.id,
      weak_topics: latest.topic ? [latest.topic] : weakest,
      recommended_difficulty: latest.difficulty,
      recommendation_text: latest.recommendation,
      created_at: latest.created_at,
    } : null,
    online: true,
  }
}

export async function saveAttempt(payload: AttemptPayload): Promise<void> {
  await request('/attempts', { method: 'POST', body: JSON.stringify(payload) })
}

export async function fetchRecommendation(learnerId: string): Promise<LearningRecommendation> {
  const raw = await request<{ recommendations: Array<{ id?: number; topic: string; recommendation: string; difficulty: string; created_at?: string }> }>(`/recommendations/${encodeURIComponent(learnerId)}?limit=1`)
  const item = raw.recommendations[0]
  if (!item) throw new Error('No learning recommendation is available')
  return {
    recommendation_id: item.id,
    weak_topics: item.topic ? [item.topic] : [],
    recommended_difficulty: item.difficulty,
    recommendation_text: item.recommendation,
    created_at: item.created_at,
  }
}
