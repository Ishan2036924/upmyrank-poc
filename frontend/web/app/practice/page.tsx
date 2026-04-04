'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, ChevronRight, CheckCircle, XCircle } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import Sidebar from '@/components/Sidebar'
import MathText from '@/components/MathText'
import VerificationBadge from '@/components/VerificationBadge'
import { apiGet, apiPost } from '@/lib/api'
import { Problem, SubmitResult, StudentGenome } from '@/lib/types'
import AuthGuard from '@/components/AuthGuard'
import { useAuth } from '@/lib/auth'

const TOTAL_QUESTIONS = 5

interface QuestionResult {
  problem: Problem
  result: SubmitResult | null
  answer: string
}

export default function PracticePage() {
  const { studentId } = useAuth()
  const [weakTopic, setWeakTopic] = useState<string>('')
  const [question, setQuestion] = useState<Problem | null>(null)
  const [answer, setAnswer] = useState('')
  const [result, setResult] = useState<SubmitResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [questionNum, setQuestionNum] = useState(1)
  const [history, setHistory] = useState<QuestionResult[]>([])
  const [showSummary, setShowSummary] = useState(false)
  const [showAnswer, setShowAnswer] = useState(false)

  useEffect(() => {
    apiGet(`/student/${studentId}`)
      .then((g: StudentGenome) => {
        const weakest = g.weakest_concepts[0]
        setWeakTopic(weakest?.subtopic ?? 'General')
        return weakest?.subtopic
      })
      .then((topic) => loadQuestion(topic ?? undefined))
      .catch(console.error)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const loadQuestion = async (topic?: string) => {
    setLoading(true)
    setAnswer('')
    setResult(null)
    setShowAnswer(false)
    try {
      const q = await apiPost('/mock/generate', { subject: 'Physics', topic })
      setQuestion(q)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async () => {
    if (!question || !answer.trim() || submitting) return
    setSubmitting(true)
    try {
      const res: SubmitResult = await apiPost('/mock/submit', {
        problem_id: question.problem_id,
        answer: answer.trim(),
        student_id: studentId,
      })
      setResult(res)
      setHistory((h) => [...h, { problem: question, result: res, answer }])
      if (questionNum >= TOTAL_QUESTIONS) {
        setTimeout(() => setShowSummary(true), 1800)
      } else {
        setTimeout(() => { setQuestionNum((n) => n + 1); loadQuestion(weakTopic) }, 2200)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setSubmitting(false)
    }
  }

  const handleSkip = () => {
    if (questionNum >= TOTAL_QUESTIONS) {
      setShowSummary(true)
    } else {
      setHistory((h) => [...h, { problem: question!, result: null, answer: '' }])
      setQuestionNum((n) => n + 1)
      loadQuestion(weakTopic)
    }
  }

  const handleNeedHelp = () => {
    if (!question) return
    window.location.href = `/doubt?q=${encodeURIComponent(question.question_text)}`
  }

  const correctCount = history.filter((h) => h.result?.correct).length

  if (showSummary) {
    return (
      <AuthGuard>
      <div className="flex h-screen">
        <Sidebar />
        <div className="md:ml-[80px] flex-1 overflow-y-auto">
          <div className="max-w-2xl mx-auto px-6 py-8 pb-24 md:pb-10 space-y-6">
            <h1 className="text-2xl font-bold text-slate-800 mb-1">Practice Complete! 🎉</h1>
            <p className="text-slate-500">
              You answered {correctCount} out of {history.filter((h) => h.result !== null).length} questions correctly.
            </p>

            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white/80 backdrop-blur-md border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-2xl p-5 text-center">
                <div className="text-3xl font-bold text-slate-800">{correctCount}/{TOTAL_QUESTIONS}</div>
                <div className="text-sm text-slate-500 mt-1">Score</div>
              </div>
              <div className="bg-white/80 backdrop-blur-md border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-2xl p-5 text-center">
                <div className="text-3xl font-bold text-slate-800">
                  {history.filter((h) => h.result !== null).length > 0
                    ? Math.round((correctCount / history.filter((h) => h.result !== null).length) * 100)
                    : 0}%
                </div>
                <div className="text-sm text-slate-500 mt-1">Accuracy</div>
              </div>
            </div>

            <div className="space-y-2">
              {history.map((h, i) => (
                <div key={i} className="flex items-start gap-3 bg-white/80 backdrop-blur-md border border-white/60 rounded-xl px-4 py-3 shadow-sm">
                  {h.result?.correct ? (
                    <CheckCircle className="h-5 w-5 text-emerald-500 flex-shrink-0 mt-0.5" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-400 flex-shrink-0 mt-0.5" />
                  )}
                  <div className="min-w-0">
                    <div className="text-sm text-slate-800 truncate">
                      <MathText>{h.problem?.question_text ?? '—'}</MathText>
                    </div>
                    {h.result && !h.result.correct && (
                      <div className="text-xs text-slate-400 mt-0.5">
                        Correct: <MathText>{h.result.verified_answer}</MathText>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => { setQuestionNum(1); setHistory([]); setShowSummary(false); loadQuestion(weakTopic) }}
                className="rounded-xl bg-indigo-600 hover:bg-indigo-700 px-5 py-2.5 text-sm font-semibold text-white transition-colors"
              >
                Practice again
              </button>
              <Link href="/" className="rounded-xl border border-slate-200 hover:bg-slate-50 px-5 py-2.5 text-sm text-slate-600 font-medium transition-colors">
                Home
              </Link>
            </div>
          </div>
        </div>
      </div>
      </AuthGuard>
    )
  }

  return (
    <AuthGuard>
    <div className="flex h-screen">
      <Sidebar />
      <div className="md:ml-[80px] flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-6 py-8 pb-24 md:pb-8 space-y-5">

          {/* Header */}
          <div className="flex items-center gap-3">
            <Link href="/" className="text-slate-400 hover:text-slate-700 transition-colors">
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <div>
              <h1 className="font-semibold text-slate-800">Adaptive Practice</h1>
              <p className="text-xs text-slate-400">
                Practicing: <span className="text-slate-600 font-medium">{weakTopic || '…'}</span>
              </p>
            </div>
          </div>

          {/* Progress bar */}
          <div>
            <div className="flex justify-between text-sm mb-2">
              <span className="text-slate-500">Question {questionNum} of {TOTAL_QUESTIONS}</span>
              <span className="text-slate-500">{correctCount} correct</span>
            </div>
            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-indigo-500 rounded-full transition-all"
                style={{ width: `${((questionNum - 1) / TOTAL_QUESTIONS) * 100}%` }}
              />
            </div>
          </div>

          {/* Question card */}
          <AnimatePresence mode="wait">
            {loading ? (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="bg-white/80 backdrop-blur-md border border-white/60 rounded-2xl p-6 text-center text-slate-400 text-sm shadow-[0_8px_30px_rgb(0,0,0,0.04)]"
              >
                Loading question…
              </motion.div>
            ) : question ? (
              <motion.div
                key={question.problem_id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="bg-white/80 backdrop-blur-md border border-white/60 rounded-2xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)]"
              >
                <div className="flex items-center gap-2 mb-4">
                  <span className="rounded-full bg-blue-50 border border-blue-200 px-2.5 py-0.5 text-xs font-medium text-blue-700">
                    {question.subtopic}
                  </span>
                  <span className="rounded-full bg-slate-100 border border-slate-200 px-2.5 py-0.5 text-xs text-slate-500">
                    Difficulty: {Math.round(question.difficulty * 100)}%
                  </span>
                </div>
                <div className="text-slate-800 leading-relaxed mb-5 text-sm">
                  <MathText>{question.question_text}</MathText>
                </div>

                {!result ? (
                  <>
                    <textarea
                      value={answer}
                      onChange={(e) => setAnswer(e.target.value)}
                      rows={4}
                      placeholder="Type your answer here… (LaTeX supported: $f(x)$)"
                      className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 placeholder-slate-400 resize-none outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 transition-all"
                    />
                    <p className="text-xs text-slate-400 mt-1">Tip: Use $...$ for math, e.g. $f \circ g$</p>
                  </>
                ) : (
                  <div className="space-y-3">
                    <div className={`flex items-center gap-2 rounded-xl border px-4 py-3 text-sm font-medium
                      ${result.correct
                        ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                        : 'border-red-200 bg-red-50 text-red-700'
                      }`}>
                      {result.correct ? <CheckCircle className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
                      {result.correct ? 'Correct!' : 'Incorrect'}
                      <span className="ml-1 text-xs opacity-80">· {result.explanation}</span>
                    </div>
                    {showAnswer && (
                      <div className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-700">
                        <div className="text-xs text-slate-400 mb-1 font-medium">Verified answer:</div>
                        <MathText>{result.verified_answer}</MathText>
                        <VerificationBadge verification={{
                          verified: result.correct,
                          confidence: result.confidence,
                          method: result.verification_method,
                          errors: [],
                          flagged_for_review: result.flagged_for_review,
                        }} />
                      </div>
                    )}
                    {!showAnswer && (
                      <button
                        onClick={() => setShowAnswer(true)}
                        className="text-xs text-slate-400 hover:text-slate-600 transition-colors flex items-center gap-1"
                      >
                        <ChevronRight className="h-3 w-3" /> Show answer
                      </button>
                    )}
                  </div>
                )}
              </motion.div>
            ) : null}
          </AnimatePresence>

          {/* Action buttons */}
          {!result && (
            <div className="flex gap-3">
              <button
                onClick={handleSubmit}
                disabled={submitting || !answer.trim() || loading}
                className="rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 px-5 py-2.5 text-sm font-semibold text-white transition-colors"
              >
                {submitting ? 'Checking…' : 'Submit answer'}
              </button>
              <button
                onClick={handleNeedHelp}
                className="rounded-xl border border-slate-200 hover:bg-slate-50 px-5 py-2.5 text-sm text-slate-600 font-medium transition-colors"
              >
                I need help
              </button>
              <button
                onClick={handleSkip}
                className="rounded-xl border border-slate-200 hover:bg-slate-50 px-5 py-2.5 text-sm text-slate-400 transition-colors ml-auto"
              >
                Skip →
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
    </AuthGuard>
  )
}
