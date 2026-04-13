'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Lock, Timer, ChevronRight } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import Sidebar from '@/components/Sidebar'
import MathText from '@/components/MathText'
import PostMortem from '@/components/PostMortem'
import { apiPost } from '@/lib/api'
import { Problem, SubmitResult } from '@/lib/types'
import AuthGuard from '@/components/AuthGuard'
import { useAuth } from '@/lib/auth'

type Phase = 'setup' | 'test' | 'done'

interface QuestionRecord {
  problem: Problem
  result: SubmitResult | null
  answer: string
  timeTaken: number
}

const TOPIC_OPTIONS = ['All', 'Mechanics', 'Thermodynamics', 'Electrostatics', 'Optics', 'Modern Physics']
const DIFFICULTY_OPTIONS = [
  { label: 'Mixed', value: null },
  { label: 'Easy', value: 0.2 },
  { label: 'Medium', value: 0.5 },
  { label: 'Hard', value: 0.8 },
]
const MCQ_LABELS = ['A', 'B', 'C', 'D']

export default function MockPage() {
  const { studentId } = useAuth()
  const [phase, setPhase] = useState<Phase>('setup')
  const [numQuestions, setNumQuestions] = useState(10)
  const [topic, setTopic] = useState('All')
  const [difficultyIdx, setDifficultyIdx] = useState(0)

  const [records, setRecords] = useState<QuestionRecord[]>([])
  const [currentProblem, setCurrentProblem] = useState<Problem | null>(null)
  const [selectedOption, setSelectedOption] = useState<string | null>(null)
  const [answeredMap, setAnsweredMap] = useState<Record<number, string>>({})
  const [questionNum, setQuestionNum] = useState(1)
  const [submitting, setSubmitting] = useState(false)
  const [loadingQ, setLoadingQ] = useState(false)

  const totalSeconds = numQuestions * 120
  const [secondsLeft, setSecondsLeft] = useState(totalSeconds)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const startTimeRef = useRef<number>(0)

  useEffect(() => {
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [])

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  const loadQuestion = async () => {
    setLoadingQ(true)
    setSelectedOption(null)
    startTimeRef.current = Date.now()
    try {
      const difficulty = DIFFICULTY_OPTIONS[difficultyIdx].value
      const q = await apiPost('/mock/generate', {
        subject: 'Physics',
        topic: topic !== 'All' ? topic : undefined,
        difficulty,
      })
      setCurrentProblem(q)
    } catch (e) {
      console.error(e)
    } finally {
      setLoadingQ(false)
    }
  }

  const startTest = async () => {
    setPhase('test')
    setRecords([])
    setQuestionNum(1)
    setAnsweredMap({})
    setSecondsLeft(totalSeconds)
    timerRef.current = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) { clearInterval(timerRef.current!); finishTest(); return 0 }
        return s - 1
      })
    }, 1000)
    await loadQuestion()
  }

  const finishTest = () => {
    if (timerRef.current) clearInterval(timerRef.current)
    setPhase('done')
  }

  const handleSubmitAndNext = async () => {
    if (!currentProblem || submitting) return
    const timeTaken = Math.round((Date.now() - startTimeRef.current) / 1000)
    const answerText = selectedOption ?? ''
    setSubmitting(true)
    let result: SubmitResult | null = null
    try {
      if (answerText) {
        result = await apiPost('/mock/submit', {
          problem_id: currentProblem.problem_id,
          answer: answerText,
          student_id: studentId,
        })
      }
    } catch (e) {
      console.error(e)
    } finally {
      setSubmitting(false)
    }
    if (answerText) setAnsweredMap((prev) => ({ ...prev, [questionNum]: answerText }))
    const newRecord: QuestionRecord = { problem: currentProblem, result, answer: answerText, timeTaken }
    const newRecords = [...records, newRecord]
    setRecords(newRecords)
    if (questionNum >= numQuestions) {
      if (timerRef.current) clearInterval(timerRef.current)
      setPhase('done')
    } else {
      setQuestionNum((n) => n + 1)
      await loadQuestion()
    }
  }

  const timerWarning = secondsLeft < 60
  const timerCritical = secondsLeft < 30

  // ── Phase: done ──────────────────────────────────────────────────────────────
  if (phase === 'done') {
    return (
      <AuthGuard>
      <div className="flex h-[100dvh]">
        <Sidebar />
        <div className="md:ml-[236px] flex-1 overflow-y-auto pt-14 md:pt-0">
          <PostMortem
            records={records}
            onRetake={() => setPhase('setup')}
            onPracticeWeak={() => window.location.href = '/practice'}
          />
        </div>
      </div>
      </AuthGuard>
    )
  }

  // ── Phase: test ──────────────────────────────────────────────────────────────
  if (phase === 'test') {
    return (
      <AuthGuard>
      <div className="flex h-[100dvh]">
        <Sidebar />
        <div className="md:ml-[236px] flex-1 flex overflow-hidden">

          {/* LEFT PANE: Question */}
          <div className="flex-1 flex flex-col overflow-hidden border-r border-slate-100">

            {/* Top bar */}
            <div className="flex-shrink-0 flex items-center justify-between px-6 py-3 border-b border-slate-100 bg-white/80 backdrop-blur-md">
              <div className="flex items-center gap-3">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Mock Test</span>
                <span className="text-slate-300">·</span>
                <span className="text-xs text-slate-400">Q{questionNum} of {numQuestions}</span>
              </div>
              <div className="flex-1 mx-6 max-w-xs h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500 rounded-full transition-all duration-300"
                  style={{ width: `${((questionNum - 1) / numQuestions) * 100}%` }}
                />
              </div>
              {currentProblem && (
                <span className="text-xs text-slate-500 bg-slate-100 border border-slate-200 rounded-full px-2.5 py-1">
                  {currentProblem.subtopic}
                </span>
              )}
            </div>

            {/* Question body */}
            <div className="flex-1 overflow-y-auto px-8 py-8">
              <AnimatePresence mode="wait">
                {loadingQ ? (
                  <motion.div
                    key="loading"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="flex flex-col items-center justify-center h-64 gap-3"
                  >
                    <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                    <span className="text-slate-400 text-sm">Loading question…</span>
                  </motion.div>
                ) : currentProblem ? (
                  <motion.div
                    key={currentProblem.problem_id}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    transition={{ duration: 0.2 }}
                  >
                    <div className="flex items-center gap-3 mb-6">
                      <div className="w-8 h-8 rounded-full bg-indigo-50 border border-indigo-200 flex items-center justify-center text-xs font-bold text-indigo-600">
                        {questionNum}
                      </div>
                      <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                        {currentProblem.topic}
                      </span>
                    </div>
                    <div className="text-slate-800 text-base leading-relaxed">
                      <MathText>{currentProblem.question_text}</MathText>
                    </div>
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </div>
          </div>

          {/* RIGHT PANE: Timer + MCQ + Nav */}
          <div className="w-[340px] flex-shrink-0 flex flex-col bg-white/80 backdrop-blur-md border-l border-slate-100 overflow-y-auto">

            {/* Timer */}
            <div className={`flex-shrink-0 flex flex-col items-center justify-center py-6 border-b border-slate-100 ${
              timerCritical ? 'bg-red-50' : timerWarning ? 'bg-amber-50' : ''
            }`}>
              <div className="flex items-center gap-2 mb-1">
                <Timer className={`h-4 w-4 ${timerCritical ? 'text-red-500 animate-pulse' : timerWarning ? 'text-amber-500' : 'text-slate-400'}`} />
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Time Left</span>
              </div>
              <div className={`text-5xl font-mono font-bold tabular-nums ${
                timerCritical ? 'text-red-500' : timerWarning ? 'text-amber-500' : 'text-slate-800'
              }`}>
                {formatTime(secondsLeft)}
              </div>
            </div>

            {/* MCQ Options */}
            <div className="flex-shrink-0 px-4 py-5 border-b border-slate-100 space-y-3">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-4">
                Select your answer
              </p>
              {MCQ_LABELS.map((label) => {
                const isSelected = selectedOption === label
                return (
                  <button
                    key={label}
                    onClick={() => !loadingQ && setSelectedOption(label)}
                    disabled={loadingQ || submitting}
                    className={`w-full flex items-center gap-4 px-4 py-3.5 rounded-xl border text-left font-medium transition-all duration-150 ${
                      isSelected
                        ? 'bg-indigo-50 border-indigo-400 text-indigo-700 shadow-sm shadow-indigo-100'
                        : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50 hover:border-slate-300'
                    } disabled:opacity-40`}
                  >
                    <span className={`w-8 h-8 flex-shrink-0 rounded-lg flex items-center justify-center text-sm font-bold ${
                      isSelected ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-500'
                    }`}>
                      {label}
                    </span>
                    <span className="text-sm">{currentProblem?.options?.[MCQ_LABELS.indexOf(label)] ?? `Option ${label}`}</span>
                    {isSelected && <ChevronRight className="h-4 w-4 text-indigo-500 ml-auto" />}
                  </button>
                )
              })}
            </div>

            {/* Question navigation grid */}
            <div className="flex-shrink-0 px-4 py-5 border-b border-slate-100">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-3">
                Questions
              </p>
              <div className="grid grid-cols-5 gap-2">
                {Array.from({ length: numQuestions }, (_, i) => {
                  const qn = i + 1
                  const isCurrent = qn === questionNum
                  const isAnswered = !!answeredMap[qn]
                  return (
                    <div
                      key={qn}
                      className={`h-9 rounded-lg flex items-center justify-center text-xs font-bold border transition-all ${
                        isCurrent
                          ? 'bg-indigo-600 border-indigo-500 text-white'
                          : isAnswered
                          ? 'bg-emerald-50 border-emerald-200 text-emerald-600'
                          : 'bg-slate-50 border-slate-200 text-slate-400'
                      }`}
                    >
                      {qn}
                    </div>
                  )
                })}
              </div>
              <div className="flex items-center gap-4 mt-3 text-[10px] text-slate-400">
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded bg-emerald-50 border border-emerald-200" />
                  Answered
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded bg-indigo-600" />
                  Current
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded bg-slate-50 border border-slate-200" />
                  Not attempted
                </span>
              </div>
            </div>

            {/* Submit / Next */}
            <div className="flex-shrink-0 px-4 py-4">
              <button
                onClick={handleSubmitAndNext}
                disabled={submitting || loadingQ || !selectedOption}
                className="w-full rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-30 py-3.5 text-sm font-semibold text-white transition-colors"
              >
                {submitting ? 'Checking…' : questionNum >= numQuestions ? 'Submit & Finish' : 'Save & Next →'}
              </button>
              {!selectedOption && !loadingQ && (
                <p className="text-[11px] text-slate-400 text-center mt-2">Select an option to continue</p>
              )}
            </div>
          </div>
        </div>
      </div>
      </AuthGuard>
    )
  }

  // ── Phase: setup ──────────────────────────────────────────────────────────────
  return (
    <AuthGuard>
    <div className="flex h-[100dvh]">
      <Sidebar />
      <div className="md:ml-[236px] flex-1 overflow-y-auto pt-14 md:pt-0">
        <div className="max-w-lg mx-auto px-6 py-10 space-y-7">

          {/* Header */}
          <div className="flex items-center gap-3">
            <Link href="/" className="text-slate-400 hover:text-slate-700 transition-colors">
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <h1 className="text-xl font-bold text-slate-800">Configure Mock Test</h1>
          </div>

          {/* Number of questions */}
          <div>
            <label className="text-sm text-slate-700 font-semibold block mb-3">Number of questions</label>
            <div className="flex gap-3">
              {[5, 10, 15].map((n) => (
                <button
                  key={n}
                  onClick={() => setNumQuestions(n)}
                  className={`flex-1 h-10 px-4 rounded-xl border text-sm font-medium transition-colors duration-200
                    ${numQuestions === n
                      ? 'bg-indigo-50 border-indigo-400 text-indigo-700'
                      : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>

          {/* Topic filter */}
          <div>
            <label className="text-sm text-slate-700 font-semibold block mb-3">Topic filter</label>
            <div className="flex flex-wrap gap-2">
              {TOPIC_OPTIONS.map((t) => (
                <button
                  key={t}
                  onClick={() => setTopic(t)}
                  className={`h-9 px-4 rounded-xl border text-sm font-medium whitespace-nowrap transition-colors duration-200
                    ${topic === t
                      ? 'bg-indigo-50 border-indigo-400 text-indigo-700'
                      : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          {/* Difficulty */}
          <div>
            <label className="text-sm text-slate-700 font-semibold block mb-3">Difficulty</label>
            <div className="flex gap-3">
              {DIFFICULTY_OPTIONS.map((d, i) => (
                <button
                  key={i}
                  onClick={() => setDifficultyIdx(i)}
                  className={`flex-1 h-10 px-4 rounded-xl border text-sm font-medium transition-colors duration-200
                    ${difficultyIdx === i
                      ? 'bg-indigo-50 border-indigo-400 text-indigo-700'
                      : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>

          {/* Summary card */}
          <div className="bg-white/80 backdrop-blur-md border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-2xl p-5 text-sm space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Questions</span>
              <span className="text-slate-800 font-semibold">{numQuestions}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Time limit</span>
              <span className="text-slate-800 font-semibold">{formatTime(numQuestions * 120)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Topic</span>
              <span className="text-slate-800 font-semibold">{topic}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Difficulty</span>
              <span className="text-slate-800 font-semibold">{DIFFICULTY_OPTIONS[difficultyIdx].label}</span>
            </div>
          </div>

          {/* CTA */}
          <div>
            <button
              onClick={startTest}
              className="w-full rounded-xl bg-indigo-600 hover:bg-indigo-700 py-3.5 text-sm font-semibold text-white transition-colors"
            >
              Start Test ⏱
            </button>
            <p className="flex items-center justify-center gap-2 text-xs text-slate-400 mt-3">
              <Lock className="h-3 w-3 shrink-0" />
              Exam conditions · No hints · Can&apos;t go back
            </p>
          </div>

        </div>
      </div>
    </div>
    </AuthGuard>
  )
}
