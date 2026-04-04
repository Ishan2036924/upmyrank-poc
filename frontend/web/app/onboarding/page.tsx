'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronRight, Check } from 'lucide-react'
import { useAuth } from '@/lib/auth'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ── Types ─────────────────────────────────────────────────────────────────────

type ClassLevel  = '11th' | '12th' | 'dropper'
type ExamType    = 'JEE_MAINS' | 'JEE_ADVANCED' | 'NEET'

const TOPICS = [
  'Kinematics', 'Laws of Motion', 'Work & Energy', 'Circular Motion',
  'Rotational Dynamics', 'Gravitation', 'Thermodynamics', 'Waves',
  'Electrostatics', 'Current Electricity', 'Magnetism',
  'Electromagnetic Induction', 'Optics', 'Modern Physics',
  'Semiconductors', 'Communication Systems',
]

const SCAFFOLDING_LABEL: Record<string, string> = {
  HIGH:   'Beginner',
  MEDIUM: 'Intermediate',
  LOW:    'Advanced',
}
const SCAFFOLDING_COLOR: Record<string, string> = {
  HIGH:   'bg-amber-100 text-amber-700 border-amber-200',
  MEDIUM: 'bg-blue-100 text-blue-700 border-blue-200',
  LOW:    'bg-emerald-100 text-emerald-700 border-emerald-200',
}
const STYLE_DESC: Record<string, string> = {
  analogy:  'use real-world analogies before formulas',
  formula:  'go straight to equations and derivations',
  example:  'work through solved examples step by step',
  visual:   'draw diagrams and think visually',
}

const LOADING_MESSAGES = [
  'Analysing your background…',
  'Mapping your weak areas…',
  'Building your learning profile…',
  'Setting up your AI tutor…',
]

// ── Animation ─────────────────────────────────────────────────────────────────

const EASE: [number, number, number, number] = [0.16, 1, 0.3, 1]
const slideIn = {
  initial:  { opacity: 0, x: 40, scale: 0.98 },
  animate:  { opacity: 1, x: 0,  scale: 1, transition: { duration: 0.45, ease: EASE } },
  exit:     { opacity: 0, x: -30, scale: 0.98, transition: { duration: 0.25 } },
}

// ── Sub-components ────────────────────────────────────────────────────────────

function OptionCard({
  label, selected, onClick,
}: { label: string; selected: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative flex-1 min-w-[120px] rounded-2xl border-2 px-5 py-4 text-sm font-semibold text-left transition-all duration-300 ease-out active:scale-[0.97] ${
        selected
          ? 'border-indigo-500 bg-indigo-50 text-indigo-700 shadow-sm shadow-indigo-100'
          : 'border-slate-200 bg-white/80 text-slate-700 hover:border-slate-300 hover:bg-white'
      }`}
    >
      {selected && (
        <span className="absolute top-2 right-2 w-4 h-4 rounded-full bg-indigo-500 flex items-center justify-center">
          <Check style={{ width: 9, height: 9 }} className="text-white" strokeWidth={3} />
        </span>
      )}
      {label}
    </button>
  )
}

function TopicChip({
  label, selected, onClick,
}: { label: string; selected: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-all duration-200 active:scale-95 ${
        selected
          ? 'border-indigo-400 bg-indigo-50 text-indigo-700'
          : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
      }`}
    >
      {label}
    </button>
  )
}

