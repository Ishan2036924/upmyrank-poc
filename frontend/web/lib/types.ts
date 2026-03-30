export interface ConceptMastery {
  concept_id: string
  subtopic: string
  mastery: number
  error_count: number
  attempt_count: number
  last_reviewed: string | null
  next_review_due: string | null
  // Knowledge Genome evolution fields
  irt_theta?: number                        // IRT ability estimate (0.0)
  forgetting_rate?: number                  // Ebbinghaus decay rate (0.3)
  error_pattern_array?: Record<string, number> // { 'sign_error': 3, 'wrong_formula': 1 }
  next_review_date?: string | null          // SM-2 spaced-repetition date
}

export interface SessionEvent {
  id: string
  student_id: string
  problem_id: string | null
  session_type: 'practice' | 'mock_test' | 'doubt'
  time_to_solve_seconds: number | null
  max_hint_level_used: number              // 0–3
  mistake_forensics_tag: string | null     // e.g. 'sign_error', 'wrong_formula'
  student_confidence_rating: number | null // 1–5
  give_up_flag: boolean
  panic_moment_indicator: boolean
  created_at: string
}

export interface TopicMastery {
  average: number
  concepts: ConceptMastery[]
}

export interface StudentGenome {
  student_id: string
  name: string
  exam_type: string
  target_year: number
  overall_mastery: number
  topic_mastery: Record<string, TopicMastery>
  weakest_concepts: ConceptMastery[]
  total_sessions: number
  resolved_sessions: number
}

export interface ChatMessage {
  id: string
  role: 'student' | 'tutor' | 'divider'
  content: string
  metadata?: {
    hint_level?: number
    analysis?: Record<string, unknown>
    verification?: VerificationResult
    out_of_scope?: boolean
    is_full_solution?: boolean
    mentor_mode?: string
    intent?: string
    doubt_block_id?: string
    doubt_block_number?: number
    doubt_block_topic?: string
    doubt_block_solved?: boolean
    is_forced_attempt?: boolean
    confidence?: 'low' | 'medium' | 'high'
  }
}

export interface StudySession {
  study_session_id: string
  started_at: string
  ended_at?: string | null
  doubt_count: number
}

export interface DoubtBlock {
  doubt_block_id: string
  topic: string | null
  hint_level: number
  solved: boolean
  summary: string | null
  started_at: string | null
  ended_at: string | null
  messages: Array<{ role: string; content: string }>
}

export interface ResumeResponse {
  study_session_id: string
  started_at: string
  ended_at: string | null
  doubt_count: number
  doubt_blocks: DoubtBlock[]
  active_block_id: string | null
}

export interface VerificationResult {
  verified: boolean
  confidence: number
  method: string
  errors: string[]
  flagged_for_review: boolean
}

export interface Problem {
  problem_id: string
  question_text: string
  question_latex: string
  topic: string
  subtopic: string
  difficulty: number
  options?: string[]   // MCQ options [A, B, C, D] — generated server-side
}

export interface SubmitResult {
  correct: boolean
  confidence: number
  verified_answer: string
  student_answer: string
  explanation: string
  concepts_tested: string[]
  verification_method: string
  flagged_for_review: boolean
  mastery_updates: Array<{
    concept_id: string
    new_mastery: number
    old_mastery: number
  }>
}
