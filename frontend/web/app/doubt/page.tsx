'use client'

import { useEffect, useRef, useState, useCallback, Suspense } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { ArrowLeft, RotateCcw, Target, BookOpen } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import Sidebar from '@/components/Sidebar'
import ChatMessage from '@/components/ChatMessage'
import ChatInput from '@/components/ChatInput'
import ConfidenceMeter, { ConfidenceLevel } from '@/components/ConfidenceMeter'
import QuickActions from '@/components/QuickActions'
import SessionHeader from '@/components/SessionHeader'
import TypingIndicator from '@/components/TypingIndicator'
import AuthGuard from '@/components/AuthGuard'
import ErrorBoundary from '@/components/ErrorBoundary'
import ChatErrorFallback from '@/components/ChatErrorFallback'
import { apiPost } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { ChatMessage as ChatMessageType, ResumeResponse, DoubtBlock, VerificationResult } from '@/lib/types'

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
  const { studentId } = useAuth()

  // Read URL query params
  const searchParams  = useSearchParams()
  const subjectParam  = searchParams.get('subject') ?? 'Physics'  // from TopicTree navigation
  const chapterParam  = searchParams.get('chapter') ?? null        // e.g. "Rotational Dynamics"
  const topicLock     = searchParams.get('topic')   ?? null        // topic lock (from TopicTree or direct link)
  const quickDoubtQ   = searchParams.get('q')       ?? null        // from QuickDoubtFAB bottom sheet

  // Track whether we've auto-submitted the QuickDoubt question
  const quickDoubtFiredRef = useRef(false)

  // Study-session state
  const [studySessionId,  setStudySessionId]  = useState<string | null>(null)
  const [sessionStartedAt, setSessionStartedAt] = useState<string | null>(null)
  const [doubtCount,      setDoubtCount]      = useState(0)
  // True once session init completes (start or resume). Blocks submit until ready
  // so every /doubt/ask always carries a study_session_id (prevents orphaned sessions).
  const [sessionReady,    setSessionReady]    = useState(false)

  // Chat state
  const [messages,          setMessages]          = useState<ChatMessageType[]>([])
  const [currentBlockId,    setCurrentBlockId]    = useState<string | null>(null)
  const [currentBlockSolved, setCurrentBlockSolved] = useState(false)
  const [isLoading,         setIsLoading]         = useState(false)
  const [chatError,         setChatError]         = useState<string | null>(null)

  // Current block metadata (for top-bar display + mastery update)
  const [sessionId,  setSessionId]  = useState<string | null>(null) // doubt_session_id
  const [analysis,   setAnalysis]   = useState<Record<string, unknown> | null>(null)
  const [mentorMode, setMentorMode] = useState<string | null>(null)

  // ── Confidence meter intercept ─────────────────────────────────────────────
  const [showConfidenceMeter, setShowConfidenceMeter] = useState(false)
  const [pendingAnswer,       setPendingAnswer]       = useState<string | null>(null)
  const [pendingImageUrl,     setPendingImageUrl]     = useState<string | null>(null)

  // ── Full solution attempt gate ─────────────────────────────────────────────
  const [showAttemptBox, setShowAttemptBox] = useState(false)
  const [attemptText,    setAttemptText]    = useState('')

  const bottomRef       = useRef<HTMLDivElement>(null)
  const inputRef        = useRef<HTMLTextAreaElement>(null)
  const studySessionRef = useRef<string | null>(null)
  const lastSendRef     = useRef<{ text: string; imageUrl?: string } | null>(null)

  // Keep ref in sync so sendBeacon closure is always fresh
  useEffect(() => { studySessionRef.current = studySessionId }, [studySessionId])

  // ── ON MOUNT: init or resume study session ─────────────────────────────────
  useEffect(() => {
    let cancelled = false

    async function startFresh() {
      const res = await apiPost('/session/start', { student_id: studentId })
      if (cancelled) return
      const startedAt = res.started_at ?? new Date().toISOString()
      saveSession(res.study_session_id, startedAt)
      setStudySessionId(res.study_session_id)
      setSessionStartedAt(startedAt)
      setSessionReady(true)
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
        setSessionReady(true)

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

    init().catch((err) => { console.error(err); setSessionReady(true) })
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

  // ── Auto-submit QuickDoubt question once session is ready ─────────────────
  useEffect(() => {
    if (
      quickDoubtQ &&
      !quickDoubtFiredRef.current &&
      studySessionId &&
      !isLoading
    ) {
      quickDoubtFiredRef.current = true
      handleSend(quickDoubtQ)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quickDoubtQ, studySessionId])

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
    const text     = pendingAnswer
    const imageUrl = pendingImageUrl
    setPendingAnswer(null)
    setPendingImageUrl(null)
    setShowConfidenceMeter(false)
    if (!text && !imageUrl) return

    // Add student message with confidence badge
    addMessage({
      role: 'student',
      content: text ?? '',
      metadata: {
        confidence:    level,
        doubt_block_id: currentBlockId ?? undefined,
        image_url:     imageUrl ?? undefined,
      },
    })
    setIsLoading(true)
    setChatError(null)

    try {
      const res = await apiPost('/doubt/ask', {
        question:           text || undefined,
        image_url:          imageUrl || undefined,
        student_id:         studentId,
        subject:            subjectParam,
        study_session_id:   studySessionId ?? undefined,
        student_confidence: level,
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
      setChatError(msg)
    } finally {
      setIsLoading(false)
    }
  }

  // ── Primary send handler ───────────────────────────────────────────────────
  const handleSend = async (text: string, imageUrl?: string) => {
    if (isLoading) return

    // Record last send for error retry
    lastSendRef.current = { text, imageUrl }
    setChatError(null)

    const jumpToFull = GIVE_UP_RE.test(text)

    // ── CONFIDENCE METER INTERCEPT ────────────────────────────────────────
    // When the tutor has issued a FORCED_ATTEMPT (max hints reached), intercept
    // the student's submission to capture their confidence level before sending.
    if (forcedAttemptActive && !jumpToFull) {
      setPendingAnswer(text)
      setPendingImageUrl(imageUrl ?? null)
      setShowConfidenceMeter(true)
      return
    }

    // Optimistic user message
    addMessage({
      role: 'student',
      content: text,
      metadata: {
        doubt_block_id: currentBlockId ?? undefined,
        image_url:      imageUrl ?? undefined,
      },
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

      // All messages → POST /doubt/ask. TypingIndicator shown while isLoading.
      const wasBlockSolved = currentBlockSolved
      const wasBlockId     = currentBlockId

      const res = await apiPost('/doubt/ask', {
        question:         text || undefined,
        image_url:        imageUrl || undefined,
        student_id:       studentId,
        subject:          subjectParam,
        study_session_id: studySessionId ?? undefined,
        ...(topicLock ? { topic_lock: topicLock } : {}),
      })

      const intent: string = res.intent ?? 'continuation'

      if (intent === 'physics_doubt') {
        // Insert divider if transitioning from a solved block
        if (wasBlockSolved && wasBlockId) {
          addMessage({
            role: 'divider',
            content: '',
            metadata: {
              doubt_block_number: doubtCount,
              doubt_block_topic:  (analysis?.topic as string | undefined) ?? 'Physics',
              doubt_block_solved: true,
              doubt_block_id:     wasBlockId,
            },
          })
        }
        setCurrentBlockSolved(false)
        setDoubtCount((c) => c + 1)
        if (res.session_id)      setSessionId(res.session_id)
        if (res.doubt_block_id)  setCurrentBlockId(res.doubt_block_id)
        if (res.analysis)        setAnalysis(res.analysis)
        if (res.mentor_mode)     setMentorMode(res.mentor_mode)
        addMessage({
          role: 'tutor',
          content: res.response ?? res.hint ?? JSON.stringify(res),
          metadata: {
            analysis:       res.analysis,
            out_of_scope:   Boolean(res.out_of_scope),
            mentor_mode:    res.mentor_mode ?? undefined,
            intent:         'physics_doubt',
            doubt_block_id: res.doubt_block_id ?? undefined,
          },
        })
      } else if (intent === 'continuation') {
        if (res.session_id)  setSessionId(res.session_id)
        if (res.mentor_mode) setMentorMode(res.mentor_mode)
        if (res.resolved)    setCurrentBlockSolved(true)
        addMessage({
          role: 'tutor',
          content: res.hint ?? res.response ?? JSON.stringify(res),
          metadata: {
            hint_level:        res.hint_level,
            verification:      res.verification as VerificationResult | undefined,
            is_full_solution:  Boolean(res.resolved ?? res.is_full_solution),
            is_forced_attempt: Boolean(res.is_forced_attempt),
            mentor_mode:       res.mentor_mode ?? undefined,
            intent:            'continuation',
            doubt_block_id:    (res.doubt_block_id ?? currentBlockId ?? undefined),
          },
        })
      } else if (intent === 'conversational') {
        // Don't start a new session — just prompt them to ask a question
        addMessage({
          role: 'tutor',
          content: res.response ?? `Ask me a ${subjectParam} question and I'll guide you through it step by step! 🎓`,
        })
      } else {
        // greeting, meta, emotional, out_of_scope, recap, explanation
        addMessage({ role: 'tutor', content: res.response ?? res.hint ?? JSON.stringify(res) })
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setChatError(msg)
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

  // ── Quick action: "Show full solution" — gated by attempt box ───────────
  const handleFullSolution = () => {
    if (!sessionId || isLoading) return
    setShowAttemptBox(true)
  }

  const handleAttemptSubmit = async () => {
    if (!sessionId || isLoading || attemptText.trim().length < 20) return
    setShowAttemptBox(false)
    setIsLoading(true)
    const attempt = attemptText.trim()
    setAttemptText('')

    // Show student's attempt as a message first
    addMessage({
      role: 'student',
      content: attempt,
      metadata: { doubt_block_id: currentBlockId ?? undefined },
    })

    try {
      const res = await apiPost('/doubt/hint', {
        session_id:            sessionId,
        student_response:      attempt,
        jump_to_full_solution: true,
        student_attempt:       attempt,
        study_session_id:      studySessionId ?? undefined,
      })
      const wasFull = res.is_full_solution ?? false
      addMessage({
        role: 'tutor',
        content: res.hint ?? res.response ?? JSON.stringify(res),
        metadata: {
          hint_level:        res.hint_level,
          verification:      res.verification ?? undefined,
          is_full_solution:  wasFull,
          is_forced_attempt: res.is_forced_attempt ?? false,
          mentor_mode:       res.mentor_mode ?? undefined,
          doubt_block_id:    res.doubt_block_id ?? currentBlockId ?? undefined,
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
  // Calls /doubt/hint with student_resolved=true so genome update fires properly
  const handleGotIt = async () => {
    if (isLoading || !sessionId) return
    setIsLoading(true)
    try {
      await apiPost('/doubt/hint', {
        session_id:       sessionId,
        student_resolved: true,
        study_session_id: studySessionId ?? undefined,
      })
      setCurrentBlockSolved(true)
      addMessage({
        role: 'tutor',
        content: '🎉 Great job! Your mastery has been updated. Ready for the next challenge?',
        metadata: {
          mentor_mode:    mentorMode ?? undefined,
          doubt_block_id: currentBlockId ?? undefined,
        },
      })
    } catch {
      setCurrentBlockSolved(true)
      addMessage({ role: 'tutor', content: '🎉 Nicely done! Keep going.' })
    } finally {
      setIsLoading(false)
    }
  }

  // ── Per-message thumbs feedback ───────────────────────────────────────────
  const handleFeedback = async (msgIdx: number, rating: 'thumbs_up' | 'thumbs_down') => {
    if (!sessionId) return
    // Optimistic update — toggle off if same rating clicked again
    setMessages(prev => prev.map((m, i) => {
      if (i !== msgIdx) return m
      const next = m.feedback === rating ? null : rating
      return { ...m, feedback: next }
    }))
    // Determine final rating from state (after optimistic update)
    const currentMsg = messages[msgIdx]
    const newRating = currentMsg.feedback === rating ? null : rating
    if (!newRating) return  // toggled off — no API call needed
    try {
      await apiPost('/feedback/response', {
        doubt_session_id: sessionId,
        response_idx:     msgIdx,
        rating:           newRating,
      })
    } catch {
      // Revert optimistic update on error
      setMessages(prev => prev.map((m, i) => {
        if (i !== msgIdx) return m
        return { ...m, feedback: currentMsg.feedback }
      }))
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
    <div className="flex h-[100dvh] p-3 gap-3 pt-[calc(56px+12px)] md:pt-3">
      <Sidebar />

      {/* ── Floating glassmorphic main window ─────────────────────────────── */}
      <div className="md:ml-[296px] flex-1 flex gap-3 min-w-0">

        {/* ── Center chat panel ─────────────────────────────────────────────── */}
        <div className="flex-1 flex flex-col bg-white/80 backdrop-blur-xl rounded-3xl border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] overflow-hidden min-w-0">

          {/* ── Top bar ─────────────────────────────────────────────────────── */}
          <div className="flex items-center gap-3 px-4 md:px-6 py-3 md:py-4 border-b border-slate-100 flex-shrink-0">
            <Link href="/" className="text-slate-400 hover:text-slate-700 transition-colors flex-shrink-0">
              <ArrowLeft className="h-5 w-5" />
            </Link>

            <div className="flex-1 min-w-0">
              {/* Topic-scoped header — shown when navigated from TopicTree */}
              {(chapterParam || topicLock) ? (
                <div className="flex items-center gap-2 flex-wrap">
                  {/* Subject badge */}
                  <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold flex-shrink-0 ${
                    subjectParam === 'Physics'   ? 'bg-blue-50 border-blue-200 text-blue-700' :
                    subjectParam === 'Chemistry' ? 'bg-emerald-50 border-emerald-200 text-emerald-700' :
                    subjectParam === 'Maths'     ? 'bg-violet-50 border-violet-200 text-violet-700' :
                                                   'bg-slate-100 border-slate-200 text-slate-600'
                  }`}>
                    {subjectParam}
                  </span>
                  {/* Chapter · Topic breadcrumb */}
                  <div className="flex items-center gap-1.5 min-w-0">
                    <BookOpen className="h-3.5 w-3.5 text-slate-400 flex-shrink-0" />
                    <span className="text-sm font-semibold text-slate-800 truncate">
                      {chapterParam && topicLock
                        ? `${chapterParam} · ${topicLock}`
                        : chapterParam || topicLock}
                    </span>
                  </div>
                  {/* Locked badge */}
                  <span className="rounded-full bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-xs text-indigo-700 font-medium flex items-center gap-1 flex-shrink-0">
                    <Target className="h-3 w-3" />
                    Focused
                  </span>
                </div>
              ) : (
                /* Generic header */
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-slate-800">Ask a doubt</span>
                  <span className="rounded-full bg-slate-100 border border-slate-200 px-2.5 py-0.5 text-xs text-slate-500 font-medium">
                    Socratic mode
                  </span>
                </div>
              )}
              {mentorMode && MENTOR_LABELS[mentorMode] && (
                <div className="mt-0.5">
                  <span className="rounded-full bg-violet-50 border border-violet-200 px-2.5 py-0.5 text-xs text-violet-600 font-medium">
                    {MENTOR_LABELS[mentorMode]}
                  </span>
                </div>
              )}
            </div>

            {analysis && (
              <div className="hidden md:flex items-center gap-2 flex-shrink-0">
                {(analysis as { subtopic?: string }).subtopic && (
                  <span className="rounded-full bg-blue-50 border border-blue-200 px-2.5 py-0.5 text-xs text-blue-600 font-medium">
                    {(analysis as { subtopic: string }).subtopic}
                  </span>
                )}
                {(analysis as { difficulty?: number }).difficulty != null && (
                  <span className="rounded-full bg-slate-100 border border-slate-200 px-2.5 py-0.5 text-xs text-slate-500">
                    Diff {(analysis as { difficulty: number }).difficulty}/10
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
                    ? `Focused on: ${topicLock}`
                    : `Your Socratic AI ${subjectParam} tutor`}
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
                    : subjectParam === 'Chemistry'
                    ? [
                        'Explain hybridization in organic compounds.',
                        'What is the difference between SN1 and SN2 reactions?',
                        'How does Le Chatelier\u2019s principle work?',
                        'Explain the periodic trends in ionization energy.',
                      ]
                    : subjectParam === 'Maths'
                    ? [
                        'How do I find the range of a function?',
                        'Explain integration by parts with an example.',
                        'What is the geometric meaning of a derivative?',
                        'How do I solve a system of linear equations?',
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

            {/* Message list — wrapped in ErrorBoundary for render errors */}
            <ErrorBoundary
              fallback={
                <ChatErrorFallback
                  error="Something went wrong displaying messages."
                  onRetry={() => window.location.reload()}
                />
              }
            >
              <AnimatePresence initial={false}>
                {messages.map((msg, i) => (
                  <ChatMessage
                    key={msg.id}
                    message={msg}
                    msgIdx={i}
                    isStreaming={false}
                    dimmed={
                      msg.role !== 'divider' &&
                      !!currentBlockId &&
                      !!msg.metadata?.doubt_block_id &&
                      msg.metadata.doubt_block_id !== currentBlockId
                    }
                    onFeedback={handleFeedback}
                  />
                ))}
              </AnimatePresence>
            </ErrorBoundary>

            {isLoading && <TypingIndicator />}

            {/* API error — retry UI */}
            {chatError && !isLoading && (
              <ChatErrorFallback
                error={chatError}
                onRetry={() => {
                  setChatError(null)
                  if (lastSendRef.current) {
                    handleSend(lastSendRef.current.text, lastSendRef.current.imageUrl)
                  }
                }}
              />
            )}

            {/* Attempt gate — shown when student clicks "Show full solution" */}
            <AnimatePresence>
              {showAttemptBox && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 4 }}
                  className="mt-3 mb-3 bg-amber-50/80 border border-amber-200/60 rounded-2xl p-4 backdrop-blur-sm"
                >
                  <p className="text-sm font-semibold text-amber-800 mb-1">
                    Write your attempt first
                  </p>
                  <p className="text-xs text-amber-600 mb-3">
                    Even a partial answer counts — this is how you actually learn. We won't judge.
                  </p>
                  <textarea
                    value={attemptText}
                    onChange={(e) => setAttemptText(e.target.value)}
                    placeholder="Write your working or where you're stuck…"
                    className="w-full text-sm bg-white/80 border border-amber-200 rounded-xl px-4 py-3 text-slate-800 placeholder-slate-400 outline-none resize-none focus:ring-2 focus:ring-amber-400/30 focus:border-amber-300"
                    rows={3}
                  />
                  <div className="flex items-center gap-3 mt-3">
                    <button
                      onClick={handleAttemptSubmit}
                      disabled={attemptText.trim().length < 20}
                      className="flex-1 rounded-xl bg-slate-900 hover:bg-amber-600 text-white text-sm font-semibold py-2.5 transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Submit &amp; See Solution
                      {attemptText.trim().length < 20 && attemptText.length > 0 && (
                        <span className="text-xs opacity-60 ml-1">
                          ({20 - attemptText.trim().length} more chars)
                        </span>
                      )}
                    </button>
                    <button
                      onClick={() => { setShowAttemptBox(false); setAttemptText('') }}
                      className="rounded-xl border border-slate-200 bg-white text-sm text-slate-500 px-4 py-2.5 hover:bg-slate-50 transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Quick actions */}
            {showQuickActions && !showAttemptBox && (
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
                  onSend={(text, imageUrl) => handleSend(text, imageUrl)}
                  disabled={isLoading || !sessionReady}
                  placeholder={
                    !sessionReady
                      ? 'Starting your session…'
                      : forcedAttemptActive
                      ? 'Write your full answer and working — I\'ll evaluate it…'
                      : currentBlockSolved
                        ? topicLock ? `Ask another question about ${topicLock}…` : `Ask a new ${subjectParam} question…`
                        : sessionId
                          ? 'Type your answer, or say "I got it" / "show solution"…'
                          : topicLock ? `Ask a question about ${topicLock}…` : `Ask a ${subjectParam} question…`
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
    <AuthGuard>
      <Suspense>
        <DoubtPageInner />
      </Suspense>
    </AuthGuard>
  )
}