function ProgressBar({ step, total }: { step: number; total: number }) {
  return (
    <div className="w-full max-w-sm mx-auto mb-8">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Step {step} of {total}
        </span>
        <span className="text-xs text-slate-400">{Math.round((step / total) * 100)}%</span>
      </div>
      <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
        <motion.div
          className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 rounded-full"
          initial={{ width: 0 }}
          animate={{ width: `${(step / total) * 100}%` }}
          transition={{ duration: 0.5, ease: EASE }}
        />
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function OnboardingPage() {
  const router    = useRouter()
  const { token } = useAuth()

  const [step,       setStep]       = useState(1)
  const [direction,  setDirection]  = useState(1) // 1 = forward, -1 = back

  // Step 1
  const [classLevel,   setClassLevel]   = useState<ClassLevel | null>(null)
  const [prevMarks,    setPrevMarks]    = useState<string>('')

  // Step 2
  const [easyTopics, setEasyTopics] = useState<Set<string>>(new Set())
  const [hardTopics, setHardTopics] = useState<Set<string>>(new Set())

  // Step 3
  const [studyHours, setStudyHours] = useState(4)
  const [examType,   setExamType]   = useState<ExamType | null>(null)
  const [examDate,   setExamDate]   = useState('')

  // Step 4
  const [submitting,      setSubmitting]      = useState(false)
  const [loadingMsgIdx,   setLoadingMsgIdx]   = useState(0)
  const [personaResult,   setPersonaResult]   = useState<Record<string, unknown> | null>(null)
  const [submitError,     setSubmitError]     = useState<string | null>(null)

  const go = (n: number) => {
    setDirection(n > step ? 1 : -1)
    setStep(n)
  }

  const toggleEasy = (t: string) => {
    setEasyTopics((prev) => {
      const next = new Set(prev)
      if (next.has(t)) next.delete(t); else next.add(t)
      return next
    })
    // Remove from hard if added to easy
    setHardTopics((prev) => { const next = new Set(prev); next.delete(t); return next })
  }

  const toggleHard = (t: string) => {
    setHardTopics((prev) => {
      const next = new Set(prev)
      if (next.has(t)) next.delete(t); else next.add(t)
      return next
    })
    // Remove from easy if added to hard
    setEasyTopics((prev) => { const next = new Set(prev); next.delete(t); return next })
  }

  const canProceed1 = !!classLevel
  const canProceed3 = !!examType

  const handleSubmit = async () => {
    if (!token) { router.push('/auth/login'); return }
    setSubmitting(true)
    setSubmitError(null)

    // Cycle through loading messages
    const interval = setInterval(() => {
      setLoadingMsgIdx((i) => (i + 1) % LOADING_MESSAGES.length)
    }, 1200)

    try {
      const body = {
        class_level:          classLevel,
        physics_prev_marks:   prevMarks ? parseInt(prevMarks, 10) : null,
        easy_topics:          Array.from(easyTopics),
        hard_topics:          Array.from(hardTopics),
        study_hours_per_day:  studyHours,
        exam_type:            examType,
        exam_date:            examDate || null,
      }
      const res = await fetch(`${API_URL}/onboarding/submit`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setPersonaResult(data.persona_profile)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setSubmitError(msg)
    } finally {
      clearInterval(interval)
      setSubmitting(false)
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-gradient-to-br from-slate-50 via-white to-indigo-50/30">
      {/* Ambient orbs */}
      <div className="pointer-events-none fixed top-0 left-1/4 w-96 h-96 rounded-full bg-violet-100/30 blur-3xl" />
      <div className="pointer-events-none fixed bottom-0 right-1/4 w-80 h-80 rounded-full bg-indigo-100/40 blur-3xl" />

      <div className="relative w-full max-w-lg">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex w-12 h-12 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 items-center justify-center mb-3 shadow-lg shadow-indigo-200/50">
            <span className="text-2xl">🎓</span>
          </div>
          <p className="text-slate-500 text-sm">Let&apos;s set up your learning profile</p>
        </div>

        {step <= 3 && <ProgressBar step={step} total={3} />}

        <div className="bg-white/80 backdrop-blur-xl rounded-3xl border border-white/60 shadow-[0_8px_40px_rgb(0,0,0,0.06)] overflow-hidden">
          <AnimatePresence mode="wait">

            {/* ── STEP 1 — Academic background ─────────────────────────────── */}
            {step === 1 && (
              <motion.div key="s1" {...slideIn} className="p-8">
                <h2 className="text-xl font-bold text-slate-900 mb-1">What class are you in?</h2>
                <p className="text-sm text-slate-500 mb-6">This helps us calibrate difficulty and pacing.</p>

                <div className="flex gap-3 mb-7">
                  {(['11th', '12th', 'dropper'] as ClassLevel[]).map((c) => (
                    <OptionCard
                      key={c}
                      label={c === 'dropper' ? 'Dropper' : `Class ${c}`}
                      selected={classLevel === c}
                      onClick={() => setClassLevel(c)}
                    />
                  ))}
                </div>

                {classLevel && classLevel !== '11th' && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                      Previous Physics marks
                    </label>
                    <div className="flex items-center gap-3">
                      <input
                        type="number"
                        min={0}
                        max={100}
                        value={prevMarks}
                        onChange={(e) => setPrevMarks(e.target.value)}
                        placeholder="e.g. 68"
                        className="w-28 rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-800 placeholder-slate-400 outline-none transition focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300"
                      />
                      <span className="text-slate-500 text-sm font-medium">%</span>
                      <span className="text-xs text-slate-400 ml-1">(leave blank if unsure)</span>
                    </div>
                  </motion.div>
                )}

                <button
                  type="button"
                  onClick={() => go(2)}
                  disabled={!canProceed1}
                  className="mt-8 w-full flex items-center justify-center gap-2 rounded-2xl bg-slate-900 hover:bg-indigo-600 text-white font-semibold py-3.5 text-sm transition-all duration-300 ease-out hover:scale-[1.01] active:scale-[0.99] disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-slate-900/20 hover:shadow-indigo-500/30"
                >
                  Continue <ChevronRight style={{ width: 15, height: 15 }} />
                </button>
              </motion.div>
            )}

            {/* ── STEP 2 — Topic assessment ─────────────────────────────────── */}
            {step === 2 && (
              <motion.div key="s2" {...slideIn} className="p-8">
                <h2 className="text-xl font-bold text-slate-900 mb-1">How are you with these topics?</h2>
                <p className="text-sm text-slate-500 mb-5">Select topics that feel easy, then which feel hardest. You can skip if unsure.</p>

                <div className="mb-5">
                  <p className="text-xs font-semibold text-emerald-600 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" /> Feels easy
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {TOPICS.map((t) => (
                      <TopicChip
                        key={`easy-${t}`}
                        label={t}
                        selected={easyTopics.has(t)}
                        onClick={() => toggleEasy(t)}
                      />
                    ))}
                  </div>
                </div>

                <div className="mb-6">
                  <p className="text-xs font-semibold text-rose-500 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-rose-400 inline-block" /> Feels hardest
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {TOPICS.map((t) => (
                      <TopicChip
                        key={`hard-${t}`}
                        label={t}
                        selected={hardTopics.has(t)}
                        onClick={() => toggleHard(t)}
                      />
                    ))}
                  </div>
                </div>

                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => go(1)}
                    className="flex-1 rounded-2xl border border-slate-200 bg-white text-slate-600 font-semibold py-3 text-sm transition-all hover:bg-slate-50 active:scale-[0.99]"
                  >
                    Back
                  </button>
                  <button
                    type="button"
                    onClick={() => go(3)}
                    className="flex-[2] flex items-center justify-center gap-2 rounded-2xl bg-slate-900 hover:bg-indigo-600 text-white font-semibold py-3 text-sm transition-all duration-300 ease-out hover:scale-[1.01] active:scale-[0.99] shadow-lg shadow-slate-900/20"
                  >
                    Continue <ChevronRight style={{ width: 15, height: 15 }} />
                  </button>
                </div>
              </motion.div>
            )}

            {/* ── STEP 3 — Study plan ───────────────────────────────────────── */}
            {step === 3 && (
              <motion.div key="s3" {...slideIn} className="p-8">
                <h2 className="text-xl font-bold text-slate-900 mb-1">Your study plan</h2>
                <p className="text-sm text-slate-500 mb-6">Help us understand your schedule and target.</p>

                <div className="mb-6">
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                    Daily study hours
                  </label>
                  <div className="flex items-center gap-4">
                    <input
                      type="range"
                      min={1}
                      max={12}
                      step={0.5}
                      value={studyHours}
                      onChange={(e) => setStudyHours(parseFloat(e.target.value))}
                      className="flex-1 h-2 rounded-full accent-indigo-500 cursor-pointer"
                    />
                    <span className="w-16 text-right text-sm font-bold text-slate-900">
                      {studyHours}h / day
                    </span>
                  </div>
                  <div className="flex justify-between text-[10px] text-slate-400 mt-1 px-0.5">
                    <span>1h</span><span>6h</span><span>12h</span>
                  </div>
                </div>

                <div className="mb-6">
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                    Target exam
                  </label>
                  <div className="flex gap-3">
                    {([
                      { id: 'JEE_MAINS',    label: 'JEE Mains'    },
                      { id: 'JEE_ADVANCED', label: 'JEE Advanced' },
                      { id: 'NEET',         label: 'NEET'          },
                    ] as { id: ExamType; label: string }[]).map((e) => (
                      <OptionCard
                        key={e.id}
                        label={e.label}
                        selected={examType === e.id}
                        onClick={() => setExamType(e.id)}
                      />
                    ))}
                  </div>
                </div>

                <div className="mb-7">
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                    Exam date <span className="normal-case font-normal text-slate-400">(optional)</span>
                  </label>
                  <input
                    type="date"
                    value={examDate}
                    onChange={(e) => setExamDate(e.target.value)}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-800 outline-none transition focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300"
                  />
                </div>

                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => go(2)}
                    className="flex-1 rounded-2xl border border-slate-200 bg-white text-slate-600 font-semibold py-3 text-sm transition-all hover:bg-slate-50 active:scale-[0.99]"
                  >
                    Back
                  </button>
                  <button
                    type="button"
                    onClick={() => { go(4); handleSubmit() }}
                    disabled={!canProceed3}
                    className="flex-[2] flex items-center justify-center gap-2 rounded-2xl bg-slate-900 hover:bg-indigo-600 text-white font-semibold py-3 text-sm transition-all duration-300 ease-out hover:scale-[1.01] active:scale-[0.99] disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-slate-900/20"
                  >
                    Build my profile <ChevronRight style={{ width: 15, height: 15 }} />
                  </button>
                </div>
              </motion.div>
            )}

            {/* ── STEP 4 — Processing & summary ────────────────────────────── */}
            {step === 4 && (
              <motion.div key="s4" {...slideIn} className="p-8 min-h-[340px] flex flex-col items-center justify-center text-center">
                {submitting && !personaResult && (
                  <>
                    <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center mb-5 shadow-lg shadow-indigo-200/50">
                      <motion.span
                        animate={{ rotate: 360 }}
                        transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                        className="text-2xl inline-block"
                      >
                        ⚙️
                      </motion.span>
                    </div>
                    <AnimatePresence mode="wait">
                      <motion.p
                        key={loadingMsgIdx}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        transition={{ duration: 0.3 }}
                        className="text-slate-700 font-medium text-sm"
                      >
                        {LOADING_MESSAGES[loadingMsgIdx]}
                      </motion.p>
                    </AnimatePresence>
                    <p className="text-xs text-slate-400 mt-2">This takes a few seconds…</p>
                  </>
                )}

                {submitError && (
                  <div className="w-full">
                    <div className="rounded-2xl bg-red-50 border border-red-100 px-5 py-4 text-sm text-red-600 mb-5 text-left">
                      {submitError}
                    </div>
                    <button
                      type="button"
                      onClick={() => { setSubmitError(null); go(3) }}
                      className="w-full rounded-2xl border border-slate-200 bg-white text-slate-700 font-semibold py-3 text-sm transition hover:bg-slate-50"
                    >
                      Go back and try again
                    </button>
                  </div>
                )}

                {personaResult && !submitting && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.5, ease: EASE }}
                    className="w-full text-left"
                  >
                    {(() => {
                      // Extract typed values once — personaResult is Record<string,unknown>
                      const level        = String(personaResult.scaffolding_level ?? 'HIGH')
                      const style        = String(personaResult.preferred_style   ?? 'analogy')
                      const summary      = String(personaResult.persona_summary   ?? '')
                      const weakConcepts = Array.isArray(personaResult.weak_concepts)
                        ? (personaResult.weak_concepts as unknown[]).map(String)
                        : []
                      const badgeCls  = SCAFFOLDING_COLOR[level]  ?? 'bg-slate-100 text-slate-600 border-slate-200'
                      const levelLabel = SCAFFOLDING_LABEL[level] ?? level
                      const styleDesc  = STYLE_DESC[style]        ?? style

                      return (
                        <>
                          {/* Header */}
                          <div className="text-center mb-6">
                            <div className="text-3xl mb-3">🎉</div>
                            <h2 className="text-xl font-bold text-slate-900">Your profile is ready!</h2>
                            <p className="text-sm text-slate-500 mt-1">Here&apos;s how I&apos;ll teach you.</p>
                          </div>

                          {/* Level badge */}
                          <div className="flex items-center justify-between mb-4">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Level</span>
                            <span className={`px-3 py-1 rounded-full text-xs font-bold border ${badgeCls}`}>
                              {levelLabel}
                            </span>
                          </div>

                          {/* Teaching style */}
                          <div className="rounded-2xl bg-indigo-50/60 border border-indigo-100 px-4 py-3 mb-4">
                            <p className="text-xs font-semibold text-indigo-500 uppercase tracking-wider mb-1">Your AI tutor will…</p>
                            <p className="text-sm text-slate-700 font-medium">{styleDesc}</p>
                          </div>

                          {/* Weak concepts */}
                          {weakConcepts.length > 0 && (
                            <div className="mb-4">
                              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Priority topics</p>
                              <div className="flex flex-wrap gap-2">
                                {weakConcepts.slice(0, 3).map((c) => (
                                  <span key={c} className="px-3 py-1 rounded-full bg-rose-50 border border-rose-100 text-xs font-medium text-rose-600">
                                    {c.replace(/_/g, ' ')}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Summary */}
                          {summary && (
                            <div className="rounded-2xl bg-slate-50 border border-slate-100 px-4 py-3 mb-6">
                              <p className="text-xs text-slate-500 leading-relaxed">{summary}</p>
                            </div>
                          )}
                        </>
                      )
                    })()}

                    <button
                      type="button"
                      onClick={() => router.push('/')}
                      className="w-full flex items-center justify-center gap-2 rounded-2xl bg-slate-900 hover:bg-indigo-600 text-white font-semibold py-3.5 text-sm transition-all duration-300 ease-out hover:scale-[1.01] active:scale-[0.99] shadow-lg shadow-slate-900/20"
                    >
                      Let&apos;s begin <ChevronRight style={{ width: 15, height: 15 }} />
                    </button>
                  </motion.div>
                )}
              </motion.div>
            )}

          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
