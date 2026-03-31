'use client'

import { useEffect, useRef, useState, useCallback, Suspense } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { ArrowLeft, RotateCcw, Target } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import Sidebar from '@/components/Sidebar'
import ChatMessage from '@/components/ChatMessage'
import ChatInput from '@/components/ChatInput'
import ConfidenceMeter, { ConfidenceLevel } from '@/components/ConfidenceMeter'
import QuickActions from '@/components/QuickActions'
import SessionHeader from '@/components/SessionHeader'
import TypingIndicator from '@/components/TypingIndicator'
import { apiPost } from '@/lib/api'
import { TEST_STUDENT_ID } from '@/lib/constants'
import { ChatMessage as ChatMessageType, ResumeResponse, DoubtBlock } from '@/lib/types'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const LS_SESSION_ID  = 'upmyrank_study_session_id'
const LS_STARTED_AT  = 'upmyrank_session_started_at'
const SESSION_TTL_MS = 2 * 60 * 60 * 1000 // 2 hours

const GIVE_UP_RE =
  /i give up|skip hints|show.*full solution|reveal.*answer|just give me the answer/i

const MENTOR_LABELS: Record<string, string> = {
  COACH:      '🏋️ Coach mode',
  TASKMASTER: '⚡ Taskmaster mode',
  COUNSELOR:  '🧘 Counselor mode',
  STRATEGIST: '🎯 Strategist mode',
}

// ── helpers ───────────────────────────────────────────────────────────────────

function nanoid() {
  return Math.random().toString(36).slice(2)
}

function getStoredSession(): { id: string; startedAt: string } | null {
  try {
    const id        = localStorage.getItem(LS_SESSION_ID)
    const startedAt = localStorage.getItem(LS_STARTED_AT)
    if (!id || !startedAt) return null
    if (Date.now() - new Date(startedAt).getTime() > SESSION_TTL_MS) {
      localStorage.removeItem(LS_SESSION_ID)
      localStorage.removeItem(LS_STARTED_AT)
      return null
    }
    return { id, startedAt }
  } catch {
    return null
  }
}

function saveSession(id: string, startedAt: string) {
  localStorage.setItem(LS_SESSION_ID,  id)
  localStorage.setItem(LS_STARTED_AT, startedAt)
}

function clearStoredSession() {
  localStorage.removeItem(LS_SESSION_ID)
  localStorage.removeItem(LS_STARTED_AT)
}

// ── Rebuild messages from resumed doubt blocks ────────────────────────────────
// When resuming, we show ALL blocks with dividers between them.

function rebuildMessages(blocks: DoubtBlock[]): ChatMessageType[] {
  const msgs: ChatMessageType[] = []
  blocks.forEach((block, idx) => {
    // Divider before every block during rebuild
    msgs.push({
      id: nanoid(),
      role: 'divider',
      content: '',
      metadata: {
        doubt_block_number: idx + 1,
        doubt_block_topic:  block.topic ?? 'Physics',
        doubt_block_solved: block.solved,
        doubt_block_id:     block.doubt_block_id,
      },
    })
    for (const m of block.messages) {
      msgs.push({
        id: nanoid(),
        role: m.role === 'student' ? 'student' : 'tutor',
        content: m.content,
        metadata: { doubt_block_id: block.doubt_block_id },
      })
    }
  })
  return msgs
}

// ── Page component ────────────────────────────────────────────────────────────

function DoubtPageInner() {
  // Read topic lock from URL query param (?topic=...)
  const searchParams = useSearchParams()
  const topicLock = searchParams.get('topic') ?? null

  // Study-session state
  const [studySessionId,  setStudySessionId]  = useState<string | null>(null)
  const [sessionStartedAt, setSessionStartedAt] = useState<string | null>(null)
  const [doubtCount,      setDoubtCount]      = useState(0)

  // Chat state
  const [messages,          setMessages]          = useState<ChatMessageType[]>([])
  const [currentBlockId,    setCurrentBlockId]    = useState<string | null>(null)
  const [currentBlockSolved, setCurrentBlockSolved] = useState(false)
  const [isLoading,         setIsLoading]         = useState(false)

  // Current block metadata (for top-bar display + mastery update)
  const [sessionId,  setSessionId]  = useState<string | null>(null) // doubt_session_id
  const [analysis,   setAnalysis]   = useState<Record<string, unknown> | null>(null)
  const [mentorMode, setMentorMode] = useState<string | null>(null)

  // ── Confidence meter intercept ─────────────────────────────────────────────
  const [showConfidenceMeter, setShowConfidenceMeter] = useState(false)
  const [pendingAnswer,       setPendingAnswer]       = useState<string | null>(null)

  const bottomRef       = useRef<HTMLDivElement>(null)
  const inputRef        = useRef<HTMLTextAreaElement>(null)
  const studySessionRef = useRef<string | null>(null)

  // Keep ref in sync so sendBeacon closure is always fresh
  useEffect(() => { studySessionRef.current = studySessionId }, [studySessionId])

  // ── ON MOUNT: init or resume study session ─────────────────────────────────
  useEffect(() => {
    let cancelled = false

    async function startFresh() {
      const res = await apiPost('/session/start', { student_id: TEST_STUDENT_ID })
      if (cancelled) return
      const startedAt = res.started_at ?? new Date().toISOString()
      saveSession(res.study_session_id, startedAt)
      setStudySessionId(res.study_session_id)
      setSessionStartedAt(startedAt)
    }

    async function init() {
      const stored = getStoredSession()
      if (!stored) {
        await startFresh()
        return
      }
      try {
        const res: ResumeResponse = await apiPost('/session/resume', {
          study_session_id: stored.id,
        })
        if (cancelled) return

        if (res.ended_at) {
          clearStoredSession()
          await startFresh()
          return
        }

        setStudySessionId(res.study_session_id)
        setSessionStartedAt(res.started_at)
        setDoubtCount(res.doubt_count)

        if (res.doubt_blocks.length > 0) {
          setMessages(rebuildMessages(res.doubt_blocks))

          if (res.active_block_id) {
            const active = res.doubt_blocks.find(
              (b) => b.doubt_block_id === res.active_block_id,
            )
            setCurrentBlockId(res.active_block_id)
            setCurrentBlockSolved(active?.solved ?? false)
          } else {
            // All blocks closed — point to the last one (read-only)
            const last = res.doubt_blocks[res.doubt_blocks.length - 1]
            if (last) {
              setCurrentBlockId(last.doubt_block_id)
              setCurrentBlockSolved(last.solved)
            }
          }
        }
      } catch {
        clearStoredSession()
        if (!cancelled) await startFresh()
      }
    }

    init().catch(console.error)
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── ON UNMOUNT + beforeunload: close study session ─────────────────────────
  useEffect(() => {
    const fire = () => {
      const sid = studySessionRef.current
      if (!sid) return
      navigator.sendBeacon(
        `${API_URL}/session/end`,
        new Blob([JSON.stringify({ study_session_id: sid })], {
          type: 'application/json',
        }),
      )
    }
    window.addEventListener('beforeunload', fire)
    return () => {
      window.removeEventListener('beforeunload', fire)
      fire() // also fires on SPA navigation away
    }
  }, [])

  // ── Scroll to bottom on new messages ──────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // ── Auto-focus input ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!isLoading && !currentBlockSolved) {
      setTimeout(() => inputRef.current?.focus(), 150)
    }
  }, [isLoading, currentBlockSolved])

  const addMessage = useCallback((msg: Omit<ChatMessageType, 'id'>) => {
    setMessages((prev) => [...prev, { ...msg, id: nanoid() }])
  }, [])

  // ── Derived: are we in a forced-attempt state? ────────────────────────────
  // True when the last message in the chat is the tutor's FORCED_ATTEMPT prompt.
  const lastMsg = messages[messages.length - 1]
  const forcedAttemptActive =
    !currentBlockSolved &&
    !!sessionId &&
    lastMsg?.role === 'tutor' &&
    lastMsg?.metadata?.is_forced_attempt === true

  // ── Confidence meter: called once user picks a level ─────────────────────
  const handleConfidenceSelect = async (level: ConfidenceLevel) => {
    const text = pendingAnswer
    setPendingAnswer(null)
    setShowConfidenceMeter(false)
    if (!text) return

    // Add student message with confidence badge
    addMessage({
      role: 'student',
      content: text,
      metadata: { confidence: level, doubt_block_id: currentBlockId ?? undefined },
    })
    setIsLoading(true)

    try {
      const res = await apiPost('/doubt/ask', {
        question:         text,
        student_id:       TEST_STUDENT_ID,
        subject:          'Physics',
        study_session_id: studySessionId ?? undefined,
        ...(topicLock ? { topic_lock: topicLock } : {}),
      })

      const intent: string = res.intent ?? 'continuation'

      if (intent === 'continuation' || intent === 'physics_doubt') {
        if (res.session_id)  setSessionId(res.session_id)
        if (res.mentor_mode) setMentorMode(res.mentor_mode)

        addMessage({
          role: 'tutor',
          content: res.hint ?? res.response ?? res.message ?? JSON.stringify(res),
          metadata: {
            hint_level:       res.hint_level,
            verification:     res.verification,
            is_full_solution: res.resolved ?? res.is_full_solution ?? false,
            is_forced_attempt: false,
            mentor_mode:      res.mentor_mode ?? undefined,
            doubt_block_id:   res.doubt_block_id ?? currentBlockId ?? undefined,
          },
        })
        if (res.resolved) setCurrentBlockSolved(true)
      } else {
        addMessage({ role: 'tutor', content: res.response ?? res.hint ?? JSON.stringify(res) })
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      addMessage({ role: 'tutor', content: `⚠️ Error: ${msg}` })
    } finally {
      setIsLoading(false)
    }
  }

  // ── Primary send handler ───────────────────────────────────────────────────
  const handleSend = async (text: string) => {
    if (isLoading) return

    const jumpToFull = GIVE_UP_RE.test(text)

    // ── CONFIDENCE METER INTERCEPT ────────────────────────────────────────
    // When the tutor has issued a FORCED_ATTEMPT (max hints reached), intercept
    // the student's submission to capture their confidence level before sending.
    if (forcedAttemptActive && !jumpToFull) {
      setPendingAnswer(text)
      setShowConfidenceMeter(true)
      return
    }

    // Optimistic user message
    addMessage({
      role: 'student',
      content: text,
      metadata: { doubt_block_id: currentBlockId ?? undefined },
    })
    setIsLoading(true)

    try {
      // Explicit give-up → call /doubt/hint directly with jump_to_full_solution
      // Backend may override jump_to_full if current_level < 3 (progressive
      // disclosure gate), so we MUST read is_full_solution from the response.
      if (jumpToFull && sessionId) {
        const res = await apiPost('/doubt/hint', {
          session_id:            sessionId,
          student_response:      text,
          jump_to_full_solution: true,
          study_session_id:      studySessionId ?? undefined,
        })
        const wasFull = res.is_full_solution ?? false
        addMessage({
          role: 'tutor',
          content: res.hint ?? res.response ?? JSON.stringify(res),
          metadata: {
            hint_level:       res.hint_level,
            verification:     res.verification,
            is_full_solution: wasFull,
            is_forced_attempt: res.is_forced_attempt ?? false,
            mentor_mode:      res.mentor_mode ?? undefined,
            doubt_block_id:   res.doubt_block_id ?? currentBlockId ?? undefined,
          },
        })
        if (res.mentor_mode) setMentorMode(res.mentor_mode)
        if (wasFull) setCurrentBlockSolved(true)
        return
      }

      // All other messages → /doubt/ask (intent-gated on backend)
      const res = await apiPost('/doubt/ask', {
        question:         text,
        student_id:       TEST_STUDENT_ID,
        subject:          'Physics',
        study_session_id: studySessionId ?? undefined,
        doubt_block_id:   currentBlockId ?? undefined,
        ...(topicLock ? { topic_lock: topicLock } : {}),
      })

      const intent: string = res.intent ?? 'physics_doubt'

      // ── Non-physics intents: append response, change nothing else ──────────
      if (['greeting', 'meta', 'emotional', 'out_of_scope'].includes(intent)) {
        addMessage({ role: 'tutor', content: res.response, metadata: { intent } })
        return
      }

      // ── New physics_doubt ──────────────────────────────────────────────────
      if (intent === 'physics_doubt') {
        const newBlockId  = res.doubt_block_id as string | null | undefined
        const newTopic    = (res.doubt_block_topic ?? res.analysis?.topic ?? 'Physics') as string

        //  Insert divider ONLY when transitioning from a solved block
        //  (first question: !currentBlockId → no divider)
        if (currentBlockSolved && currentBlockId) {
          addMessage({
            role: 'divider',
            content: '',
            metadata: {
              doubt_block_number: doubtCount,
              doubt_block_topic:  (analysis?.topic as string | undefined) ?? 'Physics',
              doubt_block_solved: true,
              doubt_block_id:     currentBlockId,
            },
          })
        }

        // Update block state
        if (res.session_id)   setSessionId(res.session_id)
        setCurrentBlockId(newBlockId ?? null)
        setCurrentBlockSolved(false)
        setDoubtCount((c) => c + 1)
        setAnalysis(res.analysis ?? null)
        if (res.mentor_mode) setMentorMode(res.mentor_mode)

        addMessage({
          role: 'tutor',
          content: res.response ?? res.message ?? JSON.stringify(res),
          metadata: {
            analysis:       res.analysis,
            out_of_scope:   res.out_of_scope ?? false,
            mentor_mode:    res.mentor_mode ?? undefined,
            intent,
            doubt_block_id: newBlockId ?? undefined,
          },
        })
        return
      }

      // ── Continuation ────────────────────────────────────────────────────────
      if (intent === 'continuation') {
        if (res.session_id)   setSessionId(res.session_id)
        if (res.mentor_mode)  setMentorMode(res.mentor_mode)

        addMessage({
          role: 'tutor',
          content: res.hint ?? res.response ?? res.message ?? JSON.stringify(res),
          metadata: {
            hint_level:       res.hint_level,
            verification:     res.verification,
            is_full_solution: res.resolved ?? false,
            is_forced_attempt: res.is_forced_attempt ?? false,
            mentor_mode:      res.mentor_mode ?? undefined,
            intent,
            doubt_block_id:   res.doubt_block_id ?? currentBlockId ?? undefined,
          },
        })
        if (res.resolved) setCurrentBlockSolved(true)
        return
      }

      // Fallback for any unexpected intent
      addMessage({
        role: 'tutor',
        content: res.response ?? res.hint ?? res.message ?? JSON.stringify(res),
        metadata: { intent },
      })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      addMessage({ role: 'tutor', content: `⚠️ Error: ${msg}` })
    } finally {
      setIsLoading(false)
    }
  }

  // ── Quick action: "I'm stuck – give me a hint" ────────────────────────────
  const handleHint = async () => {
    if (!sessionId || isLoading) return
    setIsLoading(true)
    try {
      const res = await apiPost('/doubt/hint', {
        session_id:       sessionId,
        student_response: null,
        study_session_id: studySessionId ?? undefined,
      })
      addMessage({
        role: 'tutor',
        content: res.hint ?? res.response ?? JSON.stringify(res),
        metadata: {
          hint_level:       res.hint_level,
          verification:     res.verification,
          is_full_solution: res.resolved ?? false,
          is_forced_attempt: res.is_forced_attempt ?? false,
          mentor_mode:      res.mentor_mode ?? undefined,
          doubt_block_id:   res.doubt_block_id ?? currentBlockId ?? undefined,
        },
      })
      if (res.mentor_mode) setMentorMode(res.mentor_mode)
      if (res.resolved)    setCurrentBlockSolved(true)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      addMessage({ role: 'tutor', content: `⚠️ Error: ${msg}` })
    } finally {
      setIsLoading(false)
    }
  }

  // ── Quick action: "Show full solution" ────────────────────────────────────
  const handleFullSolution = async () => {
    if (!sessionId || isLoading) return
    setIsLoading(true)
    try {
      const res = await apiPost('/doubt/hint', {
        session_id:            sessionId,
        student_response:      'Please show me the full solution.',
        jump_to_full_solution: true,
        study_session_id:      studySessionId ?? undefined,
      })
      const wasFull = res.is_full_solution ?? false
      addMessage({
        role: 'tutor',
        content: res.hint ?? res.response ?? JSON.stringify(res),
        metadata: {
          hint_level:       res.hint_level,
          verification:     res.verification ?? undefined,
          is_full_solution: wasFull,
          is_forced_attempt: res.is_forced_attempt ?? false,
          mentor_mode:      res.mentor_mode ?? undefined,
          doubt_block_id:   res.doubt_block_id ?? currentBlockId ?? undefined,
        },
      })
      if (res.mentor_mode) setMentorMode(res.mentor_mode)
      if (wasFull) setCurrentBlockSolved(true)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      addMessage({ role: 'tutor', content: `⚠️ Error: ${msg}` })
    } finally {
      setIsLoading(false)
    }
  }

  // ── Quick action: "I got it!" ─────────────────────────────────────────────
  const handleGotIt = async () => {
    if (isLoading) return
    setCurrentBlockSolved(true)
    try {
      const concepts: string[] =
        (analysis as { concepts_tested?: string[] } | null)?.concepts_tested ?? []
      await Promise.allSettled(
        concepts.map((cid) =>
          apiPost(`/student/${TEST_STUDENT_ID}/update-mastery`, {
            concept_id:        cid,
            performance_score: 1.0,
          }),
        ),
      )
      addMessage({
        role: 'tutor',
        content: '🎉 Great job! Your mastery has been updated. Ready for the next challenge?',
        metadata: {
          mentor_mode:    mentorMode ?? undefined,
          doubt_block_id: currentBlockId ?? undefined,
        },
      })
    } catch {
      addMessage({ role: 'tutor', content: '🎉 Nicely done! Keep going.' })
    }
  }

  // ── New question: reset block state but keep the study session ────────────
  const handleNewQuestion = () => {
    setSessionId(null)
    setCurrentBlockSolved(false)
    setAnalysis(null)
    setMentorMode(null)
    setShowConfidenceMeter(false)
    setPendingAnswer(null)
    setTimeout(() => inputRef.current?.focus(), 100)
  }

  // Quick-actions appear only above the last message of the current active block
  const showQuickActions =
    !!sessionId &&
    !currentBlockSolved &&
    !isLoading &&
    lastMsg?.role === 'tutor'

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen p-3 gap-3">
      <Sidebar />

      {/* ── Floating glassmorphic main window ─────────────────────────────── */}
      <div className="ml-[76px] flex-1 flex gap-3 min-w-0">

        {/* ── Center chat panel ─────────────────────────────────────────────── */}
        <div className="flex-1 flex flex-col bg-white/80 backdrop-blur-xl rounded-3xl border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] overflow-hidden min-w-0">

          {/* ── Top bar ─────────────────────────────────────────────────────── */}
          <div className="flex items-center gap-3 px-6 py-4 border-b border-slate-100 flex-shrink-0">
            <Link href="/" className="text-slate-400 hover:text-slate-700 transition-colors">
              <ArrowLeft className="h-5 w-5" />
            </Link>

            <div className="flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-slate-800">Ask a doubt</span>
                <span className="rounded-full bg-slate-100 border border-slate-200 px-2.5 py-0.5 text-xs text-slate-500 font-medium">
                  Socratic mode
                </span>
                {topicLock && (
                  <span className="rounded-full bg-indigo-50 border border-indigo-200 px-2.5 py-0.5 text-xs text-indigo-700 font-medium flex items-center gap-1">
                    <Target className="h-3 w-3" />
                    Locked to: {topicLock}
                  </span>
                )}
                {mentorMode && MENTOR_LABELS[mentorMode] && (
                  <span className="rounded-full bg-violet-50 border border-violet-200 px-2.5 py-0.5 text-xs text-violet-600 font-medium">
                    {MENTOR_LABELS[mentorMode]}
                  </span>
                )}
              </div>
            </div>

            {analysis && (
              <div className="flex items-center gap-2">
                {(analysis as { subtopic?: string }).subtopic && (
                  <span className="rounded-full bg-blue-50 border border-blue-200 px-2.5 py-0.5 text-xs text-blue-600 font-medium">
                    {(analysis as { subtopic: string }).subtopic}
                  </span>
                )}
                {(analysis as { difficulty?: number }).difficulty != null && (
                  <span className="rounded-full bg-slate-100 border border-slate-200 px-2.5 py-0.5 text-xs text-slate-500">
                    Difficulty {(analysis as { difficulty: number }).difficulty}/10
                  </span>
                )}
              </div>
            )}
          </div>

          {/* ── Session header ───────────────────────────────────────────────── */}
          {sessionStartedAt && (
            <SessionHeader startedAt={sessionStartedAt} doubtCount={doubtCount} />
          )}

          {/* ── Chat area ───────────────────────────────────────────────────── */}
          <div className="flex-1 overflow-y-auto px-6 py-6">

            {/* Empty state */}
            {messages.length === 0 && !isLoading && (
              <div className="flex flex-col items-center justify-center h-full text-center px-8">
                <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-violet-100 via-indigo-50 to-blue-100 flex items-center justify-center mb-6 shadow-[0_8px_30px_rgb(99,102,241,0.12)] ring-4 ring-white">
                  <span className="text-4xl">🎓</span>
                </div>
                <p className="text-slate-800 text-base mb-1.5 font-semibold tracking-tight">
                  {topicLock
                    ? `Locked to: ${topicLock}`
                    : 'Your Socratic AI Physics tutor'}
                </p>
                <p className="text-slate-400 text-sm mb-8 max-w-xs leading-relaxed">
                  {topicLock
                    ? `Ask anything about ${topicLock} — I\u2019ll guide you step by step without giving away the answer.`
                    : 'I won\u2019t just give you the answer. I\u2019ll ask the right questions until you find it yourself.'}
                </p>
                <div className="grid grid-cols-1 gap-2.5 w-full max-w-sm">
                  {(topicLock
                    ? [
                        `Explain ${topicLock} from first principles.`,
                        `What are the key formulas for ${topicLock}?`,
                        `Give me a JEE-level problem on ${topicLock}.`,
                        `What are common mistakes in ${topicLock}?`,
                      ]
                    : [
                        'Why does a ball thrown upward come back down?',
                        'What is the difference between speed and velocity?',
                        'How does a capacitor store charge?',
                        "Explain Newton\u2019s third law with an example.",
                      ]
                  ).map((q) => (
                    <button
                      key={q}
                      onClick={() => handleSend(q)}
                      className="text-left rounded-2xl border border-slate-100 bg-white/80 hover:border-indigo-200 hover:bg-indigo-50/50 px-5 py-3.5 text-sm text-slate-600 hover:text-slate-800 transition-all duration-300 ease-out active:scale-[0.98] shadow-[0_2px_8px_rgb(0,0,0,0.04)]"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Message list */}
            <AnimatePresence initial={false}>
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  dimmed={
                    msg.role !== 'divider' &&
                    !!currentBlockId &&
                    !!msg.metadata?.doubt_block_id &&
                    msg.metadata.doubt_block_id !== currentBlockId
                  }
                />
              ))}
            </AnimatePresence>

            {isLoading && <TypingIndicator />}

            {/* Quick actions */}
            {showQuickActions && (
              <motion.div
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-2 mb-3"
              >
                <p className="text-xs text-slate-400 mb-2 px-1 font-medium">Quick actions:</p>
                <QuickActions
                  onGotIt={handleGotIt}
                  onHint={handleHint}
                  onFullSolution={handleFullSolution}
                  disabled={isLoading}
                />
              </motion.div>
            )}

            {/* Block solved — next question prompt */}
            {currentBlockSolved && (
              <div className="flex justify-center mt-4">
                <button
                  onClick={handleNewQuestion}
                  className="flex items-center gap-2 rounded-full border border-slate-200 bg-white hover:bg-slate-50 px-5 py-2 text-sm text-slate-600 font-medium transition-colors shadow-sm"
                >
                  <RotateCcw className="h-4 w-4" />
                  New question
                </button>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* ── Input area — swaps between ChatInput and ConfidenceMeter ─────── */}
          <AnimatePresence mode="wait">
            {showConfidenceMeter ? (
              <ConfidenceMeter
                key="meter"
                onSelect={handleConfidenceSelect}
              />
            ) : (
              <motion.div
                key="input"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{    opacity: 0, y: 4 }}
                transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              >
                <ChatInput
                  ref={inputRef}
                  onSend={handleSend}
                  disabled={isLoading}
                  placeholder={
                    forcedAttemptActive
                      ? 'Write your full answer and working — I\'ll evaluate it…'
                      : currentBlockSolved
                        ? topicLock ? `Ask another question about ${topicLock}…` : 'Ask a new Physics question…'
                        : sessionId
                          ? 'Type your answer, or say "I got it" / "show solution"…'
                          : topicLock ? `Ask a question about ${topicLock}…` : 'Ask a Physics question…'
                  }
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* ── Right stats sidebar ──────────────────────────────────────────── */}
        <div className="hidden lg:flex flex-col w-[240px] flex-shrink-0 gap-3">
          {/* Session stats card */}
          <div className="bg-white/80 backdrop-blur-xl rounded-3xl border border-white/60 shadow-xl shadow-slate-200/40 p-5">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Session</p>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Doubts asked</span>
                <span className="text-sm font-bold text-slate-800">{doubtCount}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Current block</span>
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${currentBlockSolved ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600'}`}>
                  {currentBlockSolved ? 'Solved' : currentBlockId ? 'Active' : 'Idle'}
                </span>
              </div>
              {analysis && (analysis as { topic?: string }).topic && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500">Topic</span>
                  <span className="text-xs font-medium text-slate-700 text-right max-w-[120px] truncate">
                    {(analysis as { topic: string }).topic}
                  </span>
                </div>
              )}
              {analysis && (analysis as { difficulty?: number }).difficulty != null && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500">Difficulty</span>
                  <span className="text-xs font-medium text-slate-700">
                    {(analysis as { difficulty: number }).difficulty}/10
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Hint card */}
          <div className="bg-gradient-to-br from-violet-50 to-indigo-50 rounded-3xl border border-violet-100 p-5">
            <p className="text-xs font-semibold text-violet-500 uppercase tracking-wider mb-2">Tip</p>
            <p className="text-xs text-slate-600 leading-relaxed">
              Try to work through each step before asking for a hint — it builds deeper understanding.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function DoubtPage() {
  return (
    <Suspense>
      <DoubtPageInner />
    </Suspense>
  )
}
